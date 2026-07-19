from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from znak_orient.canonical import canonical_json_bytes, seal_checkpoint, verify_checkpoint_integrity
from znak_orient.engine import OrientationError, evaluate_success_condition, orient


ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = ROOT / "demo" / "evidence-package.json"


def demo_package():
    return json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def intake_by_id(result):
    return {item["change_id"]: item for item in result["intake"]}


class DemoOrientationTests(unittest.TestCase):
    def setUp(self):
        self.package = demo_package()
        self.result = orient(self.package)
        self.intake = intake_by_id(self.result)

    def test_required_synthetic_demo_orientation(self):
        self.assertEqual("RECEIPT_NOT_PASS", self.intake["chg-unsupported-success"]["reason"])
        self.assertEqual("IMPORTED_TEXT_IS_DATA_NOT_INSTRUCTION", self.intake["trace-prompt-injection"]["reason"])
        self.assertEqual("IGNORED", self.intake["trace-prompt-injection"]["status"])
        self.assertEqual("CONFLICT_PRESERVED", self.intake["chg-entrypoint-conflict"]["reason"])
        self.assertEqual("AUTHORIZED_MEANINGFUL_CHANGE", self.intake["chg-publication-gate"]["reason"])
        self.assertEqual("DUPLICATE", self.intake["chg-publication-gate-duplicate"]["reason"])
        self.assertEqual("STALE_STATE", self.intake["chg-stale-phase"]["reason"])
        self.assertEqual("UNAUTHORIZED_OVERRIDE", self.intake["chg-unauthorized-goal"]["reason"])
        self.assertEqual("RECOVERY_CARD_CONTAMINATION", self.intake["rc-forged-writeback"]["reason"])

        checkpoint = self.result["checkpoint"]
        self.assertEqual("Clean-checkout validation failed; ZNAK ORIENT is not yet judge-ready.", checkpoint["city_position"])
        self.assertEqual("BLOCKED", checkpoint["voltage"])
        self.assertEqual(1, len([item for item in checkpoint["conflicts"] if item["status"] == "DISPUTED"]))
        self.assertEqual(1, len([item for item in checkpoint["unknowns"] if item["critical"]]))
        self.assertEqual("resolve:demo.entrypoint", checkpoint["primary_next_step"]["action_id"])
        self.assertIsInstance(checkpoint["primary_next_step"], dict)
        self.assertEqual("PASS", self.result["run_receipt"]["status"])

    def test_replay_is_byte_deterministic(self):
        first = orient(copy.deepcopy(self.package))
        second = orient(copy.deepcopy(self.package))
        self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))
        self.assertEqual(first["checkpoint"]["integrity"], second["checkpoint"]["integrity"])

    def test_duplicate_rejection_has_no_second_effect(self):
        publication_lamps = [
            lamp for lamp in self.result["checkpoint"]["active_lamps"] if lamp["subject"] == "release.publication"
        ]
        self.assertEqual(1, len(publication_lamps))
        self.assertEqual(["src-authorized-change"], publication_lamps[0]["source_ids"])

    def test_unsupported_newer_completion_does_not_replace_position(self):
        completion_lamps = [
            lamp for lamp in self.result["checkpoint"]["active_lamps"] if lamp["subject"] == "project.completion"
        ]
        self.assertEqual([], completion_lamps)
        self.assertNotIn("complete", self.result["checkpoint"]["city_position"].lower())

    def test_unauthorized_override_does_not_change_goal(self):
        goal = next(lamp for lamp in self.result["checkpoint"]["active_lamps"] if lamp["type"] == "GOAL")
        self.assertEqual("Deliver a judge-ready local ZNAK ORIENT vertical slice.", goal["value"])
        self.assertEqual("AUTHORIZED", goal["authority"])

    def test_conflict_preserves_both_claims_and_drives_only_corrective_step(self):
        conflict = self.result["checkpoint"]["conflicts"][0]
        self.assertEqual("DISPUTED", conflict["status"])
        self.assertEqual(2, len(conflict["claims"]))
        self.assertEqual(
            {
                "python -m znak_orient serve --host 127.0.0.1 --port 8765",
                "python app.py --demo",
            },
            {claim["value"] for claim in conflict["claims"]},
        )
        self.assertIn("Record one AUTHORIZED resolution", self.result["checkpoint"]["primary_next_step"]["instruction"])
        self.assertNotIn("python app.py", self.result["checkpoint"]["primary_next_step"]["instruction"])

    def test_material_conclusions_have_resolvable_sources(self):
        source_ids = {source["source_id"] for source in self.result["source_evidence"]}
        checkpoint = self.result["checkpoint"]
        self.assertTrue(set(checkpoint["city_position_source_ids"]).issubset(source_ids))
        self.assertTrue(set(checkpoint["primary_next_step"]["source_ids"]).issubset(source_ids))
        for lamp in checkpoint["active_lamps"]:
            self.assertTrue(lamp["source_ids"])
            self.assertTrue(set(lamp["source_ids"]).issubset(source_ids))
        for conflict in checkpoint["conflicts"]:
            for claim in conflict["claims"]:
                self.assertTrue(set(claim["source_ids"]).issubset(source_ids))
        for unknown in checkpoint["unknowns"]:
            self.assertTrue(set(unknown["source_ids"]).issubset(source_ids))

    def test_recovery_card_is_derived_and_mutation_cannot_write_back(self):
        original_checkpoint = canonical_json_bytes(self.result["checkpoint"])
        self.result["recovery_card"]["city_position"] = "FORGED COMPLETE"
        self.result["recovery_card"]["write_back_allowed"] = True
        fresh = orient(self.package)
        self.assertEqual(original_checkpoint, canonical_json_bytes(fresh["checkpoint"]))
        self.assertFalse(fresh["recovery_card"]["source_of_truth"])
        self.assertFalse(fresh["recovery_card"]["write_back_allowed"])

    def test_exactly_one_next_step_with_machine_condition(self):
        next_step = self.result["checkpoint"]["primary_next_step"]
        self.assertEqual({"type", "subject", "required_authority"}, set(next_step["success_condition"]))
        self.assertFalse(evaluate_success_condition(self.result, next_step["success_condition"]))


