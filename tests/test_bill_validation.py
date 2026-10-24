import unittest

from langgraph.types import Command

from billing.audit import audit_bill
from billing.extraction import parse_bill_locally
from billing.knowledge import KnowledgeBase
from billing.models import Bill
from billing.samples import sample_bill
from billing.workflow import build_graph


class BillValidationTests(unittest.TestCase):
    def test_unreadable_placeholder_cannot_produce_a_clean_audit(self):
        bill = parse_bill_locally("This document has no readable billing charge table.")
        with self.assertRaises(ValueError):
            audit_bill(bill, KnowledgeBase())

    def test_graph_stops_placeholder_before_any_model_call(self):
        class ForbiddenModel:
            def text(self, *args):
                raise AssertionError("No model call permitted")

            def json(self, *args):
                raise AssertionError("No model call permitted")

        graph = build_graph(ForbiddenModel(), KnowledgeBase())
        config = {"configurable": {"thread_id": "invalid-bill"}}
        state = graph.invoke({"raw_text": "A non-billing document with no charge rows."}, config)
        with self.assertRaises(ValueError):
            graph.invoke(Command(resume=state["bill"]), config)
        self.assertNotIn("audit", graph.get_state(config).values)

    def test_real_charges_can_replace_the_placeholder(self):
        bill = parse_bill_locally("Unrecognized document layout")
        data = bill.model_dump(mode="json")
        data["lines"] = [{"line_id": "L001", "code": "99213", "description": "Office visit",
                          "amount": "100.00", "quantity": 1}]
        result = audit_bill(Bill.model_validate(data), KnowledgeBase())
        self.assertEqual(result["total_billed"], "100.00")

    def test_suspicious_charges_are_still_audited(self):
        result = audit_bill(sample_bill("Issues to find"), KnowledgeBase())
        self.assertEqual(result["potential_savings"], "340.00")


if __name__ == "__main__":
    unittest.main()
