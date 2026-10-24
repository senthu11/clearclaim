import unittest
from collections import Counter
from billing.test_cases import cases, invalid_cases
from billing.models import Bill
from billing.audit import audit_bill
from billing.knowledge import KnowledgeBase

class PackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.kb=KnowledgeBase()
    def test_expected_results(self):
        for case in cases():
            with self.subTest(case=case['id']):
                audit=audit_bill(Bill.model_validate(case['bill']),self.kb)
                for key in ('total_billed','potential_savings','unknown_codes'):
                    self.assertEqual(audit[key],case['expected'][key])
                self.assertEqual(dict(Counter(x['category'] for x in audit['findings'])),case['expected']['categories'])
    def test_invalid_inputs(self):
        for case in invalid_cases():
            with self.subTest(case=case['id']), self.assertRaises(ValueError):
                audit_bill(Bill.model_validate(case['bill']),self.kb)
    def test_pdf_extraction_roundtrip(self):
        from scripts.generate_test_pack import document
        from billing.extraction import read_upload, parse_bill_locally
        for case in cases():
            with self.subTest(case=case['id']), document(case['bill']) as pdf:
                extracted = parse_bill_locally(read_upload(pdf.tobytes(), 'test.pdf'))
                self.assertEqual(extracted.lines, Bill.model_validate(case['bill']).lines)

if __name__=='__main__': unittest.main()
