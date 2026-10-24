"""UI workflow integration uses a substitute model; it makes no paid calls."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TEST_TMP = ROOT / ".uv-cache/test-tmp"
TEST_TMP.mkdir(parents=True, exist_ok=True)
# Streamlit allocates a temporary directory during import, so configure it first.
tempfile.tempdir = str(TEST_TMP)

from streamlit.testing.v1 import AppTest


class DemoModel:
    def __init__(self, name):
        pass

    def json(self, system, payload, schema):
        from billing.privacy import model_payload
        return {"lines": model_payload(payload)["lines"]}

    def text(self, system, payload):
        return "This is a synthetic price comparison [POL-PRICE]. Ask for a billing review."


class AppTests(unittest.TestCase):
    def test_upload_path_never_constructs_cloud_model(self):
        from types import SimpleNamespace
        from billing.samples import sample_document
        upload = SimpleNamespace(name="uploaded.pdf", getvalue=lambda: sample_document("Issues to find"))
        with patch("billing.llm.NebiusModel", side_effect=AssertionError("No cloud model for uploads")) as factory, \
                patch("streamlit.file_uploader", return_value=upload):
            app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=60)
            next(item for item in app.radio if item.label == "Navigation").set_value("Investigations").run(timeout=60)
            next(item for item in app.radio if item.label == "Bill source").set_value("Upload a bill").run(timeout=60)
            next(button for button in app.button if button.label == "Extract bill charges").click().run(timeout=60)
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["stage"], "review")
            next(button for button in app.button if button.label == "Confirm charges and run audit").click().run(timeout=60)
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["stage"], "results")
            self.assertFalse(app.session_state["result"]["cloud_eligible"])
            factory.assert_not_called()

    def test_review_report_and_chat(self):
        with patch("billing.llm.NebiusModel", DemoModel), patch.object(tempfile, "tempdir", str(TEST_TMP)):
            app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=60)
            self.assertFalse(app.exception)
            next(item for item in app.radio if item.label == "Navigation").set_value("Investigations").run(timeout=60)
            next(button for button in app.button if button.label == "Extract bill charges").click().run(timeout=60)
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["stage"], "review")
            next(button for button in app.button if button.label == "Confirm charges and run audit").click().run(timeout=60)
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["stage"], "results")
            self.assertEqual(app.session_state["result"]["audit"]["potential_savings"], "340.00")
            self.assertEqual(len(app.metric), 3)
            app.chat_input[0].set_value("Why is this charge flagged?").run(timeout=60)
            self.assertFalse(app.exception)
            self.assertEqual(len(app.chat_message), 2)
            self.assertIn("POL-PRICE", app.session_state["messages"][-1]["content"])


if __name__ == "__main__":
    unittest.main()
