from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from znak_orient.canonical import canonical_json_bytes, seal_checkpoint, verify_checkpoint_integrity
from znak_orient.contracts import validate_source
from znak_orient.engine import OrientationError, evaluate_success_condition, orient


ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = ROOT / "demo" / "evidence-package.json"


def demo_package():
    return json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def intake_by_id(result):
    return {item["change_id"]: item for item in result["intake"]}


def receipt_by_id(package, receipt_id="vr-clean-007"):
    return next(item for item in package["validation_receipts"] if item["receipt_id"] == receipt_id)


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
        self.package["changes"].append(
            {
                "change_id": "chg-nested-decision",
                "object_type": "STATE_CHANGE",
                "sequence": 13,
                "observed_at": "2026-07-19T08:24:00+02:00",
                "content_type": "DECISION",
                "operation": "CREATE",
                "subject": "demo.nested",
                "value": {"command": "python -m znak_orient serve", "options": ["loopback"]},
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-authorized-change"],
            }
        )
        self.result = orient(self.package)
        original_checkpoint = canonical_json_bytes(self.result["checkpoint"])
        self.result["recovery_card"]["city_position"] = "FORGED COMPLETE"
        self.result["recovery_card"]["write_back_allowed"] = True
        nested = next(item for item in self.result["recovery_card"]["decisions"] if item["subject"] == "demo.nested")
        nested["value"]["command"] = "FORGED"
        self.result["recovery_card"]["source_pointers"][0]["locator"] = "forged://pointer"
        self.assertEqual(original_checkpoint, canonical_json_bytes(self.result["checkpoint"]))
        self.assertTrue(verify_checkpoint_integrity(self.result["checkpoint"]))
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

    def test_noise_only_does_not_create_a_checkpoint(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "trace-only",
                "object_type": "TRACE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "source_ids": ["src-checkpoint-001"],
                "text": "Wording-only detail with no semantic state change.",
            }
        ]
        result = orient(package)
        self.assertEqual("cp-old-valid-001", result["checkpoint"]["checkpoint_id"])
        self.assertEqual(4, result["checkpoint"]["last_sequence"])
        self.assertEqual("TRACE_EXPIRED_NO_MEANINGFUL_CHANGE", result["intake"][0]["reason"])

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
        receipt = receipt_by_id(package)
        receipt["status"] = "PASS"
        receipt["checks"] = [{"id": item["id"], "status": "PASS"} for item in receipt["checks"]]
        receipt["summary"] = "Clean checkout passed."
        receipt["validator_id"] = "IMPORTED_SELF_DECLARED_VALIDATOR"
        result = orient(package)
        self.assertEqual("UNTRUSTED_VALIDATOR_RECEIPT", intake_by_id(result)["chg-unsupported-success"]["reason"])

    def test_trusted_validator_policy_is_separate_from_decision_authority(self):
        package = demo_package()
        receipt = receipt_by_id(package)
        receipt["status"] = "PASS"
        receipt["checks"] = [{"id": item["id"], "status": "PASS"} for item in receipt["checks"]]
        receipt["summary"] = "Clean checkout passed."
        receipt["validator_id"] = "ZNAK_ORIENT_LOCAL_TEST_RUNNER"
        result = orient(package)
        completion = next(lamp for lamp in result["checkpoint"]["active_lamps"] if lamp["subject"] == "project.completion")
        self.assertEqual("VERIFIED", completion["epistemic"])
        self.assertEqual("NOT_APPLICABLE", completion["authority"])

    def test_material_unknown_change_is_projected_and_drives_evidence_step(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-critical-unknown",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "UNKNOWN",
                "operation": "CREATE",
                "subject": "release.owner",
                "value": "Release owner is not established.",
                "epistemic": "UNKNOWN",
                "authority": "NOT_APPLICABLE",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-clean-validation"],
            }
        ]
        result = orient(package)
        self.assertEqual("UNKNOWN", result["checkpoint"]["voltage"])
        self.assertEqual("evidence:release.owner", result["checkpoint"]["primary_next_step"]["action_id"])
        self.assertTrue(any(item["subject"] == "release.owner" for item in result["checkpoint"]["unknowns"]))

    def test_material_unknown_receipt_is_projected(self):
        package = demo_package()
        receipt_by_id(package)["status"] = "UNKNOWN"
        receipt_by_id(package)["checks"][0]["status"] = "UNKNOWN"
        package["changes"] = []
        result = orient(package)
        self.assertEqual("UNKNOWN", result["checkpoint"]["voltage"])
        self.assertTrue(any(item["unknown_id"] == "unknown:validation:project.completion" for item in result["checkpoint"]["unknowns"]))

    def test_trusted_pass_resolves_prior_validation_unknown(self):
        initial_package = demo_package()
        receipt_by_id(initial_package)["status"] = "UNKNOWN"
        receipt_by_id(initial_package)["checks"][0]["status"] = "UNKNOWN"
        initial_package["changes"] = []
        initial = orient(initial_package)

        follow_up = demo_package()
        follow_up["as_of"] = "2026-07-19T08:40:00+02:00"
        follow_up["checkpoints"] = {"primary": initial["checkpoint"], "fallbacks": []}
        follow_up["changes"] = []
        receipt = receipt_by_id(follow_up)
        receipt["status"] = "PASS"
        receipt["checked_at"] = "2026-07-19T08:35:00+02:00"
        receipt["summary"] = "Clean checkout passed."
        receipt["checks"] = [{"id": item["id"], "status": "PASS"} for item in receipt["checks"]]
        resolved = orient(follow_up)
        self.assertEqual([], [item for item in resolved["checkpoint"]["unknowns"] if item["subject"] == "project.completion"])
        self.assertEqual("Clean checkout passed.", resolved["checkpoint"]["city_position"])
        self.assertEqual("FLOWING", resolved["checkpoint"]["voltage"])

    def test_material_risk_returns_corrective_mitigation_step(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-data-loss-risk",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "RISK",
                "operation": "CREATE",
                "subject": "storage.data_loss",
                "value": "Unverified backup before migration.",
                "epistemic": "SUPPORTED",
                "authority": "NOT_APPLICABLE",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-clean-validation"],
            }
        ]
        result = orient(package)
        self.assertEqual("WEAK", result["checkpoint"]["voltage"])
        self.assertEqual("mitigate:storage.data_loss", result["checkpoint"]["primary_next_step"]["action_id"])
        self.assertFalse(evaluate_success_condition(result, result["checkpoint"]["primary_next_step"]["success_condition"]))

    def test_cross_subject_conflict_resolution_is_rejected(self):
        package = demo_package()
        package["changes"].append(
            {
                "change_id": "chg-cross-subject-resolution",
                "object_type": "STATE_CHANGE",
                "sequence": 13,
                "observed_at": "2026-07-19T08:25:00+02:00",
                "content_type": "DECISION",
                "operation": "RESOLVE",
                "subject": "different.subject",
                "value": "python app.py --demo",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "resolves_conflict_id": "conflict:decision:demo.entrypoint",
                "source_ids": ["src-entrypoint-new"],
            }
        )
        result = orient(package)
        self.assertEqual("INVALID_CONFLICT_RESOLUTION", intake_by_id(result)["chg-cross-subject-resolution"]["reason"])
        self.assertEqual("DISPUTED", result["checkpoint"]["conflicts"][0]["status"])
        self.assertFalse(any(item["subject"] == "different.subject" for item in result["checkpoint"]["active_lamps"]))

    def test_disputed_input_cannot_become_active_lamp(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-disputed-active",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "DECISION",
                "operation": "CREATE",
                "subject": "demo.disputed",
                "value": "unsafe",
                "epistemic": "DISPUTED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-entrypoint-new"],
            }
        ]
        result = orient(package)
        self.assertEqual("DISPUTED_CANNOT_ACTIVATE", intake_by_id(result)["chg-disputed-active"]["reason"])
        self.assertFalse(any(item["subject"] == "demo.disputed" for item in result["checkpoint"]["active_lamps"]))

    def test_malformed_sealed_primary_uses_valid_fallback(self):
        package = demo_package()
        fallback = copy.deepcopy(package["checkpoints"]["primary"])
        malformed = copy.deepcopy(fallback)
        malformed["active_lamps"] = [{}]
        package["checkpoints"] = {"primary": seal_checkpoint(malformed), "fallbacks": [fallback]}
        result = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", result["base_checkpoint"]["status"])
        self.assertIn("lamp identity", result["base_checkpoint"]["rejected_candidates"][0]["reason"])

    def test_invalid_next_step_shape_cannot_bypass_fallback(self):
        package = demo_package()
        fallback = copy.deepcopy(package["checkpoints"]["primary"])
        malformed = copy.deepcopy(fallback)
        malformed["primary_next_step"]["actions"] = [{"id": "one"}, {"id": "two"}]
        package["checkpoints"] = {"primary": seal_checkpoint(malformed), "fallbacks": [fallback]}
        result = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", result["base_checkpoint"]["status"])

    def test_supersession_requires_exact_active_target(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-bad-supersession",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "DECISION",
                "operation": "SUPERSEDE",
                "subject": "demo.entrypoint",
                "value": "unsafe replacement",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "supersedes": "lamp:decision:wrong-target",
                "source_ids": ["src-entrypoint-new"],
            }
        ]
        result = orient(package)
        self.assertEqual("INVALID_SUPERSESSION_TARGET", result["intake"][0]["reason"])
        entrypoint = next(item for item in result["checkpoint"]["active_lamps"] if item["subject"] == "demo.entrypoint")
        self.assertIn("python -m znak_orient", entrypoint["value"])

    def test_future_source_or_receipt_fails_closed(self):
        future_source = demo_package()
        future_source["sources"][0]["captured_at"] = "2030-01-01T00:00:00+00:00"
        with self.assertRaisesRegex(OrientationError, "future"):
            orient(future_source)

        future_receipt = demo_package()
        receipt_by_id(future_receipt)["checked_at"] = "2030-01-01T00:00:00+00:00"
        with self.assertRaisesRegex(OrientationError, "future"):
            orient(future_receipt)

    def test_receipt_status_must_match_its_checks(self):
        package = demo_package()
        receipt_by_id(package)["status"] = "PASS"
        with self.assertRaisesRegex(OrientationError, "non-PASS check"):
            orient(package)

    def test_verified_fact_retains_receipt_provenance(self):
        package = demo_package()
        receipt = receipt_by_id(package)
        receipt["status"] = "PASS"
        receipt["checks"] = [{"id": item["id"], "status": "PASS"} for item in receipt["checks"]]
        receipt["summary"] = "Clean checkout passed."
        receipt["validator_id"] = "ZNAK_ORIENT_LOCAL_TEST_RUNNER"
        result = orient(package)
        completion = next(lamp for lamp in result["checkpoint"]["active_lamps"] if lamp["subject"] == "project.completion")
        self.assertEqual("vr-clean-007", completion["validation_receipt_id"])
        self.assertEqual({"src-clean-validation", "src-status-chat"}, set(completion["source_ids"]))

    def test_untrusted_pass_cannot_satisfy_success_condition(self):
        result = {
            "checkpoint": {"active_lamps": [], "conflicts": [], "unknowns": []},
            "validation_receipts": [
                {"subject": "project.completion", "status": "PASS", "validator_id": "IMPORTED_SELF_DECLARED_VALIDATOR"}
            ],
        }
        self.assertFalse(evaluate_success_condition(result, {"type": "validation_pass", "subject": "project.completion"}))
        self.assertFalse(evaluate_success_condition(result, {"type": "validation_receipt_retained", "status": "PASS"}))

    def test_rejected_recovery_card_does_not_poison_checkpoint_cursor(self):
        package = demo_package()
        package["changes"] = [
            {
                "change_id": "rc-gap-poison",
                "object_type": "RECOVERY_CARD",
                "sequence": 1000000,
                "observed_at": "2026-07-19T08:23:00+02:00",
                "source_ids": ["src-status-chat"],
                "value": {"write_back_allowed": True},
            }
        ]
        result = orient(package)
        self.assertEqual("RECOVERY_CARD_CONTAMINATION", result["intake"][0]["reason"])
        self.assertEqual(4, result["checkpoint"]["last_sequence"])

    def test_recovery_card_cannot_suppress_valid_change_at_same_sequence(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-valid-same-sequence",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "CONSTRAINT",
                "operation": "CREATE",
                "subject": "demo.safe",
                "value": "LOCAL_ONLY",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-authorized-change"],
            },
            {
                "change_id": "rc-same-sequence",
                "object_type": "RECOVERY_CARD",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "source_ids": ["src-status-chat"],
                "value": {"write_back_allowed": True},
            },
        ]
        result = orient(package)
        intake = intake_by_id(result)
        self.assertEqual("APPLIED", intake["chg-valid-same-sequence"]["status"])
        self.assertEqual("RECOVERY_CARD_CONTAMINATION", intake["rc-same-sequence"]["reason"])
        self.assertTrue(any(item["subject"] == "demo.safe" for item in result["checkpoint"]["active_lamps"]))
        self.assertEqual(5, result["checkpoint"]["last_sequence"])

    def test_tied_reused_event_identity_is_order_independent(self):
        package_a = demo_package()
        package_a["validation_receipts"] = [receipt_by_id(package_a, "vr-core-001")]
        changes = []
        for value in ("A", "B"):
            changes.append(
                {
                    "change_id": "chg-reused",
                    "object_type": "STATE_CHANGE",
                    "sequence": 5,
                    "observed_at": "2026-07-19T08:00:00+02:00",
                    "content_type": "RISK",
                    "operation": "CREATE",
                    "subject": "demo.order",
                    "value": value,
                    "epistemic": "SUPPORTED",
                    "authority": "NOT_APPLICABLE",
                    "material": True,
                    "expected_checkpoint_id": "cp-old-valid-001",
                    "source_ids": ["src-clean-validation"],
                }
            )
        package_a["changes"] = changes
        package_b = copy.deepcopy(package_a)
        package_b["changes"].reverse()
        self.assertEqual(canonical_json_bytes(orient(package_a)), canonical_json_bytes(orient(package_b)))

    def test_corroborating_source_merge_is_retained(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-network-corroboration",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:20:00+02:00",
                "content_type": "CONSTRAINT",
                "operation": "UPDATE",
                "subject": "network.policy",
                "value": "LOCAL_ONLY_NO_EXTERNAL_APIS",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-authorized-change"],
            }
        ]
        result = orient(package)
        lamp = next(item for item in result["checkpoint"]["active_lamps"] if item["subject"] == "network.policy")
        self.assertEqual({"src-pin-001", "src-authorized-change"}, set(lamp["source_ids"]))
        self.assertEqual("CORROBORATING_SOURCE_MERGED", result["intake"][0]["reason"])

    def test_source_free_self_sealed_checkpoint_is_rejected(self):
        package = demo_package()
        package["sources"] = []
        package["validation_receipts"] = []
        package["changes"] = []
        with self.assertRaisesRegex(OrientationError, "no valid checkpoint"):
            orient(package)

    def test_checkpoint_cannot_authorize_goal_from_unauthorized_source(self):
        package = demo_package()
        fallback = copy.deepcopy(package["checkpoints"]["primary"])
        hijacked = copy.deepcopy(fallback)
        goal = next(item for item in hijacked["active_lamps"] if item["type"] == "GOAL")
        goal["value"] = "HIJACKED"
        goal["source_ids"] = ["src-status-chat"]
        hijacked["primary_next_step"]["goal"]["source_ids"] = ["src-status-chat"]
        hijacked["source_pointers"].append(
            {
                key: validate_source(next(item for item in package["sources"] if item["source_id"] == "src-status-chat"))[key]
                for key in ("source_id", "kind", "locator", "captured_at", "authority", "content_sha256")
            }
        )
        package["checkpoints"] = {"primary": seal_checkpoint(hijacked), "fallbacks": [fallback]}
        result = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", result["base_checkpoint"]["status"])
        self.assertIn("untrusted source", result["base_checkpoint"]["rejected_candidates"][0]["reason"])

    def test_checkpoint_without_active_goal_uses_fallback(self):
        package = demo_package()
        fallback = copy.deepcopy(package["checkpoints"]["primary"])
        malformed = copy.deepcopy(fallback)
        malformed["active_lamps"] = [item for item in malformed["active_lamps"] if item["type"] != "GOAL"]
        package["checkpoints"] = {"primary": seal_checkpoint(malformed), "fallbacks": [fallback]}
        result = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", result["base_checkpoint"]["status"])
        self.assertIn("no active goal", result["base_checkpoint"]["rejected_candidates"][0]["reason"])

    def test_checkpoint_non_fact_lamp_cannot_reference_missing_receipt(self):
        package = demo_package()
        fallback = copy.deepcopy(package["checkpoints"]["primary"])
        malformed = copy.deepcopy(fallback)
        decision = next(item for item in malformed["active_lamps"] if item["type"] == "DECISION")
        decision["validation_receipt_id"] = "missing-receipt"
        package["checkpoints"] = {"primary": seal_checkpoint(malformed), "fallbacks": [fallback]}
        result = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", result["base_checkpoint"]["status"])
        self.assertIn("validation receipt is unresolved", result["base_checkpoint"]["rejected_candidates"][0]["reason"])

    def test_checkpoint_pointer_hash_binds_current_source_content(self):
        package = demo_package()
        primary = copy.deepcopy(package["checkpoints"]["primary"])
        pin = next(item for item in package["sources"] if item["source_id"] == "src-pin-001")
        pin["excerpt"] = "Changed source content."
        updated_pin = validate_source(pin)
        fallback = copy.deepcopy(primary)
        pointer = next(item for item in fallback["source_pointers"] if item["source_id"] == "src-pin-001")
        pointer["content_sha256"] = updated_pin["content_sha256"]
        fallback = seal_checkpoint(fallback)
        package["checkpoints"] = {"primary": primary, "fallbacks": [fallback]}
        result = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", result["base_checkpoint"]["status"])
        self.assertIn("hash", result["base_checkpoint"]["rejected_candidates"][0]["reason"])

    def test_contradictory_trusted_receipts_are_order_independent_and_disputed(self):
        package_a = demo_package()
        package_a["changes"] = []
        package_a["validation_receipts"].append(
            {
                "receipt_id": "vr-clean-pass",
                "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                "subject": "project.completion",
                "status": "PASS",
                "checked_at": "2026-07-19T08:15:00+02:00",
                "material": True,
                "summary": "Clean checkout passed.",
                "assertion_sha256": "4dc7bc201c36b6ce654527e82784f9dd66558c8c50078ac65b444cd37ac75837",
                "source_ids": ["src-clean-validation"],
                "checks": [{"id": "clean-checkout", "status": "PASS"}],
            }
        )
        package_b = copy.deepcopy(package_a)
        package_b["validation_receipts"].reverse()
        result_a = orient(package_a)
        result_b = orient(package_b)
        self.assertEqual(canonical_json_bytes(result_a), canonical_json_bytes(result_b))
        self.assertTrue(any(item["classification"] == "CONTRADICTORY_VALIDATION_RECEIPTS" for item in result_a["checkpoint"]["conflicts"]))
        self.assertTrue(any(item["unknown_id"] == "unknown:receipt-conflict:project.completion" for item in result_a["checkpoint"]["unknowns"]))

    def test_pass_receipt_is_bound_to_exact_fact_value(self):
        package = demo_package()
        receipt = receipt_by_id(package)
        receipt["status"] = "PASS"
        receipt["summary"] = "Clean checkout passed."
        receipt["checks"] = [{"id": item["id"], "status": "PASS"} for item in receipt["checks"]]
        change = next(item for item in package["changes"] if item["change_id"] == "chg-unsupported-success")
        change["value"] = {"arbitrary": "different assertion"}
        result = orient(package)
        self.assertEqual("RECEIPT_ASSERTION_MISMATCH", intake_by_id(result)["chg-unsupported-success"]["reason"])

    def test_trusted_fail_receipt_can_invalidate_bound_active_fact(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["validation_receipts"].append(
            {
                "receipt_id": "vr-phase-fail",
                "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                "subject": "project.phase",
                "status": "FAIL",
                "checked_at": "2026-07-19T08:10:00+02:00",
                "material": True,
                "summary": "Core phase evidence was invalidated.",
                "assertion_sha256": "8c3c072f6bc2253c4c50cf64d78838410536beac593f79b45e812ace44c6699b",
                "source_ids": ["src-clean-validation"],
                "checks": [{"id": "core-phase-current", "status": "FAIL"}],
            }
        )
        package["changes"] = [
            {
                "change_id": "chg-invalidate-phase",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:12:00+02:00",
                "content_type": "FACT",
                "operation": "INVALIDATE",
                "subject": "project.phase",
                "value": "CORE_IMPLEMENTED_VALIDATION_PENDING",
                "epistemic": "VERIFIED",
                "authority": "NOT_APPLICABLE",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "validation_receipt_id": "vr-phase-fail",
                "source_ids": ["src-clean-validation"],
            }
        ]
        result = orient(package)
        self.assertEqual("APPLIED", result["intake"][0]["status"])
        self.assertFalse(any(item["type"] == "FACT" and item["subject"] == "project.phase" for item in result["checkpoint"]["active_lamps"]))

    def test_unauthorized_evidence_cannot_remove_material_risk(self):
        initial_package = demo_package()
        initial_package["validation_receipts"] = [receipt_by_id(initial_package, "vr-core-001")]
        initial_package["changes"] = [
            {
                "change_id": "chg-create-risk",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "RISK",
                "operation": "CREATE",
                "subject": "storage.data_loss",
                "value": "Backup is unverified.",
                "epistemic": "SUPPORTED",
                "authority": "NOT_APPLICABLE",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-clean-validation"],
            }
        ]
        initial = orient(initial_package)

        follow_up = demo_package()
        follow_up["as_of"] = "2026-07-19T08:40:00+02:00"
        follow_up["validation_receipts"] = [receipt_by_id(follow_up, "vr-core-001")]
        follow_up["checkpoints"] = {"primary": initial["checkpoint"], "fallbacks": []}
        follow_up["changes"] = [
            {
                "change_id": "chg-remove-risk-untrusted",
                "object_type": "STATE_CHANGE",
                "sequence": 6,
                "observed_at": "2026-07-19T08:35:00+02:00",
                "content_type": "RISK",
                "operation": "DEACTIVATE",
                "subject": "storage.data_loss",
                "value": "Backup is unverified.",
                "epistemic": "SUPPORTED",
                "authority": "UNAUTHORIZED",
                "material": True,
                "expected_checkpoint_id": initial["checkpoint"]["checkpoint_id"],
                "source_ids": ["src-status-chat"],
            }
        ]
        result = orient(follow_up)
        self.assertEqual("UNTRUSTED_EVIDENCE_SOURCE", result["intake"][0]["reason"])
        self.assertTrue(any(item["type"] == "RISK" and item["subject"] == "storage.data_loss" for item in result["checkpoint"]["active_lamps"]))

    def test_non_fact_receipt_reference_and_missing_expected_checkpoint_fail_closed(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-missing-receipt",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "DECISION",
                "operation": "CREATE",
                "subject": "demo.receipt",
                "value": "value",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "validation_receipt_id": "missing-receipt",
                "source_ids": ["src-entrypoint-new"],
            },
            {
                "change_id": "chg-missing-expected",
                "object_type": "STATE_CHANGE",
                "sequence": 6,
                "observed_at": "2026-07-19T08:01:00+02:00",
                "content_type": "GOAL",
                "operation": "SUPERSEDE",
                "subject": "project.primary",
                "value": "Bypass stale-state protection.",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "supersedes": "lamp:goal:project.primary",
                "source_ids": ["src-pin-001"],
            },
        ]
        result = orient(package)
        intake = intake_by_id(result)
        self.assertEqual("UNKNOWN_VALIDATION_RECEIPT", intake["chg-missing-receipt"]["reason"])
        self.assertEqual("MISSING_EXPECTED_CHECKPOINT", intake["chg-missing-expected"]["reason"])

    def test_move_is_explicitly_rejected_until_contract_is_defined(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-move",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "DECISION",
                "operation": "MOVE",
                "subject": "demo.entrypoint",
                "value": "python -m znak_orient serve --host 127.0.0.1 --port 8765",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-entrypoint-old"],
            }
        ]
        result = orient(package)
        self.assertEqual("MOVE_NOT_IMPLEMENTED_IN_MVP", result["intake"][0]["reason"])

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
