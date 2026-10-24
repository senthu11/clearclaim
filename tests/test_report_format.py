import re
import unittest

from billing.advocate import local_summary
from billing.advocate import escape_currency
from billing.audit import audit_bill
from billing.knowledge import KnowledgeBase
from billing.samples import sample_bill


class ReportFormatTests(unittest.TestCase):
    def setUp(self):
        self.audit = audit_bill(sample_bill("Issues to find"), KnowledgeBase())

    def test_currency_does_not_trigger_math_rendering(self):
        summary = local_summary(self.audit)
        self.assertIsNone(re.search(r"(?<!\\)\$", summary))
        self.assertIn("840.00", summary)
        self.assertIn("340.00", summary)

    def test_repeated_findings_are_grouped_in_overview(self):
        summary = local_summary(self.audit)
        self.assertEqual(summary.count("Above fictional reference prices"), 1)
        self.assertIn("3 lines", summary)
        self.assertIn("Next steps", summary)
        self.assertLess(len(summary), 1800)

    def test_currency_escaping_preserves_existing_escapes(self):
        source = "Billed $200.00; reference $100.00. Already escaped \\$40.00."
        escaped = escape_currency(source)
        self.assertIsNone(re.search(r"(?<!\\)\$", escaped))
        self.assertEqual(escape_currency(escaped), escaped)
        self.assertIn(r"\$200.00", escaped)


if __name__ == "__main__":
    unittest.main()
