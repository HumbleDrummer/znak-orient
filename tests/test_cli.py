from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from znak_orient.cli import main


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_verify_demo_writes_inspectable_scoped_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            exit_code = main(
                [
                    "verify-demo",
                    "--input",
                    str(ROOT / "demo" / "evidence-package.json"),
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(0, exit_code)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("PASS", result["run_receipt"]["status"])
            self.assertEqual("ORIENTATION_TRANSFORM_ONLY", result["run_receipt"]["scope"])
            self.assertIn("does not claim project completion", result["run_receipt"]["claim_limit"])


if __name__ == "__main__":
    unittest.main()
