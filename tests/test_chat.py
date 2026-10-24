import os
import unittest
from unittest.mock import patch

from billing.chat import answer_question
from billing.knowledge import KnowledgeBase
from billing.audit import audit_bill
from billing.samples import sample_bill


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase()
        fixture = sample_bill("Issues to find")
        self.state = {"bill": fixture.model_dump(mode="json"), "audit": audit_bill(fixture, self.kb),
                      "synthetic_sample": "Issues to find", "cloud_eligible": True}

    def test_search_failure_falls_back_without_sending_bill(self):
        from langchain_keenable import KeenableSearch

        class Model:
            def text(self, system, payload):
                return "See the fictional benchmark [PRICE-99213]."

        with patch.dict(os.environ, {"KEENABLE_API_KEY": "test-key"}), \
                patch.object(KeenableSearch, "invoke", side_effect=RuntimeError("network")) as search:
            result = answer_question(Model(), self.kb, self.state, "What is a duplicate?", [], web=True)
        self.assertIn("unavailable", result["warning"])
        self.assertEqual(search.call_args.args[0], {"query": "site:cms.gov duplicate medical bill charges explanation"})
        self.assertTrue(all(source["kind"] == "synthetic" for source in result["sources"]))

    def test_web_sources_and_unverified_citations(self):
        from langchain_keenable import KeenableSearch

        class Model:
            def text(self, system, payload):
                return "Context [WEB-1]. Unsupported [POL-INVENTED]."

        with patch.dict(os.environ, {"KEENABLE_API_KEY": "test-key"}), \
                patch.object(KeenableSearch, "invoke", return_value=[
                    {"title": "Public source", "url": "https://example.org/billing", "snippet": "Example text"}
                ]):
            result = answer_question(Model(), self.kb, self.state, "Explain billing", [], web=True)
        self.assertIn("not sent to the LLM", result["warning"])
        self.assertNotIn("[WEB-1]", result["answer"])
        self.assertNotIn("POL-INVENTED", result["answer"])
        self.assertEqual(result["sources"][-1]["url"], "https://example.org/billing")


if __name__ == "__main__":
    unittest.main()
