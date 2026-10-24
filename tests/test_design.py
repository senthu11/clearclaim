import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from billing.design import demo_cases
from billing.knowledge import KnowledgeBase

ROOT = Path(__file__).resolve().parents[1]
test_tmp = ROOT / ".uv-cache/test-tmp"
test_tmp.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(test_tmp)

from streamlit.testing.v1 import AppTest


class DesignTests(unittest.TestCase):
    def test_review_status_and_upload_callout(self):
        with patch("billing.llm.NebiusModel", side_effect=AssertionError("No cloud calls from overview")):
            app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=60)
            next(button for button in app.button if button.label == "Mark as reviewed").click().run(timeout=60)
            self.assertFalse(app.exception)
            self.assertIn("DEMO-001", app.session_state["reviewed_demo_cases"])
            next(item for item in app.radio if item.label == "Queue status").set_value("Reviewed").run(timeout=60)
            self.assertFalse(app.exception)
            self.assertIn("select_DEMO-001", [item.key for item in app.button])
            next(button for button in app.button if button.label == "Choose a file").click().run(timeout=60)
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["bill_source"], "Upload a bill")

    def test_dashboard_totals_are_backed_by_demo_rules(self):
        cases = demo_cases(KnowledgeBase())
        self.assertEqual(len(cases), 3)
        self.assertEqual(sum(item["status"] == "Needs review" for item in cases), 1)
        self.assertEqual(cases[0]["audit"]["potential_savings"], "340.00")

    def test_navigation_queue_and_analyze_button(self):
        with patch("billing.llm.NebiusModel", side_effect=AssertionError("Dashboard must not call cloud")):
            app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=60)
            self.assertFalse(app.exception)
            self.assertTrue(any(item.value == "Investigation queue" for item in app.subheader))
            next(item for item in app.radio if item.label == "Queue status").set_value("Clear").run(timeout=60)
            self.assertFalse(app.exception)
            self.assertNotIn("select_DEMO-001", [item.key for item in app.button])
            next(button for button in app.button if button.label == "Open investigation").click().run(timeout=60)
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["navigation"], "Investigations")
            self.assertEqual(app.session_state["stage"], "review")
            self.assertEqual(app.session_state["sample_scenario"], "Clean comparison")
            next(item for item in app.radio if item.label == "Navigation").set_value("Reports").run(timeout=60)
            self.assertFalse(app.exception)
            self.assertTrue(any(item.value == "Reports" for item in app.title))


if __name__ == "__main__":
    unittest.main()
