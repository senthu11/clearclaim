import unittest
from decimal import Decimal

from billing.audit import audit_bill
from billing.knowledge import KnowledgeBase
from billing.models import Bill


def bill(lines, **kwargs):
    return Bill.model_validate({
        "patient": "Demo Patient", "provider": "Demo Clinic", "account": "SYN-1",
        "visit_type": "outpatient", "visit_start": "2026-10-01", "visit_end": "2026-10-01",
        "lines": [{**dict(line_id=f"L{i + 1:03}", code="99213", description="Office visit",
                       service_date="2026-10-01", quantity=1, amount="200.00"), **line}
                  for i, line in enumerate(lines)], **kwargs,
    })


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = KnowledgeBase()

    def test_overlap_does_not_double_count(self):
        result = audit_bill(bill([{}, {}]), self.kb)
        # Fictional benchmark is $100: $100 on original plus $200 duplicate.
        self.assertEqual(result["potential_savings"], "300.00")
        self.assertEqual(result["total_billed"], "400.00")
        self.assertIn("duplicate", {f["category"] for f in result["findings"]})

    def test_modifiers_and_missing_dates_are_not_duplicates(self):
        for lines in ([{}, {"modifiers": "25"}],
                      [{"service_date": None}, {"service_date": None}]):
            result = audit_bill(bill(lines), self.kb)
            self.assertNotIn("duplicate", {f["category"] for f in result["findings"]})

    def test_pricing_uses_quantity(self):
        result = audit_bill(bill([{"quantity": 2, "amount": "200.00"}]), self.kb)
        self.assertEqual(result["potential_savings"], "0.00")

    def test_unknown_code_does_not_invent_a_price(self):
        result = audit_bill(bill([{"code": "ZZ999", "amount": "999.99"}]), self.kb)
        self.assertEqual(result["potential_savings"], "0.00")
        self.assertEqual(result["unknown_codes"], ["ZZ999"])

    def test_bundle_and_overlap_cap(self):
        result = audit_bill(bill([
            {"code": "80053", "amount": "70.00"},
            {"code": "82947", "amount": "40.00"},
        ]), self.kb)
        self.assertEqual(result["potential_savings"], "40.00")
        self.assertIn("unbundling", {f["category"] for f in result["findings"]})

    def test_distinct_service_modifier_suppresses_bundle(self):
        result = audit_bill(bill([
            {"code": "80053", "amount": "50.00"},
            {"code": "82947", "amount": "10.00", "modifiers": "59"},
        ]), self.kb)
        self.assertEqual(result["findings"], [])

    def test_clean_sample_has_no_findings(self):
        from billing.samples import SAMPLE_LINES
        for sample in ("Clean comparison", "Distinct services"):
            data = bill([{"code": code, "description": desc, "service_date": day,
                          "quantity": qty, "amount": amount, "modifiers": mod}
                         for code, desc, day, qty, amount, mod in SAMPLE_LINES[sample]])
            self.assertEqual(audit_bill(data, self.kb)["findings"], [])

    def test_mismatch_has_no_assumed_savings(self):
        result = audit_bill(bill([{"service_date": "2026-10-02", "amount": "100.00"}]), self.kb)
        self.assertEqual(result["potential_savings"], "0.00")
        self.assertIn("date_mismatch", {f["category"] for f in result["findings"]})

    def test_every_citation_exists(self):
        result = audit_bill(bill([{}, {}]), self.kb)
        for finding in result["findings"]:
            self.assertTrue(finding["citations"])
            self.assertTrue(all(self.kb.get(source) for source in finding["citations"]))

    def test_exact_code_retrieval(self):
        docs = self.kb.retrieve("Explain benchmark for 99213")
        self.assertIn("PRICE-99213", {doc.metadata["source_id"] for doc in docs})

    def test_invalid_money_and_duplicate_ids_rejected(self):
        for amount in ("-1", "NaN", "1.234"):
            with self.assertRaises(ValueError):
                bill([{"amount": amount}])
        with self.assertRaises(ValueError):
            Bill.model_validate({"lines": [
                {"line_id": "L001", "code": "99213", "amount": "10"},
                {"line_id": "L001", "code": "99213", "amount": "10"},
            ]})


class GraphTests(unittest.TestCase):
    def test_pauses_before_audit_and_uses_corrected_values(self):
        from billing.workflow import build_graph
        from langgraph.types import Command

        calls = []

        class FakeModel:
            def json(self, system, payload, schema):
                calls.append("extract")
                return bill([{}]).model_dump(mode="json")

            def text(self, system, payload):
                calls.append("explain")
                return "Synthetic demonstration. Review the cited findings."

        graph = build_graph(FakeModel(), KnowledgeBase())
        config = {"configurable": {"thread_id": "test-review"}}
        from billing.samples import sample_text
        result = graph.invoke({"raw_text": sample_text("Clean comparison")}, config)
        self.assertTrue(result.get("__interrupt__"))
        self.assertNotIn("audit", result)
        corrected = result["bill"]
        corrected["lines"][0]["amount"] = "80.00"
        result = graph.invoke(Command(resume=corrected), config)
        self.assertEqual(result["audit"]["potential_savings"], "0.00")
        self.assertTrue(result["letter"])
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
