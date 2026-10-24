"""Component checks independent of cloud clients and the graph runtime."""
import io
import json
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pymupdf
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
TEST_TMP = ROOT / ".uv-cache/test-tmp"
TEST_TMP.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(TEST_TMP)
from streamlit.testing.v1 import AppTest

from billing.audit import audit_bill
from billing.samples import sample_bill, sample_document
from billing.workspace import preview_page

ROOT = Path(__file__).resolve().parents[1]


def reference_fixture():
    # The deterministic auditor needs exact reference data, not vector retrieval.
    return SimpleNamespace(
        prices={row["code"]: row for row in json.loads((ROOT / "data/pricing.json").read_text())},
        policies=json.loads((ROOT / "data/policies.json").read_text()))


class EvidenceWorkspaceTests(unittest.TestCase):
    def test_restored_sample_totals_and_nonoverlap(self):
        result = audit_bill(sample_bill("Issues to find"), reference_fixture())
        self.assertEqual((result["total_billed"], result["potential_savings"]), ("840.00", "340.00"))
        self.assertEqual(len(result["findings"]), 7)
        for scenario in ("Clean comparison", "Distinct services"):
            self.assertEqual(audit_bill(sample_bill(scenario), reference_fixture())["findings"], [])

    def test_preview_pdf_and_image_are_bounded_png(self):
        for image in (False, True):
            content = sample_document("Issues to find", image=image)
            preview = preview_page(content, "bill.png" if image else "bill.pdf")
            with Image.open(io.BytesIO(preview)) as rendered:
                self.assertEqual(rendered.format, "PNG")
                self.assertLessEqual(rendered.width, 1400)
                self.assertLessEqual(rendered.height, 1800)

    def test_preview_uses_selected_pdf_page(self):
        with pymupdf.open() as doc:
            doc.new_page(width=200, height=300)
            doc.new_page(width=400, height=200)
            content = doc.tobytes()
        with Image.open(io.BytesIO(preview_page(content, "bill.pdf", 0))) as first:
            self.assertLess(first.width, first.height)
        with Image.open(io.BytesIO(preview_page(content, "bill.pdf", 1))) as second:
            self.assertGreater(second.width, second.height)

    def test_confirmation_preserves_original_and_returns_edits(self):
        app = AppTest.from_string('''
import streamlit as st
from billing.samples import sample_bill, sample_document, sample_text
from billing.workspace import confirm_charges
st.session_state.result = {"raw_text": sample_text("Issues to find")}
st.session_state.source_document = {"content": sample_document("Issues to find"), "filename": "bill.pdf"}
original = sample_bill("Issues to find").model_dump(mode="json")
submitted, edited, metadata = confirm_charges(original)
if submitted:
    st.session_state.confirmed = metadata
    st.session_state.original_patient = original["patient"]
''').run(timeout=30)
        self.assertFalse(app.exception)
        next(field for field in app.text_input if field.label == "Patient").set_value("Corrected locally")
        next(button for button in app.button if button.label == "Confirm charges and run audit").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["confirmed"]["patient"], "Corrected locally")
        self.assertEqual(app.session_state["original_patient"], "Alex Example")

    def test_new_bill_clears_source_and_charge_state(self):
        app = AppTest.from_string('''
import streamlit as st
from billing.design import new_bill
if "initialized" not in st.session_state:
    st.session_state.update(initialized=True, source_document={"content": b"private"},
                            source_page=2, charge_editor={"edited_rows": {0: {"amount": "1"}}})
st.button("New bill", on_click=new_bill)
''').run(timeout=30)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        for key in ("source_document", "source_page", "charge_editor"):
            self.assertNotIn(key, app.session_state)

    def test_report_groups_questions_and_handles_no_findings(self):
        app = AppTest.from_string('''
import streamlit as st
from billing.workspace import report_questions
report_questions({"findings": [
    {"category":"duplicate", "title":"Possible repeated charge"},
    {"category":"duplicate", "title":"Another repeated charge"}]})
report_questions({"findings": []})
''').run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(len(app.expander), 1)
        self.assertEqual(len(app.success), 1)


if __name__ == "__main__":
    unittest.main()