class RecoveryAndPolicyTests(unittest.TestCase):
    def test_corrupt_primary_falls_back_and_replays_identically(self):
        package = demo_package()
        valid = copy.deepcopy(package["checkpoints"]["primary"])
        package["checkpoints"]["fallbacks"] = [valid]
        package["checkpoints"]["primary"]["city_position"] = "tampered"
        recovered = orient(package)
        normal = orient(demo_package())
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", recovered["base_checkpoint"]["status"])
        self.assertEqual(normal["checkpoint"], recovered["checkpoint"])
        self.assertTrue(recovered["base_checkpoint"]["rejected_candidates"])

    def test_all_checkpoints_corrupt_fails_closed(self):
        package = demo_package()
        package["checkpoints"]["primary"]["integrity"]["value"] = "0" * 64
        with self.assertRaisesRegex(OrientationError, "no valid checkpoint"):
            orient(package)

    def test_minimum_sufficient_memory_matches_package_with_covered_history(self):
        compact = demo_package()
        full = demo_package()
        for sequence in range(1, 5):
            full["changes"].append(
                {
                    "change_id": f"historical-trace-{sequence}",
                    "object_type": "TRACE",
                    "sequence": sequence,
                    "observed_at": "2026-07-18T10:00:00+02:00",
                    "source_ids": ["src-checkpoint-001"],
                    "text": f"historical detail {sequence}",
                }
            )
        compact_result = orient(compact)
        full_result = orient(full)
        self.assertEqual(compact_result["checkpoint"], full_result["checkpoint"])
        self.assertEqual(compact_result["recovery_card"], full_result["recovery_card"])
        covered = [item for item in full_result["intake"] if item["reason"] == "COVERED_BY_VALID_CHECKPOINT"]
        self.assertEqual(4, len(covered))

    def test_authorized_explicit_supersession_is_update_not_conflict(self):
        package = demo_package()
        conflict_change = next(item for item in package["changes"] if item["change_id"] == "chg-entrypoint-conflict")
        conflict_change["operation"] = "SUPERSEDE"
        conflict_change["supersedes"] = "lamp:decision:demo.entrypoint"
        result = orient(package)
        self.assertEqual([], [item for item in result["checkpoint"]["conflicts"] if item["status"] == "DISPUTED"])
        entrypoint = next(lamp for lamp in result["checkpoint"]["active_lamps"] if lamp["subject"] == "demo.entrypoint")
        self.assertEqual("python app.py --demo", entrypoint["value"])

    def test_authorized_resolution_satisfies_previous_success_condition(self):
        package = demo_package()
        initial = orient(package)
        condition = initial["checkpoint"]["primary_next_step"]["success_condition"]
        package["changes"].append(
            {
                "change_id": "chg-resolve-entrypoint",
                "object_type": "STATE_CHANGE",
                "sequence": 13,
                "observed_at": "2026-07-19T08:25:00+02:00",
                "content_type": "DECISION",
                "operation": "RESOLVE",
                "subject": "demo.entrypoint",
                "value": "python -m znak_orient serve --host 127.0.0.1 --port 8765",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "resolves_conflict_id": "conflict:decision:demo.entrypoint",
                "source_ids": ["src-entrypoint-old", "src-entrypoint-new"],
            }
        )
        resolved = orient(package)
        self.assertTrue(evaluate_success_condition(resolved, condition))
        self.assertEqual("RESOLVED", resolved["checkpoint"]["conflicts"][0]["status"])

    def test_untrusted_self_declared_pass_cannot_promote_fact(self):
        package = demo_package()
        receipt = package["validation_receipts"][0]
        receipt["status"] = "PASS"
        receipt["validator_id"] = "IMPORTED_SELF_DECLARED_VALIDATOR"
        result = orient(package)
        self.assertEqual("UNTRUSTED_VALIDATOR_RECEIPT", intake_by_id(result)["chg-unsupported-success"]["reason"])

    def test_trusted_validator_policy_is_separate_from_decision_authority(self):
        package = demo_package()
        receipt = package["validation_receipts"][0]
        receipt["status"] = "PASS"
        receipt["validator_id"] = "ZNAK_ORIENT_LOCAL_TEST_RUNNER"
        result = orient(package)
        completion = next(lamp for lamp in result["checkpoint"]["active_lamps"] if lamp["subject"] == "project.completion")
        self.assertEqual("VERIFIED", completion["epistemic"])
        self.assertEqual("NOT_APPLICABLE", completion["authority"])

    def test_checkpoint_sealing_detects_tamper(self):
        checkpoint = seal_checkpoint(
            {
                "schema_version": "0.3C",
                "checkpoint_id": "cp-test",
                "created_at": "2026-07-19T08:00:00+02:00",
                "last_sequence": 0,
                "city_position": "Known",
                "city_position_source_ids": ["src"],
                "active_lamps": [],
                "recent_changes": [],
                "conflicts": [],
                "unknowns": [],
                "voltage": "UNKNOWN",
                "primary_next_step": {"action_id": "ask", "source_ids": ["src"]},
                "source_pointers": [],
            }
        )
        self.assertTrue(verify_checkpoint_integrity(checkpoint))
        checkpoint["city_position"] = "tampered"
        self.assertFalse(verify_checkpoint_integrity(checkpoint))


if __name__ == "__main__":
    unittest.main()

