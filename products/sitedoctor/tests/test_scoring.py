import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sitedoctor.checks import CheckResult
from sitedoctor.scoring import score_audit


class TestScoring(unittest.TestCase):
    def test_all_passing_scores_100(self):
        results = [CheckResult("a", "A", "PASS", "info", "ok")]
        audit = score_audit("example.com", results)
        self.assertEqual(audit.score, 100)
        self.assertEqual(audit.passed, results)

    def test_critical_finding_deducts_25(self):
        results = [CheckResult("a", "A", "FAIL", "critical", "bad")]
        audit = score_audit("example.com", results)
        self.assertEqual(audit.score, 75)
        self.assertEqual(len(audit.critical), 1)

    def test_score_floors_at_zero(self):
        results = [CheckResult(f"c{i}", "C", "FAIL", "critical", "bad") for i in range(10)]
        audit = score_audit("example.com", results)
        self.assertEqual(audit.score, 0)

    def test_buckets_by_severity(self):
        results = [
            CheckResult("a", "A", "FAIL", "critical", "x"),
            CheckResult("b", "B", "WARN", "high", "y"),
            CheckResult("c", "C", "FAIL", "medium", "z"),
        ]
        audit = score_audit("example.com", results)
        self.assertEqual(len(audit.critical), 1)
        self.assertEqual(len(audit.high), 1)
        self.assertEqual(len(audit.medium), 1)


if __name__ == "__main__":
    unittest.main()
