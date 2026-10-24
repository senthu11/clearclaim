import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pymupdf
from langgraph.types import Command
from billing import storage
from billing.review import decision, snapshot, compare_eob, amount, snapshot_knowledge
from billing.exports import selected_letter, letter_pdf
from billing.extraction import read_upload
from billing.llm import UserError
from billing.samples import sample_bill, sample_document, sample_text
from billing.audit import audit_bill
from billing.knowledge import KnowledgeBase
from billing.workflow import build_graph
from billing.provenance import locate, highlighted

class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = KnowledgeBase()
        cls.bill = sample_bill('Issues to find').model_dump(mode='json')
        cls.state = {'bill': cls.bill, 'audit': audit_bill(sample_bill('Issues to find'), cls.kb), 'raw_text': 'PRIVATE SOURCE'}

    def test_decisions_and_export_privacy(self):
        original = copy.deepcopy(self.state)
        review = decision({}, 'F001', 'Explained', 'Provider supplied records')
        self.assertEqual(len(decision(review, 'F001', 'Explained', 'Provider supplied records')['history']), 1)
        data = snapshot(self.state, {'name': 'SECRET NAME'}, review, self.kb)
        self.assertNotIn('SECRET NAME', json.dumps(data))
        self.assertNotIn('PRIVATE SOURCE', json.dumps(data))
        self.assertEqual(self.state, original)
        data['review']['decisions']['F001']['note'] = 'Changed'
        self.assertEqual(review['decisions']['F001']['note'], 'Provider supplied records')
        frozen = snapshot_knowledge(data, self.kb)
        self.assertEqual(frozen.get('POL-SAVINGS').page_content, self.kb.get('POL-SAVINGS').page_content)

    def test_statement_mismatch_requires_explanation(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=60)
        next(x for x in app.button if x.label == 'Open investigation').click().run(timeout=60)
        next(x for x in app.text_input if x.label == 'Statement charge total USD (optional)').set_value('900.00')
        next(x for x in app.button if x.label == 'Confirm charges and run audit').click().run(timeout=60)
        self.assertEqual(app.session_state['stage'], 'review')
        self.assertTrue(any('differ' in x.value for x in app.error))
        next(x for x in app.text_input if x.label == 'Explain any difference from the charge total').set_value('Separate statement adjustment needs review')
        next(x for x in app.button if x.label == 'Confirm charges and run audit').click().run(timeout=60)
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['stage'], 'results')
        self.assertEqual(app.session_state['review_meta']['financial']['statement_total'], '900.00')

    def test_encrypted_storage_roundtrip_wrong_password_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identifier = storage.save({'patient': 'PRIVATE NAME'}, 'long passphrase test', root=root)
            self.assertNotIn('PRIVATE NAME', storage.path_for(identifier, root).read_text())
            self.assertEqual(storage.load(identifier, 'long passphrase test', root)['patient'], 'PRIVATE NAME')
            with self.assertRaises(ValueError):
                storage.load(identifier, 'incorrect passphrase', root)
            document = json.loads(storage.path_for(identifier, root).read_text())
            document['token'] = document['token'][:20] + 'x' + document['token'][21:]
            storage.path_for(identifier, root).write_text(json.dumps(document))
            with self.assertRaises(ValueError):
                storage.load(identifier, 'long passphrase test', root)
            with self.assertRaises(ValueError):
                storage.delete('../outside', root)
            storage.delete(identifier, root)
            self.assertEqual(storage.list_saved(root), [])

    def test_money_and_ambiguous_eob(self):
        for value in ('NaN', 'Infinity', '-1', '1.001'):
            with self.assertRaises(ValueError): amount(value)
        line = self.bill['lines'][0]
        eob = [{'code': line['code'], 'service_date': line['service_date'], 'billed': line['amount']}]
        self.assertEqual(compare_eob([line, line], eob)[0]['match'], 'Unresolved')
        self.assertEqual(compare_eob([line], eob)[0]['billed_difference'], '0.00')
        self.assertTrue(all(x['match'] == 'Unresolved' for x in compare_eob([line], eob * 2)))

    def test_optional_ai_failure_preserves_full_audit(self):
        class Offline:
            def json(self, *args): raise UserError('Offline')
            def text(self, *args): raise UserError('Offline')
        graph = build_graph(Offline(), self.kb, 'Issues to find')
        config = {'configurable': {'thread_id': 'offline-test'}}
        graph.invoke({'raw_text': sample_text('Issues to find')}, config)
        result = graph.invoke(Command(resume=self.bill), config)
        self.assertEqual(result['audit']['potential_savings'], '340.00')
        self.assertIn('letter', result)
        self.assertEqual(len(result['warnings']), 3)

    def test_selective_letter_and_paginated_pdf(self):
        data = snapshot(self.state, {}, {}, self.kb)
        letter = selected_letter(data, ['F001'], 'Firm')
        self.assertIn('F001:', letter)
        self.assertNotIn('F002:', letter)
        with pymupdf.open(stream=letter_pdf(letter + '\nLong paragraph <literal> & text.' * 200), filetype='pdf') as document:
            self.assertGreater(document.page_count, 1)
            text = ''.join(page.get_text() for page in document)
            self.assertIn('<literal>', text)

    def test_source_candidates_and_mixed_pdf_ocr(self):
        content = sample_document('Issues to find')
        matches = locate(content, self.bill['lines'][0])
        self.assertTrue(matches)
        self.assertTrue(highlighted(content, matches[0]).startswith(b'\x89PNG'))
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((30, 30), 'A long digital heading which is not the scanned charges underneath')
            page.insert_image(pymupdf.Rect(0, 80, 595, 820), stream=sample_document('Issues to find', image=True))
            document.new_page().insert_text((30, 30), 'Second page digital text with enough characters to avoid OCR')
            content = document.tobytes()
        with patch('billing.extraction.ocr', return_value='scanned charges') as engine:
            result = read_upload(content, 'mixed.pdf')
        engine.assert_called_once()
        self.assertIn('scanned charges', result)
        self.assertIn('\f', result)

    def test_saved_review_ui_and_decision_roundtrip(self):
        from streamlit.testing.v1 import AppTest
        data = snapshot(self.state, {}, {}, self.kb)
        item = {'id': 'a' * 32, 'created': '2026-10-24', 'expires': '2026-11-24'}
        with patch('billing.storage.list_saved', return_value=[item]), patch('billing.storage.load', return_value=data):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=60)
            next(x for x in app.radio if x.label == 'Navigation').set_value('Saved reviews').run(timeout=60)
            next(x for x in app.button if x.label == 'Open saved review').click().run(timeout=60)
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['stage'], 'results')
            next(x for x in app.selectbox if x.label == 'Your assessment').set_value('Explained')
            next(x for x in app.text_area if x.label == 'Your notes').set_value('Separate service confirmed')
            next(x for x in app.button if x.label == 'Save assessment').click().run(timeout=60)
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['review_meta']['decisions']['F001']['status'], 'Explained')
            self.assertEqual(app.session_state['result']['audit'], self.state['audit'])
            next(x for x in app.button if x.label == 'Clear this review and personal details').click().run(timeout=60)
            self.assertNotIn('result', app.session_state)
            self.assertNotIn('review_meta', app.session_state)

    def test_expired_reviews_removed_on_listing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identifier = storage.save({'test': True}, 'long passphrase test', root=root)
            path = storage.path_for(identifier, root)
            document = json.loads(path.read_text())
            document['expires'] = '2000-01-01T00:00:00+00:00'
            path.write_text(json.dumps(document))
            self.assertEqual(storage.list_saved(root), [])
            self.assertFalse(path.exists())

if __name__ == '__main__': unittest.main()
