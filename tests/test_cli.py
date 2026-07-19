from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stderr
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
            self.assertEqual([], list(Path(directory).glob(".*.tmp")))

    def test_verify_demo_rejects_duplicate_json_keys_before_orientation(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "ambiguous.json"
            output = Path(directory) / "result.json"
            input_path.write_text(
                '{"schema_version":"0.3C","schema_version":"OVERRIDE"}',
                encoding="utf-8",
            )

            error_output = io.StringIO()
            with redirect_stderr(error_output):
                exit_code = main(
                    ["verify-demo", "--input", str(input_path), "--output", str(output)]
                )

            self.assertEqual(2, exit_code)
            self.assertFalse(output.exists())
            self.assertIn("duplicate JSON object key", error_output.getvalue())


if __name__ == "__main__":
    unittest.main()
