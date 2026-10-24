"""Privacy regressions: uploaded data must never reach an external model."""

import json
import unittest

from langgraph.types import Command

from billing.chat import answer_question
from billing.knowledge import KnowledgeBase
from billing.samples import sample_text
from billing.workflow import build_graph

PRIVATE_TEXT = sample_text("Issues to find").replace("Alex Example", "PRIVATE_PATIENT_481") + (
    "\nAge: 61\nSex: Female\nDOB: 1965-02-03\n"
    "Guarantor: PRIVATE_GUARANTOR_727\nSubscriber ID: PRIVATE_MEMBER_848\n"
    "Address: PRIVATE_ADDRESS_383\nDoctor: PRIVATE_DOCTOR_626\n")


class ForbiddenModel:
    def text(self, *args, **kwargs):
        raise AssertionError("Uploaded data must not invoke the LLM")

    def json(self, *args, **kwargs):
        raise AssertionError("Uploaded text must not invoke the LLM")


class PrivacyTests(unittest.TestCase):
    def test_upload_workflow_and_chat_make_zero_model_calls(self):
        kb = KnowledgeBase()
        graph = build_graph(ForbiddenModel(), kb)
        config = {"configurable": {"thread_id": "private-upload"}}
        state = graph.invoke({"raw_text": PRIVATE_TEXT}, config)
        self.assertTrue(state.get("__interrupt__"))
        state = graph.invoke(Command(resume=state["bill"]), config)
        self.assertEqual(state["audit"]["potential_savings"], "340.00")
        self.assertTrue(state["letter"])
        response = answer_question(ForbiddenModel(), kb, state,
                                  "My friend PRIVATE_CHAT_929 is 42. Explain the glucose charge.",
                                  [{"role": "user", "content": "PRIVATE_HISTORY_151"}], web=True)
        self.assertTrue(response["answer"])
        self.assertIn("local", response["warning"].lower())

    def test_model_boundary_rejects_arbitrary_payload(self):
        from unittest.mock import Mock
        from billing.llm import NebiusModel, UserError
        model = object.__new__(NebiusModel)
        model.chat = Mock()
        with self.assertRaises(UserError):
            model._invoke("Test", {"bill_text": PRIVATE_TEXT})
        model.chat.invoke.assert_not_called()

    def test_synthetic_requests_do_not_include_person_fields(self):
        from billing.privacy import SyntheticRequest, model_payload
        payload = model_payload(SyntheticRequest("Issues to find", "auditor"))
        encoded = json.dumps(payload)
        for value in ("Alex Example", "Example Learning Clinic", "SYN-2026-001"):
            self.assertNotIn(value, encoded)
        self.assertFalse({"patient", "account", "provider", "age", "sex", "birth"} & payload["bill"].keys())
        self.assertIn("99213", encoded)

    def test_edited_synthetic_bill_falls_back_to_local(self):
        kb = KnowledgeBase()
        graph = build_graph(None, kb, synthetic_sample="Issues to find")
        config = {"configurable": {"thread_id": "edited-private"}}
        state = graph.invoke({"raw_text": sample_text("Issues to find")}, config)
        corrected = state["bill"]
        corrected["patient"] = "PRIVATE_EDIT_404"
        state = graph.invoke(Command(resume=corrected), config)
        self.assertFalse(state["cloud_eligible"])

    def test_every_user_edit_invalidates_synthetic_eligibility(self):
        import copy
        from billing.privacy import request_for_bill
        from billing.samples import sample_bill
        baseline = sample_bill("Issues to find").model_dump(mode="json")
        for field in ("patient", "provider", "account", "extraction_notes"):
            with self.subTest(field=field):
                changed = copy.deepcopy(baseline)
                changed[field] = ["PRIVATE_NOTE"] if field == "extraction_notes" else "PRIVATE_FIELD"
                self.assertIsNone(request_for_bill(changed, "Issues to find", "auditor"))
        for field, value in (("line_id", "PRIVATE_ID"), ("description", "PRIVATE_DESCRIPTION"),
                             ("amount", "201.00"), ("modifiers", "25"), ("service_date", "2026-10-04")):
            with self.subTest(field=field):
                changed = copy.deepcopy(baseline)
                changed["lines"][0][field] = value
                self.assertIsNone(request_for_bill(changed, "Issues to find", "auditor"))

    def test_typed_names_and_history_are_never_forwarded(self):
        from unittest.mock import patch
        from langchain_keenable import KeenableSearch
        from billing.audit import audit_bill
        from billing.privacy import model_payload
        from billing.samples import sample_bill
        kb = KnowledgeBase()
        fixture = sample_bill("Issues to find")
        state = {"bill": fixture.model_dump(mode="json"), "audit": audit_bill(fixture, kb),
                 "synthetic_sample": "Issues to find", "cloud_eligible": True}
        captured = []

        class Model:
            def text(self, system, payload):
                captured.append(json.dumps(model_payload(payload)))
                return "Fictional policy explanation [POL-BUNDLE]."

        with patch.dict("os.environ", {"KEENABLE_API_KEY": "test"}), \
                patch.object(KeenableSearch, "invoke", return_value=[]) as search:
            answer_question(Model(), kb, state, "My friend PRIVATE_CHAT_NAME is 54; explain glucose.",
                            [{"role": "user", "content": "PRIVATE_HISTORY_NAME"}], web=True)
        self.assertNotIn("PRIVATE_CHAT_NAME", captured[0])
        self.assertNotIn("PRIVATE_HISTORY_NAME", captured[0])
        self.assertEqual(search.call_args.args[0], {"query": "site:cms.gov medical billing bundled services explanation"})

    def test_transport_receives_only_reconstructed_fixtures(self):
        from unittest.mock import Mock
        from billing.llm import NebiusModel
        from billing.privacy import SyntheticRequest
        model = object.__new__(NebiusModel)
        model.chat = Mock()
        model.chat.invoke.return_value.content = "Synthetic response"
        model._invoke("Fixed system prompt", SyntheticRequest("Issues to find", "auditor"))
        messages = model.chat.invoke.call_args.args[0]
        sent = json.loads(messages[1].content)
        self.assertTrue(sent["synthetic_demo"])
        self.assertNotIn("patient", sent["bill"])
        self.assertNotIn("Alex Example", messages[1].content)


if __name__ == "__main__":
    unittest.main()
