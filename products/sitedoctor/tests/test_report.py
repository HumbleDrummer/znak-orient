import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sitedoctor.checks import CheckResult
from sitedoctor.report import NeglectAssumptions, estimate_cost_of_neglect, render_report
from sitedoctor.scoring import score_audit


class TestNeglectEstimate(unittest.TestCase):
    def test_estimate_is_positive_and_capped(self):
        assumptions = NeglectAssumptions(
            extra_load_seconds=3.0,
            monthly_visits=10_000,
            baseline_conversion_rate=0.02,
            average_order_value=60.0,
        )
        estimate = estimate_cost_of_neglect(assumptions)
        self.assertAlmostEqual(estimate["lost_conversion_share"], 0.21)
        self.assertGreater(estimate["estimated_lost_revenue_per_month"], 0)

    def test_conversion_share_never_exceeds_100_percent(self):
        assumptions = NeglectAssumptions(
            extra_load_seconds=100.0,
            monthly_visits=1000,
            baseline_conversion_rate=0.02,
            average_order_value=60.0,
        )
        estimate = estimate_cost_of_neglect(assumptions)
        self.assertLessEqual(estimate["lost_conversion_share"], 1.0)


class TestRenderReport(unittest.TestCase):
    def test_report_includes_score_and_findings(self):
        results = [
            CheckResult("a", "SSL certificate", "FAIL", "critical", "expired"),
            CheckResult("b", "DNS resolution", "PASS", "info", "resolves"),
        ]
        audit = score_audit("example.com", results)
        report = render_report(audit)
        self.assertIn("example.com", report)
        self.assertIn(str(audit.score), report)
        self.assertIn("SSL certificate", report)

    def test_report_labels_neglect_estimate_as_estimate(self):
        audit = score_audit("example.com", [CheckResult("a", "A", "PASS", "info", "ok")])
        neglect = estimate_cost_of_neglect(
            NeglectAssumptions(2.0, 10_000, 0.02, 60.0)
        )
        report = render_report(audit, neglect=neglect)
        self.assertIn("estimate", report.lower())
        self.assertIn("not a guarantee", report.lower())

    def test_report_includes_competitor_table(self):
        audit = score_audit("example.com", [])
        competitor = score_audit("competitor.com", [])
        report = render_report(audit, competitors=[competitor])
        self.assertIn("competitor.com", report)


if __name__ == "__main__":
    unittest.main()
