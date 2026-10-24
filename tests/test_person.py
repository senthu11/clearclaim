import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from billing.person import LocalPerson, personalized_bill
from billing.privacy import model_payload
from billing.samples import sample_bill

ROOT = Path(__file__).resolve().parents[1]
test_tmp = ROOT / ".uv-cache/test-tmp"
test_tmp.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(test_tmp)

from streamlit.testing.v1 import AppTest


class PersonTests(unittest.TestCase):
    def test_personalization_does_not_mutate_agent_bill(self):
        source = sample_bill("Issues to find").model_dump(mode="json")
        person = LocalPerson(name="PRIVATE_NAME_412", age=57, sex="Female", reference="PRIVATE_REF_381")
        result = personalized_bill(source, person.model_dump())
        self.assertEqual(source["patient"], "Alex Example")
        self.assertEqual(result["patient"], "PRIVATE_NAME_412")
        self.assertEqual(result["account"], "PRIVATE_REF_381")
        self.assertNotIn("age", result)
        self.assertNotIn("sex", result)

    def test_person_form_cloud_isolation_and_clear(self):
        captured = []

        class Model:
            def __init__(self, name):
                pass

            def json(self, system, payload, schema):
                data = model_payload(payload)
                captured.append(json.dumps(data))
                return {"lines": data["lines"]}

            def text(self, system, payload):
                captured.append(json.dumps(model_payload(payload)))
                return "Synthetic explanation [POL-SAVINGS]."

        with patch("billing.llm.NebiusModel", Model):
            app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=60)
            next(item for item in app.text_input if item.label == "Full name (optional)").set_value("PRIVATE_NAME_412")
            next(item for item in app.number_input if item.label == "Age (optional)").set_value(57)
            next(item for item in app.selectbox if item.label == "Sex (optional)").set_value("Female")
            next(item for item in app.text_input if item.label == "Bill reference (optional)").set_value("PRIVATE_REF_381")
            next(button for button in app.button if button.label == "Save for this session").click().run(timeout=60)
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["local_person"]["name"], "PRIVATE_NAME_412")
            next(button for button in app.button if button.label == "Analyze a bill").click().run(timeout=60)
            next(item for item in app.checkbox if item.label == "Use cloud AI for this fixed synthetic sample").check().run(timeout=60)
            next(button for button in app.button if button.label == "Extract bill charges").click().run(timeout=60)
            next(button for button in app.button if button.label == "Confirm charges and run audit").click().run(timeout=60)
            self.assertFalse(app.exception)
            self.assertEqual(len(captured), 3)
            self.assertTrue(all("PRIVATE_NAME_412" not in data and "PRIVATE_REF_381" not in data for data in captured))
            self.assertNotIn("local_person", app.session_state["result"])
            self.assertFalse(any("PRIVATE_NAME_412" in item.value for item in app.text_area))
            next(item for item in app.checkbox if item.label == "Include patient, provider and account details in downloads and saved reviews").check().run(timeout=60)
            self.assertTrue(any("PRIVATE_NAME_412" in item.value for item in app.text_area))
            next(item for item in app.radio if item.label == "Navigation").set_value("Overview").run(timeout=60)
            next(button for button in app.button if button.label == "Clear details").click().run(timeout=60)
            self.assertFalse(app.exception)
            self.assertNotIn("local_person", app.session_state)


if __name__ == "__main__":
    unittest.main()
