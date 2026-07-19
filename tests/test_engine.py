from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from znak_orient.canonical import canonical_json_bytes, seal_checkpoint, sha256_hex, verify_checkpoint_integrity
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


def state_change(
    change_id,
    sequence,
    content_type,
    operation,
    subject,
    value,
    epistemic="SUPPORTED",
    authority="NOT_APPLICABLE",
    material=True,
    expected_checkpoint_id="cp-old-valid-001",
):
    return {
        "change_id": change_id,
        "object_type": "STATE_CHANGE",
        "sequence": sequence,
        "observed_at": f"2026-07-19T08:{sequence:02d}:00+02:00",
        "content_type": content_type,
        "operation": operation,
        "subject": subject,
        "value": value,
        "epistemic": epistemic,
        "authority": authority,
        "material": material,
        "expected_checkpoint_id": expected_checkpoint_id,
        "source_ids": ["src-authorized-change"],
    }


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
        self.assertEqual(
            {"type", "subject", "content_type", "required_authority"},
            set(next_step["success_condition"]),
        )
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

    def test_activate_operation_creates_state_and_records_explicit_impact(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            state_change(
                "chg-activate-risk",
                5,
                "RISK",
                "ACTIVATE",
                "risk.activation-contract",
                "Activation remains locally testable.",
            )
        ]

        result = orient(package)
        applied = intake_by_id(result)["chg-activate-risk"]
        lamp = next(
            item
            for item in result["checkpoint"]["active_lamps"]
            if item["subject"] == "risk.activation-contract"
        )

        self.assertEqual("APPLIED", applied["status"])
        self.assertEqual("STATE_ACTIVATED", applied["impact"])
        self.assertEqual("ACTIVATE", result["checkpoint"]["recent_changes"][0]["operation"])
        self.assertEqual("RISK", lamp["type"])

    def test_impact_is_derived_output_and_remains_closed_to_input(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        change = state_change(
            "chg-forged-input-impact",
            5,
            "RISK",
            "ACTIVATE",
            "risk.forged-impact",
            "Input must not declare its own effect.",
        )
        change["impact"] = "STATE_ACTIVATED"
        package["changes"] = [change]

        with self.assertRaisesRegex(OrientationError, "STATE_CHANGE contains unsupported fields"):
            orient(package)

    def test_connection_content_type_is_preserved_as_an_active_lamp(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            state_change(
                "chg-create-connection",
                5,
                "CONNECTION",
                "CREATE",
                "connection.goal-to-validation",
                {"from": "project.primary", "to": "validation.clean-checkout"},
            )
        ]

        result = orient(package)
        connection = next(
            item
            for item in result["checkpoint"]["active_lamps"]
            if item["subject"] == "connection.goal-to-validation"
        )

        self.assertEqual("CONNECTION", connection["type"])
        self.assertEqual("STATE_ACTIVATED", result["checkpoint"]["recent_changes"][0]["impact"])
        self.assertEqual(
            {"from": "project.primary", "to": "validation.clean-checkout"},
            connection["value"],
        )

    def test_inferred_epistemic_state_remains_inferred_without_becoming_fact(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            state_change(
                "chg-inferred-risk",
                5,
                "RISK",
                "CREATE",
                "risk.inferred-only",
                "The dependency may delay the next validation.",
                epistemic="INFERRED",
            )
        ]

        result = orient(package)
        inferred = next(
            item
            for item in result["checkpoint"]["active_lamps"]
            if item["subject"] == "risk.inferred-only"
        )

        self.assertEqual("RISK", inferred["type"])
        self.assertEqual("INFERRED", inferred["epistemic"])
        self.assertFalse(
            any(
                item["type"] == "FACT" and item["subject"] == inferred["subject"]
                for item in result["checkpoint"]["active_lamps"]
            )
        )

    def test_checkpoint_rejects_inconsistent_state_change_impact(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            state_change(
                "chg-impact-tamper-target",
                5,
                "RISK",
                "ACTIVATE",
                "risk.impact-tamper",
                "Impact must remain structurally bound.",
            )
        ]
        generated = orient(copy.deepcopy(package))["checkpoint"]
        malformed = copy.deepcopy(generated)
        malformed["recent_changes"][0]["impact"] = "STATE_DEACTIVATED"

        package["checkpoints"] = {
            "primary": seal_checkpoint(malformed),
            "fallbacks": [copy.deepcopy(demo_package()["checkpoints"]["primary"])],
        }
        package["changes"] = []
        recovered = orient(package)

        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", recovered["base_checkpoint"]["status"])
        self.assertIn(
            "checkpoint recent change is invalid",
            recovered["base_checkpoint"]["rejected_candidates"][0]["reason"],
        )

    def test_checkpoint_rejects_semantically_complete_deactivation_tamper_with_active_state(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            state_change(
                "chg-projection-tamper-target",
                5,
                "RISK",
                "ACTIVATE",
                "risk.projection-tamper",
                "The risk remains active in canonical state.",
            )
        ]
        generated = orient(copy.deepcopy(package))["checkpoint"]
        malformed = copy.deepcopy(generated)
        retained_change = malformed["recent_changes"][0]
        activated_lamp = copy.deepcopy(retained_change["after"])
        retained_change.update(
            {
                "operation": "DEACTIVATE",
                "reason": "STATE_DEACTIVATED",
                "impact": "STATE_DEACTIVATED",
                "before": activated_lamp,
                "after": None,
            }
        )

        package["checkpoints"] = {
            "primary": seal_checkpoint(malformed),
            "fallbacks": [copy.deepcopy(demo_package()["checkpoints"]["primary"])],
        }
        package["changes"] = []
        recovered = orient(package)

        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", recovered["base_checkpoint"]["status"])
        self.assertIn(
            "does not match final state projection",
            recovered["base_checkpoint"]["rejected_candidates"][0]["reason"],
        )

    def test_checkpoint_rejects_semantically_complete_fact_deactivation_tamper(self):
        package = demo_package()
        receipt = receipt_by_id(package)
        receipt["status"] = "PASS"
        receipt["checks"] = [
            {"id": item["id"], "status": "PASS"} for item in receipt["checks"]
        ]
        receipt["summary"] = "Clean checkout passed."
        receipt["validator_id"] = "ZNAK_ORIENT_LOCAL_TEST_RUNNER"
        generated = orient(copy.deepcopy(package))["checkpoint"]
        malformed = copy.deepcopy(generated)
        retained_change = next(
            item
            for item in malformed["recent_changes"]
            if item["content_type"] == "FACT"
            and item["impact"] == "STATE_ACTIVATED"
        )
        activated_lamp = copy.deepcopy(retained_change["after"])
        retained_change.update(
            {
                "operation": "DEACTIVATE",
                "reason": "STATE_DEACTIVATED",
                "impact": "STATE_DEACTIVATED",
                "before": activated_lamp,
                "after": None,
            }
        )

        package["checkpoints"] = {
            "primary": seal_checkpoint(malformed),
            "fallbacks": [copy.deepcopy(demo_package()["checkpoints"]["primary"])],
        }
        package["changes"] = []
        recovered = orient(package)

        self.assertEqual(
            "FALLBACK_VALID_AFTER_CORRUPTION",
            recovered["base_checkpoint"]["status"],
        )
        self.assertIn(
            "does not match final state projection",
            recovered["base_checkpoint"]["rejected_candidates"][0]["reason"],
        )

    def test_checkpoint_rejects_disconnected_recent_change_transition_chain(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            state_change(
                "chg-chain-create",
                5,
                "RISK",
                "CREATE",
                "risk.transition-chain",
                "Original first state.",
            ),
            state_change(
                "chg-chain-supersede",
                6,
                "RISK",
                "SUPERSEDE",
                "risk.transition-chain",
                "Final state.",
            ),
        ]
        package["changes"][1]["supersedes"] = "lamp:risk:risk.transition-chain"
        generated = orient(copy.deepcopy(package))["checkpoint"]
        malformed = copy.deepcopy(generated)
        malformed["recent_changes"][0]["meaning"] = "Fabricated disconnected state."
        malformed["recent_changes"][0]["after"]["value"] = (
            "Fabricated disconnected state."
        )

        package["checkpoints"] = {
            "primary": seal_checkpoint(malformed),
            "fallbacks": [copy.deepcopy(demo_package()["checkpoints"]["primary"])],
        }
        package["changes"] = []
        recovered = orient(package)

        self.assertEqual(
            "FALLBACK_VALID_AFTER_CORRUPTION",
            recovered["base_checkpoint"]["status"],
        )
        self.assertIn(
            "transition chain is discontinuous",
            recovered["base_checkpoint"]["rejected_candidates"][0]["reason"],
        )

    def test_legacy_03c_checkpoint_is_integrity_checked_then_migrated_and_resealed(self):
        source_package = demo_package()
        source_package["validation_receipts"] = [receipt_by_id(source_package, "vr-core-001")]
        source_package["changes"] = [
            state_change(
                "chg-legacy-risk",
                5,
                "RISK",
                "ACTIVATE",
                "risk.legacy-impact",
                "Legacy history has one unambiguous activation.",
            )
        ]
        current = orient(source_package)["checkpoint"]
        legacy = copy.deepcopy(current)
        legacy["checkpoint_id"] = "cp-legacy-03c-without-impact"
        for change in legacy["recent_changes"]:
            change.pop("impact")
        legacy = seal_checkpoint(legacy)
        original_legacy_bytes = canonical_json_bytes(legacy)

        package = demo_package()
        package["as_of"] = "2026-07-19T08:45:00+02:00"
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["checkpoints"] = {"primary": legacy, "fallbacks": []}
        package["changes"] = []
        migrated = orient(package)
        replayed = orient(package)

        self.assertEqual(
            "PRIMARY_VALID_LEGACY_MIGRATED",
            migrated["base_checkpoint"]["status"],
        )
        self.assertEqual(legacy["checkpoint_id"], migrated["base_checkpoint"]["checkpoint_id"])
        self.assertNotEqual(legacy["checkpoint_id"], migrated["checkpoint"]["checkpoint_id"])
        self.assertEqual(package["as_of"], migrated["checkpoint"]["created_at"])
        self.assertTrue(verify_checkpoint_integrity(migrated["checkpoint"]))
        self.assertEqual(original_legacy_bytes, canonical_json_bytes(legacy))
        self.assertEqual(migrated["checkpoint"], replayed["checkpoint"])
        self.assertEqual(len(legacy["recent_changes"]), len(migrated["checkpoint"]["recent_changes"]))
        for prior, upgraded in zip(
            legacy["recent_changes"], migrated["checkpoint"]["recent_changes"], strict=True
        ):
            self.assertEqual("STATE_ACTIVATED", upgraded["impact"])
            self.assertEqual(prior, {key: value for key, value in upgraded.items() if key != "impact"})

        corrupt_legacy = copy.deepcopy(legacy)
        corrupt_legacy["recent_changes"][0]["meaning"] = "Changed after the legacy seal."
        corrupt_package = copy.deepcopy(package)
        corrupt_package["checkpoints"] = {
            "primary": corrupt_legacy,
            "fallbacks": [copy.deepcopy(demo_package()["checkpoints"]["primary"])],
        }
        recovered = orient(corrupt_package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", recovered["base_checkpoint"]["status"])
        self.assertIn(
            "integrity mismatch",
            recovered["base_checkpoint"]["rejected_candidates"][0]["reason"],
        )

    def test_legacy_fact_history_survives_explicit_later_receipt_suspension(self):
        initial_package = demo_package()
        passing_receipt = receipt_by_id(initial_package)
        passing_receipt["status"] = "PASS"
        passing_receipt["checks"] = [
            {"id": item["id"], "status": "PASS"}
            for item in passing_receipt["checks"]
        ]
        passing_receipt["summary"] = "Clean checkout passed."
        passing_receipt["validator_id"] = "ZNAK_ORIENT_LOCAL_TEST_RUNNER"
        legacy = orient(copy.deepcopy(initial_package))["checkpoint"]
        for change in legacy["recent_changes"]:
            change.pop("impact")
        legacy = seal_checkpoint(legacy)

        follow_up = copy.deepcopy(initial_package)
        follow_up["as_of"] = "2026-07-19T08:45:00+02:00"
        follow_up["checkpoints"] = {"primary": legacy, "fallbacks": []}
        follow_up["changes"] = []
        failing_receipt = copy.deepcopy(passing_receipt)
        failing_receipt.update(
            {
                "receipt_id": "vr-clean-later-fail",
                "status": "FAIL",
                "checked_at": "2026-07-19T08:35:00+02:00",
                "summary": "Later clean-checkout validation failed.",
                "checks": [{"id": "clean-checkout", "status": "FAIL"}],
            }
        )
        follow_up["validation_receipts"].append(failing_receipt)

        migrated = orient(follow_up)

        self.assertEqual(
            "PRIMARY_VALID_LEGACY_MIGRATED",
            migrated["base_checkpoint"]["status"],
        )
        self.assertFalse(
            any(
                lamp["type"] == "FACT"
                and lamp["subject"] == "project.completion"
                for lamp in migrated["checkpoint"]["active_lamps"]
            )
        )
        self.assertTrue(
            any(
                conflict["status"] == "DISPUTED"
                and conflict["subject"] == "validation.project.completion"
                and any(
                    claim["claim_id"] == "lamp:fact:project.completion"
                    for claim in conflict["claims"]
                )
                for conflict in migrated["checkpoint"]["conflicts"]
            )
        )
        self.assertTrue(
            any(
                change["content_type"] == "FACT"
                and change["impact"] == "STATE_ACTIVATED"
                for change in migrated["checkpoint"]["recent_changes"]
            )
        )

        forged = copy.deepcopy(migrated["checkpoint"])
        retained_fact = next(
            change
            for change in forged["recent_changes"]
            if change["content_type"] == "FACT"
            and change["subject"] == "project.completion"
            and change["impact"] == "STATE_ACTIVATED"
        )
        retained_fact["meaning"] = "Fabricated fact without matching proof."
        retained_fact["after"]["value"] = retained_fact["meaning"]
        receipt_conflict = next(
            conflict
            for conflict in forged["conflicts"]
            if conflict["subject"] == "validation.project.completion"
        )
        suspended_claim = next(
            claim
            for claim in receipt_conflict["claims"]
            if claim["claim_id"] == "lamp:fact:project.completion"
        )
        suspended_claim["value"]["fact_value"] = retained_fact["meaning"]

        forged_package = copy.deepcopy(follow_up)
        forged_package["checkpoints"] = {
            "primary": seal_checkpoint(forged),
            "fallbacks": [copy.deepcopy(legacy)],
        }
        recovered = orient(forged_package)

        self.assertEqual(
            "FALLBACK_VALID_AFTER_CORRUPTION_LEGACY_MIGRATED",
            recovered["base_checkpoint"]["status"],
        )
        self.assertIn(
            "does not match final state projection",
            recovered["base_checkpoint"]["rejected_candidates"][0]["reason"],
        )

    def test_legacy_03c_checkpoint_with_ambiguous_impact_uses_valid_fallback(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            state_change(
                "chg-ambiguous-legacy-risk",
                5,
                "RISK",
                "ACTIVATE",
                "risk.ambiguous-legacy",
                "This record will be made structurally ambiguous.",
            )
        ]
        legacy = orient(copy.deepcopy(package))["checkpoint"]
        legacy["recent_changes"][0].pop("impact")
        legacy["recent_changes"][0]["operation"] = "MOVE"
        legacy = seal_checkpoint(legacy)
        fallback = copy.deepcopy(demo_package()["checkpoints"]["primary"])
        package["checkpoints"] = {"primary": legacy, "fallbacks": [fallback]}
        package["changes"] = []

        recovered = orient(package)

        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", recovered["base_checkpoint"]["status"])
        self.assertIn(
            "impact is not unambiguously derivable",
            recovered["base_checkpoint"]["rejected_candidates"][0]["reason"],
        )

    def test_destructive_operations_cannot_be_appended_as_disputed_claims(self):
        initial_package = demo_package()
        initial = orient(initial_package)

        for operation in ("DEACTIVATE", "INVALIDATE", "SUPERSEDE"):
            with self.subTest(operation=operation):
                package = demo_package()
                package["as_of"] = "2026-07-19T08:45:00+02:00"
                package["checkpoints"] = {"primary": initial["checkpoint"], "fallbacks": []}
                change = state_change(
                    f"chg-disputed-{operation.lower()}",
                    20,
                    "DECISION",
                    operation,
                    "demo.entrypoint",
                    "python app.py --demo",
                    epistemic="VERIFIED",
                    authority="AUTHORIZED",
                    expected_checkpoint_id=initial["checkpoint"]["checkpoint_id"],
                )
                change["source_ids"] = ["src-entrypoint-new"]
                if operation == "SUPERSEDE":
                    change["supersedes"] = "lamp:decision:demo.entrypoint"
                package["changes"] = [change]

                result = orient(package)

                self.assertEqual(
                    "DISPUTED_CONFLICT_REQUIRES_RESOLVE",
                    result["intake"][0]["reason"],
                )
                conflict = next(
                    item
                    for item in result["checkpoint"]["conflicts"]
                    if item["subject"] == "demo.entrypoint"
                )
                self.assertEqual("DISPUTED", conflict["status"])
                self.assertFalse(
                    any(
                        lamp["subject"] == "demo.entrypoint"
                        for lamp in result["checkpoint"]["active_lamps"]
                    )
                )

    def test_operation_specific_target_fields_fail_closed(self):
        cases = [
            ("CREATE", "supersedes", "lamp:risk:target-fields", "SUPERSESSION_FIELD_REQUIRES_SUPERSEDE_OPERATION"),
            ("SUPERSEDE", None, None, "SUPERSEDE_REQUIRES_TARGET"),
            ("CREATE", "resolves_conflict_id", "conflict:risk:target-fields", "RESOLUTION_FIELD_REQUIRES_RESOLVE_OPERATION"),
            ("RESOLVE", None, None, "RESOLVE_REQUIRES_CONFLICT_TARGET"),
        ]
        for operation, field, value, expected_reason in cases:
            with self.subTest(operation=operation, field=field):
                package = demo_package()
                package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
                change = state_change(
                    f"chg-target-field-{operation.lower()}-{field or 'missing'}",
                    5,
                    "RISK",
                    operation,
                    "target-fields",
                    "Operation-specific fields are closed.",
                )
                if field is not None:
                    change[field] = value
                package["changes"] = [change]

                result = orient(package)

                self.assertEqual(expected_reason, result["intake"][0]["reason"])

    def test_same_value_supersede_is_still_recorded_as_state_replacement(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        change = state_change(
            "chg-same-value-supersede",
            5,
            "DECISION",
            "SUPERSEDE",
            "demo.entrypoint",
            "python -m znak_orient serve --host 127.0.0.1 --port 8765",
            epistemic="VERIFIED",
            authority="AUTHORIZED",
        )
        change["supersedes"] = "lamp:decision:demo.entrypoint"
        change["source_ids"] = ["src-entrypoint-old"]
        package["changes"] = [change]

        result = orient(package)
        retained = result["checkpoint"]["recent_changes"][0]

        self.assertEqual("APPLIED", result["intake"][0]["status"])
        self.assertEqual("SUPERSEDE", retained["operation"])
        self.assertEqual("STATE_REPLACED", retained["impact"])
        self.assertEqual(retained["before"]["value"], retained["after"]["value"])

    def test_meaningful_history_compaction_preserves_orientation_after_required_cas_rebase(self):
        prefix_changes = [
            state_change(
                "chg-history-risk",
                5,
                "RISK",
                "ACTIVATE",
                "risk.meaningful-history",
                "The release dependency is open.",
            ),
            state_change(
                "chg-history-connection",
                6,
                "CONNECTION",
                "CREATE",
                "connection.history-to-goal",
                {"from": "risk.meaningful-history", "to": "project.primary"},
            ),
        ]
        prefix_package = demo_package()
        prefix_package["as_of"] = "2026-07-19T08:10:00+02:00"
        prefix_package["validation_receipts"] = [receipt_by_id(prefix_package, "vr-core-001")]
        prefix_package["changes"] = copy.deepcopy(prefix_changes)
        compacted_prefix = orient(prefix_package)["checkpoint"]

        full_tail = state_change(
            "chg-history-risk-superseded",
            20,
            "RISK",
            "SUPERSEDE",
            "risk.meaningful-history",
            "The release dependency now has a bounded mitigation.",
        )
        full_tail["supersedes"] = "lamp:risk:risk.meaningful-history"
        compact_tail = copy.deepcopy(full_tail)
        compact_tail["expected_checkpoint_id"] = compacted_prefix["checkpoint_id"]
        self.assertEqual(
            {"expected_checkpoint_id"},
            {
                key
                for key in full_tail
                if full_tail[key] != compact_tail[key]
            },
        )

        full_package = demo_package()
        full_package["validation_receipts"] = [receipt_by_id(full_package, "vr-core-001")]
        full_package["changes"] = copy.deepcopy(prefix_changes) + [full_tail]
        full_result = orient(full_package)

        compact_package = demo_package()
        compact_package["validation_receipts"] = [receipt_by_id(compact_package, "vr-core-001")]
        compact_package["checkpoints"] = {"primary": compacted_prefix, "fallbacks": []}
        compact_package["changes"] = [compact_tail]
        compact_result = orient(compact_package)

        semantic_checkpoint_fields = {
            "last_sequence",
            "city_position",
            "city_position_source_ids",
            "active_lamps",
            "conflicts",
            "unknowns",
            "voltage",
            "primary_next_step",
            "source_pointers",
            "validation_receipt_pointers",
        }
        self.assertEqual(
            {key: full_result["checkpoint"][key] for key in semantic_checkpoint_fields},
            {key: compact_result["checkpoint"][key] for key in semantic_checkpoint_fields},
        )
        self.assertEqual(
            full_result["checkpoint"]["recent_changes"][-1],
            compact_result["checkpoint"]["recent_changes"][-1],
        )
        self.assertEqual("STATE_REPLACED", compact_result["checkpoint"]["recent_changes"][0]["impact"])

    def test_noise_only_does_not_create_a_checkpoint(self):
        baseline_package = demo_package()
        baseline_package["validation_receipts"] = [
            receipt_by_id(baseline_package, "vr-core-001")
        ]
        baseline_package["changes"] = []
        baseline = orient(baseline_package)["checkpoint"]

        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["checkpoints"] = {"primary": baseline, "fallbacks": []}
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
        self.assertEqual(baseline["checkpoint_id"], result["checkpoint"]["checkpoint_id"])
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

    def test_authorized_resolution_selects_pass_over_prior_validation_fail(self):
        initial_package = demo_package()
        receipt_by_id(initial_package)["status"] = "FAIL"
        receipt_by_id(initial_package)["checks"][0]["status"] = "FAIL"
        initial_package["changes"] = []
        initial = orient(initial_package)
        condition = initial["checkpoint"]["primary_next_step"]["success_condition"]

        follow_up = demo_package()
        follow_up["as_of"] = "2026-07-19T08:40:00+02:00"
        follow_up["checkpoints"] = {"primary": initial["checkpoint"], "fallbacks": []}
        receipt_by_id(follow_up)["status"] = "FAIL"
        receipt_by_id(follow_up)["checks"][0]["status"] = "FAIL"
        assertion_sha256 = receipt_by_id(follow_up)["assertion_sha256"]
        selected_claim = {
            "status": "PASS",
            "summary": "Clean checkout passed.",
            "assertion_sha256": assertion_sha256,
        }
        pass_condition = {
            "type": "validation_pass",
            "status": "PASS",
            "subject": "project.completion",
            "checked_after": "2026-07-19T08:00:00+02:00",
            "assertion_sha256": assertion_sha256,
        }
        follow_up["validation_receipts"].extend(
            [
                {
                    "receipt_id": "vr-clean-pass-followup",
                    "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                    "subject": "project.completion",
                    "status": "PASS",
                    "checked_at": "2026-07-19T08:35:00+02:00",
                    "material": True,
                    "summary": "Clean checkout passed.",
                    "assertion_sha256": assertion_sha256,
                    "source_ids": ["src-clean-validation"],
                    "checks": [{"id": "clean-checkout", "status": "PASS"}],
                },
                {
                    "receipt_id": "vr-validation-resolution",
                    "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                    "subject": "validation.project.completion",
                    "status": "PASS",
                    "checked_at": "2026-07-19T08:36:00+02:00",
                    "material": False,
                    "summary": "Receipt conflict resolution was value-bound and retained.",
                    "assertion_sha256": sha256_hex(
                        {"subject": "validation.project.completion", "value": selected_claim}
                    ),
                    "source_ids": ["src-clean-validation"],
                    "checks": [{"id": "resolution-value-bound", "status": "PASS"}],
                },
            ]
        )
        follow_up["changes"] = [
            {
                "change_id": "chg-resolve-validation-receipts",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:37:00+02:00",
                "content_type": "FACT",
                "operation": "RESOLVE",
                "subject": "validation.project.completion",
                "value": selected_claim,
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": initial["checkpoint"]["checkpoint_id"],
                "validation_receipt_id": "vr-validation-resolution",
                "resolves_conflict_id": "conflict:fact:validation.project.completion",
                "source_ids": ["src-authorized-change"],
            }
        ]
        resolved = orient(follow_up)
        self.assertEqual([], [item for item in resolved["checkpoint"]["unknowns"] if item["subject"] == "project.completion"])
        self.assertEqual("FLOWING", resolved["checkpoint"]["voltage"])
        self.assertEqual("Clean checkout passed.", resolved["checkpoint"]["city_position"])
        self.assertTrue(evaluate_success_condition(resolved, condition))
        self.assertTrue(evaluate_success_condition(resolved, pass_condition))
        receipt_conflict = next(
            item
            for item in resolved["checkpoint"]["conflicts"]
            if item["conflict_id"] == "conflict:fact:validation.project.completion"
        )
        self.assertEqual("RESOLVED", receipt_conflict["status"])
        self.assertEqual(
            {"vr-clean-007", "vr-clean-pass-followup"},
            {claim["claim_id"] for claim in receipt_conflict["claims"]},
        )

        contested_proof = copy.deepcopy(follow_up)
        contested_proof["validation_receipts"].append(
            {
                "receipt_id": "vr-validation-resolution-fail",
                "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                "subject": "validation.project.completion",
                "status": "FAIL",
                "checked_at": "2026-07-19T08:36:30+02:00",
                "material": True,
                "summary": "Receipt conflict resolution proof failed.",
                "assertion_sha256": sha256_hex(
                    {"subject": "validation.project.completion", "value": selected_claim}
                ),
                "source_ids": ["src-clean-validation"],
                "checks": [{"id": "resolution-value-bound", "status": "FAIL"}],
            }
        )
        contested_result = orient(contested_proof)
        contested_intake = intake_by_id(contested_result)
        self.assertEqual("REJECTED", contested_intake["chg-resolve-validation-receipts"]["status"])
        self.assertEqual(
            "RECEIPT_CONFLICT_BLOCKS_FACT",
            contested_intake["chg-resolve-validation-receipts"]["reason"],
        )

        resolved_proof_to_fail = copy.deepcopy(contested_proof)
        proof_fail_claim = {
            "status": "FAIL",
            "summary": "Receipt conflict resolution proof failed.",
            "assertion_sha256": sha256_hex(
                {"subject": "validation.project.completion", "value": selected_claim}
            ),
        }
        resolved_proof_to_fail["validation_receipts"].append(
            {
                "receipt_id": "vr-proof-resolution-authority",
                "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                "subject": "validation.validation.project.completion",
                "status": "PASS",
                "checked_at": "2026-07-19T08:36:35+02:00",
                "material": False,
                "summary": "The proof-receipt dispute was resolved to the retained FAIL claim.",
                "assertion_sha256": sha256_hex(
                    {
                        "subject": "validation.validation.project.completion",
                        "value": proof_fail_claim,
                    }
                ),
                "source_ids": ["src-clean-validation"],
                "checks": [{"id": "proof-resolution-value-bound", "status": "PASS"}],
            }
        )
        resolved_proof_to_fail["changes"][0]["sequence"] = 6
        resolved_proof_to_fail["changes"].insert(
            0,
            {
                "change_id": "chg-resolve-proof-to-fail",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:36:45+02:00",
                "content_type": "FACT",
                "operation": "RESOLVE",
                "subject": "validation.validation.project.completion",
                "value": proof_fail_claim,
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": initial["checkpoint"]["checkpoint_id"],
                "validation_receipt_id": "vr-proof-resolution-authority",
                "resolves_conflict_id": "conflict:fact:validation.validation.project.completion",
                "source_ids": ["src-authorized-change"],
            },
        )
        proof_fail_result = orient(resolved_proof_to_fail)
        proof_fail_intake = intake_by_id(proof_fail_result)
        self.assertEqual("APPLIED", proof_fail_intake["chg-resolve-proof-to-fail"]["status"])
        self.assertEqual("REJECTED", proof_fail_intake["chg-resolve-validation-receipts"]["status"])
        self.assertEqual(
            "RECEIPT_RESOLUTION_DOES_NOT_SELECT_PROOF",
            proof_fail_intake["chg-resolve-validation-receipts"]["reason"],
        )

        replay = copy.deepcopy(follow_up)
        replay["as_of"] = "2026-07-19T08:45:00+02:00"
        replay["checkpoints"] = {"primary": resolved["checkpoint"], "fallbacks": []}
        replay["changes"] = []
        replayed = orient(replay)
        replayed_conflict = next(
            item
            for item in replayed["checkpoint"]["conflicts"]
            if item["conflict_id"] == "conflict:fact:validation.project.completion"
        )
        self.assertEqual("RESOLVED", replayed_conflict["status"])
        self.assertEqual("PRIMARY_VALID", replayed["base_checkpoint"]["status"])

        corroborating = copy.deepcopy(replay)
        corroborating["validation_receipts"].append(
            {
                "receipt_id": "vr-later-corroborating-pass",
                "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                "subject": "project.completion",
                "status": "PASS",
                "checked_at": "2026-07-19T08:42:00+02:00",
                "material": True,
                "summary": "Clean checkout passed.",
                "assertion_sha256": assertion_sha256,
                "source_ids": ["src-clean-validation"],
                "checks": [{"id": "later-corroboration", "status": "PASS"}],
            }
        )
        corroborated_result = orient(corroborating)
        corroborated_conflict = next(
            item
            for item in corroborated_result["checkpoint"]["conflicts"]
            if item["conflict_id"] == "conflict:fact:validation.project.completion"
        )
        self.assertEqual("RESOLVED", corroborated_conflict["status"])
        self.assertEqual("FLOWING", corroborated_result["checkpoint"]["voltage"])
        self.assertEqual("Clean checkout passed.", corroborated_result["checkpoint"]["city_position"])

        reopened = copy.deepcopy(corroborating)
        reopened["as_of"] = "2026-07-19T08:55:00+02:00"
        reopened["checkpoints"] = {"primary": corroborated_result["checkpoint"], "fallbacks": []}
        reopened["changes"] = []
        reopened["validation_receipts"].append(
            {
                "receipt_id": "vr-later-conflicting-fail",
                "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                "subject": "project.completion",
                "status": "FAIL",
                "checked_at": "2026-07-19T08:50:00+02:00",
                "material": True,
                "summary": "A later retained validation failed.",
                "assertion_sha256": assertion_sha256,
                "source_ids": ["src-clean-validation"],
                "checks": [{"id": "later-validation", "status": "FAIL"}],
            }
        )
        reopened_result = orient(reopened)
        reopened_conflict = next(
            item
            for item in reopened_result["checkpoint"]["conflicts"]
            if item["conflict_id"] == "conflict:fact:validation.project.completion"
        )
        self.assertEqual("DISPUTED", reopened_conflict["status"])
        self.assertEqual(4, len(reopened_conflict["claims"]))
        self.assertFalse(evaluate_success_condition(reopened_result, condition))
        self.assertFalse(evaluate_success_condition(reopened_result, pass_condition))
        self.assertFalse(
            any(
                lamp["type"] == "FACT" and lamp["subject"] == "validation.project.completion"
                for lamp in reopened_result["checkpoint"]["active_lamps"]
            )
        )

    def test_receipt_id_cannot_be_silently_overwritten_across_checkpoints(self):
        initial_package = demo_package()
        original = receipt_by_id(initial_package)
        original["status"] = "UNKNOWN"
        original["checks"][0]["status"] = "UNKNOWN"
        initial_package["changes"] = []
        initial = orient(initial_package)

        follow_up = demo_package()
        follow_up["as_of"] = "2026-07-19T08:40:00+02:00"
        follow_up["checkpoints"] = {"primary": initial["checkpoint"], "fallbacks": []}
        follow_up["changes"] = []
        reused = receipt_by_id(follow_up)
        reused["status"] = "PASS"
        reused["checked_at"] = "2026-07-19T08:35:00+02:00"
        reused["summary"] = "Clean checkout passed."
        reused["checks"] = [{"id": "clean-checkout", "status": "PASS"}]

        with self.assertRaisesRegex(OrientationError, "RECEIPT-ID-REUSE"):
            orient(follow_up)

    def test_receipt_ledger_cannot_be_deleted_to_rollback_identity_history(self):
        original_package = demo_package()
        latest = orient(copy.deepcopy(original_package))["checkpoint"]
        ledger_deleted = copy.deepcopy(latest)
        ledger_deleted.pop("validation_receipt_pointers")
        ledger_deleted = seal_checkpoint(ledger_deleted)

        replay = demo_package()
        replay["checkpoints"] = {
            "primary": ledger_deleted,
            "fallbacks": [copy.deepcopy(original_package["checkpoints"]["primary"])],
        }
        replay["changes"] = []
        receipt_by_id(replay)["summary"] = "Mutated meaning under a historical receipt ID."
        with self.assertRaisesRegex(OrientationError, "RECEIPT-LINEAGE-UNKNOWN"):
            orient(replay)

    def test_corrupt_newer_checkpoint_cannot_rollback_receipt_identity_history(self):
        original_package = demo_package()
        latest = orient(copy.deepcopy(original_package))["checkpoint"]
        latest["integrity"]["value"] = "0" * 64

        replay = demo_package()
        replay["checkpoints"] = {
            "primary": latest,
            "fallbacks": [copy.deepcopy(original_package["checkpoints"]["primary"])],
        }
        replay["changes"] = []
        receipt_by_id(replay)["summary"] = "Mutated meaning after a corrupt primary checkpoint."
        with self.assertRaisesRegex(OrientationError, "RECEIPT-ID-REUSE"):
            orient(replay)

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
        self.assertIn("lamp", result["base_checkpoint"]["rejected_candidates"][0]["reason"])

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
        self.assertIn("exactly one active goal", result["base_checkpoint"]["rejected_candidates"][0]["reason"])

    def test_checkpoint_non_fact_lamp_cannot_reference_missing_receipt(self):
        package = demo_package()
        fallback = copy.deepcopy(package["checkpoints"]["primary"])
        malformed = copy.deepcopy(fallback)
        decision = next(item for item in malformed["active_lamps"] if item["type"] == "DECISION")
        decision["validation_receipt_id"] = "missing-receipt"
        package["checkpoints"] = {"primary": seal_checkpoint(malformed), "fallbacks": [fallback]}
        result = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", result["base_checkpoint"]["status"])
        self.assertIn("non-FACT", result["base_checkpoint"]["rejected_candidates"][0]["reason"])

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

    def test_single_tail_receipt_merges_with_preserved_conflict_without_full_history(self):
        initial_package = demo_package()
        initial_package["changes"] = []
        failed = receipt_by_id(initial_package)
        failed["material"] = False
        initial_package["validation_receipts"].append(
            {
                "receipt_id": "vr-pass-old-nonmaterial",
                "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                "subject": "project.completion",
                "status": "PASS",
                "checked_at": "2026-07-19T08:15:00+02:00",
                "material": False,
                "summary": "An earlier non-material validation passed.",
                "assertion_sha256": failed["assertion_sha256"],
                "source_ids": ["src-clean-validation"],
                "checks": [{"id": "nonmaterial-pass", "status": "PASS"}],
            }
        )
        initial = orient(initial_package)
        initial_conflict = next(
            item
            for item in initial["checkpoint"]["conflicts"]
            if item["conflict_id"] == "conflict:fact:validation.project.completion"
        )
        self.assertFalse(initial_conflict["material"])
        self.assertEqual("FLOWING", initial["checkpoint"]["voltage"])

        follow_up = demo_package()
        follow_up["as_of"] = "2026-07-19T08:50:00+02:00"
        follow_up["checkpoints"] = {"primary": initial["checkpoint"], "fallbacks": []}
        follow_up["changes"] = []
        core_receipt = receipt_by_id(follow_up, "vr-core-001")
        follow_up["validation_receipts"] = [
            core_receipt,
            {
                "receipt_id": "vr-new-material-pass",
                "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                "subject": "project.completion",
                "status": "PASS",
                "checked_at": "2026-07-19T08:40:00+02:00",
                "material": True,
                "summary": "A new material claim differs from both preserved sides.",
                "assertion_sha256": failed["assertion_sha256"],
                "source_ids": ["src-clean-validation"],
                "checks": [{"id": "material-tail-pass", "status": "PASS"}],
            },
        ]
        result = orient(follow_up)
        conflict = next(
            item
            for item in result["checkpoint"]["conflicts"]
            if item["conflict_id"] == "conflict:fact:validation.project.completion"
        )
        self.assertTrue(conflict["material"])
        self.assertEqual(3, len(conflict["claims"]))
        self.assertIn("vr-new-material-pass", {claim["claim_id"] for claim in conflict["claims"]})
        self.assertEqual("BLOCKED", result["checkpoint"]["voltage"])
        self.assertTrue(
            any(
                item["unknown_id"] == "unknown:receipt-conflict:project.completion"
                and item["critical"]
                for item in result["checkpoint"]["unknowns"]
            )
        )

    def test_same_assertion_with_incompatible_summaries_is_disputed(self):
        package = demo_package()
        package["changes"] = []
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        shared = {
            "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
            "subject": "project.completion",
            "status": "PASS",
            "checked_at": "2026-07-19T08:15:00+02:00",
            "material": True,
            "assertion_sha256": "4dc7bc201c36b6ce654527e82784f9dd66558c8c50078ac65b444cd37ac75837",
            "source_ids": ["src-clean-validation"],
            "checks": [{"id": "clean-checkout", "status": "PASS"}],
        }
        package["validation_receipts"].extend(
            [
                {**shared, "receipt_id": "vr-summary-a", "summary": "Project is complete and published."},
                {**shared, "receipt_id": "vr-summary-b", "summary": "Project is locally complete but unpublished."},
            ]
        )

        result = orient(package)
        self.assertEqual(
            "Current position is UNKNOWN because trusted validation receipts for project.completion disagree.",
            result["checkpoint"]["city_position"],
        )
        self.assertTrue(any(item["subject"] == "validation.project.completion" for item in result["checkpoint"]["conflicts"]))
        self.assertTrue(any(item["unknown_id"] == "unknown:receipt-conflict:project.completion" for item in result["checkpoint"]["unknowns"]))
        self.assertEqual("PASS", result["run_receipt"]["status"])

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
        self.assertEqual("REJECTED", result["intake"][0]["status"])
        self.assertEqual("RECEIPT_CONFLICT_BLOCKS_FACT", result["intake"][0]["reason"])
        self.assertFalse(any(item["type"] == "FACT" and item["subject"] == "project.phase" for item in result["checkpoint"]["active_lamps"]))
        self.assertTrue(
            any(
                item["conflict_id"] == "conflict:fact:validation.project.phase"
                and item["status"] == "DISPUTED"
                for item in result["checkpoint"]["conflicts"]
            )
        )

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

    def test_non_material_goal_conflict_never_flows_without_an_active_goal(self):
        for operation in ("CREATE", "UPDATE"):
            with self.subTest(operation=operation):
                package = demo_package()
                package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
                primary = package["checkpoints"]["primary"]
                goal = next(item for item in primary["active_lamps"] if item["type"] == "GOAL")
                goal["material"] = False
                package["checkpoints"]["primary"] = seal_checkpoint(primary)
                package["changes"] = [
                    {
                        "change_id": f"chg-non-material-goal-{operation.lower()}",
                        "object_type": "STATE_CHANGE",
                        "sequence": 5,
                        "observed_at": "2026-07-19T08:00:00+02:00",
                        "content_type": "GOAL",
                        "operation": operation,
                        "subject": "project.primary",
                        "value": "Replace the active goal without material status.",
                        "epistemic": "VERIFIED",
                        "authority": "AUTHORIZED",
                        "material": False,
                        "expected_checkpoint_id": "cp-old-valid-001",
                        "source_ids": ["src-pin-001"],
                    }
                ]

                try:
                    result = orient(package)
                except OrientationError:
                    # Rejecting the non-material goal policy at the package boundary is fail-closed.
                    continue

                disposition = result["intake"][0]
                active_goals = [item for item in result["checkpoint"]["active_lamps"] if item["type"] == "GOAL"]
                disputed_goal = any(
                    item["type"] == "GOAL" and item["status"] == "DISPUTED"
                    for item in result["checkpoint"]["conflicts"]
                )
                safely_rejected = disposition["status"] == "REJECTED" and bool(active_goals)
                safely_blocked = disputed_goal and result["checkpoint"]["voltage"] == "BLOCKED"
                self.assertTrue(safely_rejected or safely_blocked)
                self.assertFalse(result["checkpoint"]["voltage"] == "FLOWING" and not active_goals)

    def test_checkpoint_cannot_keep_active_lamp_for_same_disputed_subject(self):
        package = demo_package()
        fallback = copy.deepcopy(package["checkpoints"]["primary"])
        malformed = copy.deepcopy(orient(package)["checkpoint"])
        active_entrypoint = next(
            item for item in fallback["active_lamps"]
            if item["type"] == "DECISION" and item["subject"] == "demo.entrypoint"
        )
        malformed["active_lamps"].append(active_entrypoint)
        package["checkpoints"] = {"primary": seal_checkpoint(malformed), "fallbacks": [fallback]}
        package["changes"] = []

        result = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", result["base_checkpoint"]["status"])
        self.assertTrue(result["base_checkpoint"]["rejected_candidates"])

    def test_goal_validation_requires_new_pass_for_exact_goal_subject(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-goal-validation-boundary",
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
        condition = result["checkpoint"]["primary_next_step"]["success_condition"]
        self.assertEqual(
            {"type", "status", "subject", "checked_after", "assertion_sha256"},
            set(condition),
        )
        self.assertEqual("validation_receipt_retained", condition["type"])
        self.assertEqual("PASS", condition["status"])
        self.assertEqual("project.primary", condition["subject"])
        self.assertEqual(package["as_of"], condition["checked_after"])
        goal = next(item for item in result["checkpoint"]["active_lamps"] if item["type"] == "GOAL")
        self.assertEqual(
            "7cecb593d92d68682f26ae66e6e9ce41f90c7a4d65093200b0736f2d28afb7f8",
            condition["assertion_sha256"],
        )
        self.assertEqual(goal["subject"], condition["subject"])
        self.assertFalse(evaluate_success_condition(result, condition))
        later = copy.deepcopy(result)
        later["validation_receipts"].append(
            {
                "receipt_id": "vr-goal-wrong-assertion",
                "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                "subject": "project.primary",
                "status": "PASS",
                "checked_at": "2026-07-19T08:31:00+02:00",
                "material": True,
                "summary": "A different goal assertion passed.",
                "assertion_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "source_ids": ["src-clean-validation"],
                "checks": [{"id": "goal-assertion", "status": "PASS"}],
            }
        )
        self.assertFalse(evaluate_success_condition(later, condition))
        later["validation_receipts"][-1]["assertion_sha256"] = condition["assertion_sha256"]
        self.assertTrue(evaluate_success_condition(later, condition))

    def test_checkpoint_and_tail_both_enforce_exactly_one_active_goal(self):
        package = demo_package()
        fallback = copy.deepcopy(package["checkpoints"]["primary"])
        malformed = copy.deepcopy(fallback)
        malformed["active_lamps"].append(
            {
                "lamp_id": "lamp:goal:project.secondary",
                "type": "GOAL",
                "subject": "project.secondary",
                "value": "Competing second active goal.",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "source_ids": ["src-pin-001"],
                "updated_at": "2026-07-18T18:00:00+02:00",
                "material": True,
            }
        )
        package["checkpoints"] = {"primary": seal_checkpoint(malformed), "fallbacks": [fallback]}
        package["changes"] = []
        recovered = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", recovered["base_checkpoint"]["status"])

        tail_package = demo_package()
        tail_package["validation_receipts"] = [receipt_by_id(tail_package, "vr-core-001")]
        tail_package["changes"] = [
            {
                "change_id": "chg-create-second-goal",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "GOAL",
                "operation": "CREATE",
                "subject": "project.secondary",
                "value": "Competing second active goal.",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-pin-001"],
            }
        ]
        rejected = orient(tail_package)
        self.assertEqual("REJECTED", rejected["intake"][0]["status"])
        self.assertEqual(1, len([item for item in rejected["checkpoint"]["active_lamps"] if item["type"] == "GOAL"]))

    def test_resolved_conflict_reopened_later_retains_resolution_history(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-open-entrypoint-once",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:05:00+02:00",
                "content_type": "DECISION",
                "operation": "UPDATE",
                "subject": "demo.entrypoint",
                "value": "python app.py --demo",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-entrypoint-new"],
            },
            {
                "change_id": "chg-resolve-entrypoint-once",
                "object_type": "STATE_CHANGE",
                "sequence": 6,
                "observed_at": "2026-07-19T08:15:00+02:00",
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
            },
            {
                "change_id": "chg-reopen-entrypoint",
                "object_type": "STATE_CHANGE",
                "sequence": 7,
                "observed_at": "2026-07-19T08:21:00+02:00",
                "content_type": "DECISION",
                "operation": "UPDATE",
                "subject": "demo.entrypoint",
                "value": "python -m znak_orient serve --safe-mode",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-authorized-change"],
            },
        ]

        result = orient(package)
        conflict = next(
            item for item in result["checkpoint"]["conflicts"]
            if item["conflict_id"] == "conflict:decision:demo.entrypoint"
        )
        self.assertEqual("DISPUTED", conflict["status"])
        self.assertIn("chg-resolve-entrypoint-once", json.dumps(conflict, sort_keys=True))
        self.assertIn("python -m znak_orient serve --safe-mode", [claim["value"] for claim in conflict["claims"]])

    def test_non_material_trusted_fail_does_not_block_goal_voltage(self):
        package = demo_package()
        package["validation_receipts"] = [
            receipt_by_id(package, "vr-core-001"),
            {
                "receipt_id": "vr-optional-fail",
                "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                "subject": "project.optional-check",
                "status": "FAIL",
                "checked_at": "2026-07-19T08:11:00+02:00",
                "material": False,
                "summary": "An optional diagnostic failed.",
                "assertion_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "source_ids": ["src-clean-validation"],
                "checks": [{"id": "optional-diagnostic", "status": "FAIL"}],
            },
        ]
        package["changes"] = []

        result = orient(package)
        self.assertEqual("FLOWING", result["checkpoint"]["voltage"])
        self.assertEqual("GOAL_VALIDATION", result["checkpoint"]["primary_next_step"]["policy_class"])
        self.assertFalse(any(item["subject"] == "project.optional-check" for item in result["checkpoint"]["unknowns"]))

    def test_city_position_cannot_be_driven_by_unauthorized_source(self):
        package = demo_package()
        fallback = copy.deepcopy(package["checkpoints"]["primary"])
        malformed = copy.deepcopy(fallback)
        malformed["city_position"] = "Project complete and externally published."
        malformed["city_position_source_ids"] = ["src-untrusted-note"]
        source = validate_source(next(item for item in package["sources"] if item["source_id"] == "src-untrusted-note"))
        malformed["source_pointers"].append(
            {
                "source_id": source["source_id"],
                "kind": source["kind"],
                "locator": source["locator"],
                "captured_at": source["captured_at"],
                "authority": source["authority"],
                "content_sha256": source["content_sha256"],
            }
        )
        package["checkpoints"] = {"primary": seal_checkpoint(malformed), "fallbacks": [fallback]}
        package["changes"] = []

        result = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", result["base_checkpoint"]["status"])
        self.assertIn("trusted checkpoint or receipt provenance", result["base_checkpoint"]["rejected_candidates"][0]["reason"])

    def test_contradictory_material_receipts_do_not_select_one_side_as_position(self):
        package = demo_package()
        package["changes"] = []
        package["validation_receipts"].append(
            {
                "receipt_id": "vr-clean-pass-position",
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

        result = orient(package)
        self.assertEqual(
            "Current position is UNKNOWN because trusted validation receipts for project.completion disagree.",
            result["checkpoint"]["city_position"],
        )
        self.assertTrue(any(item["subject"] == "validation.project.completion" for item in result["checkpoint"]["conflicts"]))
        self.assertTrue(any(item["unknown_id"] == "unknown:receipt-conflict:project.completion" for item in result["checkpoint"]["unknowns"]))

    def test_machine_constraint_can_forbid_selected_policy_class(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-forbid-goal-validation",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "CONSTRAINT",
                "operation": "CREATE",
                "subject": "policy.forbidden-classes",
                "value": {"forbidden_policy_classes": ["GOAL_VALIDATION"]},
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-pin-001"],
            }
        ]

        result = orient(package)
        step = result["checkpoint"]["primary_next_step"]
        self.assertEqual("BROKEN", result["checkpoint"]["voltage"])
        self.assertEqual("CORRECTIVE_CONSTRAINT_RESOLUTION", step["policy_class"])
        self.assertEqual("constraint_policy_allows", step["success_condition"]["type"])
        self.assertFalse(evaluate_success_condition(result, step["success_condition"]))
        constraint = next(item for item in step["constraints"] if item["subject"] == "policy.forbidden-classes")
        self.assertEqual({"forbidden_policy_classes": ["GOAL_VALIDATION"]}, constraint["value"])

    def test_constraint_correction_preserves_contested_goal_context(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-forbid-conflict-resolution",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "CONSTRAINT",
                "operation": "CREATE",
                "subject": "policy.conflict-resolution",
                "value": {"forbidden_policy_classes": ["CORRECTIVE_CONFLICT_RESOLUTION"]},
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-pin-001"],
            },
            {
                "change_id": "chg-contest-primary-goal",
                "object_type": "STATE_CHANGE",
                "sequence": 6,
                "observed_at": "2026-07-19T08:01:00+02:00",
                "content_type": "GOAL",
                "operation": "UPDATE",
                "subject": "project.primary",
                "value": "A competing primary goal.",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-pin-001"],
            },
        ]

        result = orient(package)
        self.assertEqual("BROKEN", result["checkpoint"]["voltage"])
        self.assertEqual("CORRECTIVE_CONSTRAINT_RESOLUTION", result["checkpoint"]["primary_next_step"]["policy_class"])
        self.assertEqual("project.primary", result["checkpoint"]["primary_next_step"]["goal"]["subject"])
        self.assertEqual("PASS", result["run_receipt"]["status"])

    def test_constraint_cannot_forbid_the_only_meta_correction_policy(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-self-locking-constraint",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "CONSTRAINT",
                "operation": "CREATE",
                "subject": "policy.self-locking",
                "value": {
                    "forbidden_policy_classes": [
                        "GOAL_VALIDATION",
                        "CORRECTIVE_CONSTRAINT_RESOLUTION",
                    ]
                },
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-pin-001"],
            }
        ]

        result = orient(package)
        self.assertEqual("REJECTED", result["intake"][0]["status"])
        self.assertEqual("UNSUPPORTED_CONSTRAINT_POLICY", result["intake"][0]["reason"])
        self.assertFalse(any(item["subject"] == "policy.self-locking" for item in result["checkpoint"]["active_lamps"]))

    def test_historical_conflict_claim_id_reuse_is_rejected_without_invalid_output(self):
        initial = orient(demo_package())
        package = demo_package()
        package["as_of"] = "2026-07-19T08:45:00+02:00"
        package["checkpoints"] = {"primary": initial["checkpoint"], "fallbacks": []}
        package["changes"] = [
            {
                "change_id": "chg-entrypoint-conflict",
                "object_type": "STATE_CHANGE",
                "sequence": initial["checkpoint"]["last_sequence"] + 1,
                "observed_at": "2026-07-19T08:40:00+02:00",
                "content_type": "DECISION",
                "operation": "UPDATE",
                "subject": "demo.entrypoint",
                "value": "python -m znak_orient serve --another-mode",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": initial["checkpoint"]["checkpoint_id"],
                "source_ids": ["src-authorized-change"],
            }
        ]

        result = orient(package)
        self.assertEqual("REJECTED", result["intake"][0]["status"])
        self.assertEqual("HISTORICAL_ID_REUSE", result["intake"][0]["reason"])
        self.assertEqual("PASS", result["run_receipt"]["status"])
        claim_ids = [
            claim["claim_id"]
            for conflict in result["checkpoint"]["conflicts"]
            for claim in conflict["claims"]
        ]
        self.assertEqual(len(claim_ids), len(set(claim_ids)))

    def test_active_lamp_id_cannot_be_reused_as_conflicting_change_id(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "lamp:decision:demo.entrypoint",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "DECISION",
                "operation": "UPDATE",
                "subject": "demo.entrypoint",
                "value": "python app.py --demo",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-authorized-change"],
            }
        ]

        result = orient(package)
        self.assertEqual("REJECTED", result["intake"][0]["status"])
        self.assertEqual("HISTORICAL_ID_REUSE", result["intake"][0]["reason"])
        self.assertEqual("PASS", result["run_receipt"]["status"])

    def test_latest_valid_checkpoint_is_selected_across_fallbacks(self):
        package = demo_package()
        newer = orient(copy.deepcopy(package))["checkpoint"]
        package["checkpoints"] = {
            "primary": package["checkpoints"]["primary"],
            "fallbacks": [newer],
        }
        package["changes"] = []

        result = orient(package)
        self.assertEqual("LATEST_VALID_FALLBACK_SELECTED", result["base_checkpoint"]["status"])
        self.assertEqual(newer["checkpoint_id"], result["base_checkpoint"]["checkpoint_id"])

    def test_latest_checkpoint_tie_uses_semantic_cursor_before_primary_label(self):
        def constraint_change(change_id, sequence, subject):
            return {
                "change_id": change_id,
                "object_type": "STATE_CHANGE",
                "sequence": sequence,
                "observed_at": f"2026-07-19T08:0{sequence}:00+02:00",
                "content_type": "CONSTRAINT",
                "operation": "CREATE",
                "subject": subject,
                "value": "LOCAL_ONLY",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-authorized-change"],
            }

        primary_package = demo_package()
        primary_package["validation_receipts"] = [receipt_by_id(primary_package, "vr-core-001")]
        primary_package["changes"] = [constraint_change("chg-seq-five", 5, "policy.seq-five")]
        primary = orient(primary_package)["checkpoint"]

        fallback_package = demo_package()
        fallback_package["validation_receipts"] = [receipt_by_id(fallback_package, "vr-core-001")]
        fallback_package["changes"] = [
            constraint_change("chg-seq-five", 5, "policy.seq-five"),
            constraint_change("chg-seq-six", 6, "policy.seq-six"),
        ]
        fallback = orient(fallback_package)["checkpoint"]
        self.assertEqual(primary["created_at"], fallback["created_at"])
        self.assertGreater(fallback["last_sequence"], primary["last_sequence"])

        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["checkpoints"] = {"primary": primary, "fallbacks": [fallback]}
        package["changes"] = []
        result = orient(package)
        self.assertEqual(fallback["checkpoint_id"], result["base_checkpoint"]["checkpoint_id"])
        self.assertEqual("LATEST_VALID_FALLBACK_SELECTED", result["base_checkpoint"]["status"])

    def test_checkpoint_recent_changes_cannot_exceed_cursor_or_creation_time(self):
        package = demo_package()
        fallback = copy.deepcopy(package["checkpoints"]["primary"])
        malformed = copy.deepcopy(fallback)
        malformed["recent_changes"] = [
            {
                "change_id": "chg-impossible-history",
                "sequence": malformed["last_sequence"] + 1,
                "status": "APPLIED",
                "reason": "Impossible retained history.",
                "source_ids": ["src-pin-001"],
                "observed_at": "2030-01-01T00:00:00+02:00",
                "before": None,
                "after": {"value": "future"},
            }
        ]
        package["checkpoints"] = {"primary": seal_checkpoint(malformed), "fallbacks": [fallback]}
        package["changes"] = []

        result = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", result["base_checkpoint"]["status"])
        self.assertIn("recent change", result["base_checkpoint"]["rejected_candidates"][0]["reason"])

    def test_checkpoint_recent_change_sequence_must_be_positive(self):
        package = demo_package()
        fallback = copy.deepcopy(package["checkpoints"]["primary"])
        malformed = copy.deepcopy(fallback)
        malformed["recent_changes"] = [
            {
                "change_id": "chg-negative-history",
                "sequence": -1,
                "status": "APPLIED",
                "reason": "Impossible negative history.",
                "source_ids": ["src-pin-001"],
                "observed_at": "2026-07-19T07:45:00+02:00",
                "before": None,
                "after": {"value": "invalid"},
            }
        ]
        package["checkpoints"] = {"primary": seal_checkpoint(malformed), "fallbacks": [fallback]}
        package["changes"] = []

        result = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", result["base_checkpoint"]["status"])
        self.assertIn("recent change", result["base_checkpoint"]["rejected_candidates"][0]["reason"])

    def test_source_pointers_cover_recent_changes_and_resolution_history(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-deactivate-entrypoint-for-coverage",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "DECISION",
                "operation": "DEACTIVATE",
                "subject": "demo.entrypoint",
                "value": "python -m znak_orient serve --host 127.0.0.1 --port 8765",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-authorized-change"],
            }
        ]

        result = orient(package)
        pointers = {item["source_id"] for item in result["checkpoint"]["source_pointers"]}
        self.assertIn("src-authorized-change", pointers)
        for change in result["checkpoint"]["recent_changes"]:
            self.assertTrue(set(change["source_ids"]).issubset(pointers))
        for conflict in result["checkpoint"]["conflicts"]:
            for resolution in conflict.get("resolution_history", []):
                self.assertTrue(set(resolution["source_ids"]).issubset(pointers))

    def test_checkpoint_position_cannot_select_one_side_of_receipt_dispute(self):
        package = demo_package()
        package["changes"] = []
        package["validation_receipts"].append(
            {
                "receipt_id": "vr-clean-pass-checkpoint",
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
        neutral = orient(copy.deepcopy(package))["checkpoint"]
        malformed = copy.deepcopy(neutral)
        failed = receipt_by_id(package, "vr-clean-007")
        malformed["city_position"] = failed["summary"]
        malformed["city_position_source_ids"] = list(failed["source_ids"])
        package["checkpoints"] = {"primary": seal_checkpoint(malformed), "fallbacks": [neutral]}

        result = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", result["base_checkpoint"]["status"])
        self.assertIn("deterministic evidence policy", result["base_checkpoint"]["rejected_candidates"][0]["reason"])

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
                "validation_receipt_pointers": [],
            }
        )
        self.assertTrue(verify_checkpoint_integrity(checkpoint))
        checkpoint["city_position"] = "tampered"
        self.assertFalse(verify_checkpoint_integrity(checkpoint))


class TemporalBoundaryRegressionTests(unittest.TestCase):
    def test_checkpoint_integrity_object_rejects_unsupported_fields(self):
        package = demo_package()
        fallback = copy.deepcopy(package["checkpoints"]["primary"])
        malformed = copy.deepcopy(fallback)
        malformed["integrity"]["unsupported"] = "ignored"
        package["checkpoints"] = {"primary": malformed, "fallbacks": [fallback]}
        package["changes"] = []

        result = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", result["base_checkpoint"]["status"])
        self.assertIn(
            "integrity shape is not closed",
            result["base_checkpoint"]["rejected_candidates"][0]["reason"],
        )

    def _orient_with_rejected_primary(
        self,
        package,
        malformed,
        fallback,
        expected_reason,
    ):
        package["checkpoints"] = {
            "primary": seal_checkpoint(malformed),
            "fallbacks": [copy.deepcopy(fallback)],
        }
        package["changes"] = []
        result = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", result["base_checkpoint"]["status"])
        self.assertIn(expected_reason, result["base_checkpoint"]["rejected_candidates"][0]["reason"])
        self.assertEqual(fallback["checkpoint_id"], result["base_checkpoint"]["checkpoint_id"])
        return result

    def _resolved_entrypoint_checkpoint(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-open-entrypoint-temporal-regression",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:05:00+02:00",
                "content_type": "DECISION",
                "operation": "UPDATE",
                "subject": "demo.entrypoint",
                "value": "python app.py --demo",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-entrypoint-new"],
            },
            {
                "change_id": "chg-resolve-entrypoint-temporal-regression",
                "object_type": "STATE_CHANGE",
                "sequence": 6,
                "observed_at": "2026-07-19T08:10:00+02:00",
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
            },
        ]
        checkpoint = orient(package)["checkpoint"]
        conflict = next(
            item for item in checkpoint["conflicts"]
            if item["conflict_id"] == "conflict:decision:demo.entrypoint"
        )
        self.assertEqual("RESOLVED", conflict["status"])
        return package, checkpoint

    def test_tail_change_rejects_source_or_receipt_that_postdates_it(self):
        source_package = demo_package()
        source_package["validation_receipts"] = [receipt_by_id(source_package, "vr-core-001")]
        source = next(
            item for item in source_package["sources"]
            if item["source_id"] == "src-authorized-change"
        )
        source["captured_at"] = "2026-07-19T08:06:00+02:00"
        source_package["changes"] = [
            {
                "change_id": "chg-source-after-tail",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:05:00+02:00",
                "content_type": "CONSTRAINT",
                "operation": "CREATE",
                "subject": "network.postdated-source",
                "value": "LOCAL_ONLY",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-authorized-change"],
            }
        ]
        source_result = orient(source_package)
        self.assertEqual("REJECTED", source_result["intake"][0]["status"])
        self.assertEqual("SOURCE_POSTDATES_CHANGE", source_result["intake"][0]["reason"])
        self.assertFalse(
            any(
                lamp["subject"] == "network.postdated-source"
                for lamp in source_result["checkpoint"]["active_lamps"]
            )
        )

        receipt_package = demo_package()
        receipt_package["changes"] = [
            {
                "change_id": "chg-receipt-after-tail",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:05:00+02:00",
                "content_type": "FACT",
                "operation": "CREATE",
                "subject": "project.completion",
                "value": "COMPLETE",
                "epistemic": "VERIFIED",
                "authority": "NOT_APPLICABLE",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "validation_receipt_id": "vr-clean-007",
                "source_ids": ["src-clean-validation"],
            }
        ]
        receipt_result = orient(receipt_package)
        self.assertEqual("REJECTED", receipt_result["intake"][0]["status"])
        self.assertEqual("RECEIPT_POSTDATES_CHANGE", receipt_result["intake"][0]["reason"])
        self.assertFalse(
            any(
                lamp["subject"] == "project.completion"
                for lamp in receipt_result["checkpoint"]["active_lamps"]
            )
        )

    def test_resolution_earlier_than_competing_claim_is_rejected(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-open-entrypoint-before-stale-resolution",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:05:00+02:00",
                "content_type": "DECISION",
                "operation": "UPDATE",
                "subject": "demo.entrypoint",
                "value": "python app.py --demo",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-entrypoint-new"],
            },
            {
                "change_id": "chg-resolve-before-competing-claim",
                "object_type": "STATE_CHANGE",
                "sequence": 6,
                "observed_at": "2026-07-19T08:04:00+02:00",
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
            },
        ]

        result = orient(package)
        intake = intake_by_id(result)
        self.assertEqual("DISPUTED", intake["chg-open-entrypoint-before-stale-resolution"]["status"])
        self.assertEqual("REJECTED", intake["chg-resolve-before-competing-claim"]["status"])
        self.assertEqual("STALE_CONFLICT_EVENT", intake["chg-resolve-before-competing-claim"]["reason"])
        conflict = next(
            item for item in result["checkpoint"]["conflicts"]
            if item["conflict_id"] == "conflict:decision:demo.entrypoint"
        )
        self.assertEqual("DISPUTED", conflict["status"])
        self.assertFalse(
            any(
                lamp["type"] == "DECISION" and lamp["subject"] == "demo.entrypoint"
                for lamp in result["checkpoint"]["active_lamps"]
            )
        )

    def test_sealed_checkpoint_rejects_extra_recovery_card_and_postdated_members(self):
        extra_card_package = demo_package()
        fallback = copy.deepcopy(extra_card_package["checkpoints"]["primary"])
        malformed = copy.deepcopy(fallback)
        malformed["recovery_card"] = {"write_back_allowed": False}
        self._orient_with_rejected_primary(
            extra_card_package,
            malformed,
            fallback,
            "top-level shape is not closed",
        )

        source_package = demo_package()
        fallback = copy.deepcopy(source_package["checkpoints"]["primary"])
        malformed = copy.deepcopy(fallback)
        source_package["sources"].append(
            {
                "source_id": "src-after-checkpoint",
                "kind": "USER_DECISION",
                "locator": "demo://decisions/after-checkpoint",
                "captured_at": "2026-07-19T07:51:00+02:00",
                "authority": "AUTHORIZED",
                "excerpt": "Captured after the sealed checkpoint.",
            }
        )
        normalized_source = validate_source(source_package["sources"][-1])
        malformed["source_pointers"].append(
            {
                key: normalized_source[key]
                for key in (
                    "source_id",
                    "kind",
                    "locator",
                    "captured_at",
                    "authority",
                    "content_sha256",
                )
            }
        )
        self._orient_with_rejected_primary(
            source_package,
            malformed,
            fallback,
            "source pointer is newer than the checkpoint",
        )

        lamp_package = demo_package()
        fallback = copy.deepcopy(lamp_package["checkpoints"]["primary"])
        malformed = copy.deepcopy(fallback)
        goal = next(item for item in malformed["active_lamps"] if item["type"] == "GOAL")
        goal["updated_at"] = "2026-07-19T07:51:00+02:00"
        self._orient_with_rejected_primary(
            lamp_package,
            malformed,
            fallback,
            "lamp is newer than the checkpoint",
        )

        receipt_package = demo_package()
        fallback = copy.deepcopy(receipt_package["checkpoints"]["primary"])
        malformed = copy.deepcopy(fallback)
        fact_subject = "checkpoint.postdated-receipt"
        fact_value = "VERIFIED_TOO_LATE"
        receipt_package["validation_receipts"].append(
            {
                "receipt_id": "vr-after-checkpoint",
                "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                "subject": fact_subject,
                "status": "PASS",
                "checked_at": "2026-07-19T07:51:00+02:00",
                "material": False,
                "summary": "Receipt checked after checkpoint creation.",
                "assertion_sha256": sha256_hex({"subject": fact_subject, "value": fact_value}),
                "source_ids": ["src-clean-validation"],
                "checks": [{"id": "postdated-check", "status": "PASS"}],
            }
        )
        malformed["active_lamps"].append(
            {
                "lamp_id": f"lamp:fact:{fact_subject}",
                "type": "FACT",
                "subject": fact_subject,
                "value": fact_value,
                "epistemic": "VERIFIED",
                "authority": "NOT_APPLICABLE",
                "validation_receipt_id": "vr-after-checkpoint",
                "source_ids": ["src-clean-validation"],
                "updated_at": fallback["created_at"],
                "material": False,
            }
        )
        clean_source = validate_source(
            next(
                item for item in receipt_package["sources"]
                if item["source_id"] == "src-clean-validation"
            )
        )
        malformed["source_pointers"].append(
            {
                key: clean_source[key]
                for key in (
                    "source_id",
                    "kind",
                    "locator",
                    "captured_at",
                    "authority",
                    "content_sha256",
                )
            }
        )
        self._orient_with_rejected_primary(
            receipt_package,
            malformed,
            fallback,
            "validation receipt postdates the lamp",
        )

    def test_resolved_conflict_must_match_active_lamp_exactly(self):
        package, resolved = self._resolved_entrypoint_checkpoint()
        fallback = copy.deepcopy(package["checkpoints"]["primary"])

        mutations = {
            "missing lamp": lambda checkpoint: checkpoint.__setitem__(
                "active_lamps",
                [
                    lamp for lamp in checkpoint["active_lamps"]
                    if not (lamp["type"] == "DECISION" and lamp["subject"] == "demo.entrypoint")
                ],
            ),
            "different preserved value": lambda checkpoint: next(
                lamp for lamp in checkpoint["active_lamps"]
                if lamp["type"] == "DECISION" and lamp["subject"] == "demo.entrypoint"
            ).__setitem__("value", "python app.py --demo"),
            "different sources": lambda checkpoint: next(
                lamp for lamp in checkpoint["active_lamps"]
                if lamp["type"] == "DECISION" and lamp["subject"] == "demo.entrypoint"
            ).__setitem__("source_ids", ["src-entrypoint-old"]),
            "different timestamp": lambda checkpoint: next(
                lamp for lamp in checkpoint["active_lamps"]
                if lamp["type"] == "DECISION" and lamp["subject"] == "demo.entrypoint"
            ).__setitem__("updated_at", "2026-07-19T08:11:00+02:00"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                malformed = copy.deepcopy(resolved)
                mutate(malformed)
                self._orient_with_rejected_primary(
                    copy.deepcopy(package),
                    malformed,
                    fallback,
                    "resolved conflict is inconsistent with its active lamp",
                )

    def test_resolved_conflict_selects_preserved_claim_with_authorized_trusted_provenance(self):
        package, resolved = self._resolved_entrypoint_checkpoint()
        fallback = copy.deepcopy(package["checkpoints"]["primary"])

        unpreserved = copy.deepcopy(resolved)
        conflict = next(
            item for item in unpreserved["conflicts"]
            if item["conflict_id"] == "conflict:decision:demo.entrypoint"
        )
        conflict["resolution_history"][-1]["value"] = "python -m znak_orient serve --unpreserved"
        resolved_lamp = next(
            item for item in unpreserved["active_lamps"]
            if item["type"] == "DECISION" and item["subject"] == "demo.entrypoint"
        )
        resolved_lamp["value"] = conflict["resolution_history"][-1]["value"]
        self._orient_with_rejected_primary(
            copy.deepcopy(package),
            unpreserved,
            fallback,
            "resolution selects an unpreserved claim",
        )

        untrusted = copy.deepcopy(resolved)
        conflict = next(
            item for item in untrusted["conflicts"]
            if item["conflict_id"] == "conflict:decision:demo.entrypoint"
        )
        conflict["resolution_history"][-1]["source_ids"] = ["src-checkpoint-001"]
        self._orient_with_rejected_primary(
            copy.deepcopy(package),
            untrusted,
            fallback,
            "resolution lacks authorized provenance",
        )


class SemanticSuccessConditionRegressionTests(unittest.TestCase):
    def test_receipt_dispute_suspends_active_fact_and_keeps_its_claim(self):
        package = demo_package()
        core_receipt = receipt_by_id(package, "vr-core-001")
        package["validation_receipts"].append(
            {
                "receipt_id": "vr-core-conflicting-fail",
                "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                "subject": "project.phase",
                "status": "FAIL",
                "checked_at": "2026-07-19T08:15:00+02:00",
                "material": True,
                "summary": "Core phase validation failed.",
                "assertion_sha256": core_receipt["assertion_sha256"],
                "source_ids": ["src-clean-validation"],
                "checks": [{"id": "core-phase", "status": "FAIL"}],
            }
        )
        package["changes"] = []

        result = orient(package)
        self.assertFalse(
            any(
                lamp["type"] == "FACT" and lamp["subject"] == "project.phase"
                for lamp in result["checkpoint"]["active_lamps"]
            )
        )
        conflict = next(
            item
            for item in result["checkpoint"]["conflicts"]
            if item["conflict_id"] == "conflict:fact:validation.project.phase"
        )
        self.assertEqual("DISPUTED", conflict["status"])
        self.assertIn("lamp:fact:project.phase", {claim["claim_id"] for claim in conflict["claims"]})
        self.assertTrue(result["run_receipt"]["checks"]["disputed_claims_not_action_driving"])
        self.assertEqual("PASS", result["run_receipt"]["status"])

    def test_new_receipt_dispute_replaces_receipt_driven_position_with_unknown(self):
        first_package = demo_package()
        first_package["validation_receipts"] = [receipt_by_id(first_package, "vr-core-001")]
        first_package["validation_receipts"].append(
            {
                "receipt_id": "vr-release-pass",
                "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                "subject": "release.state",
                "status": "PASS",
                "checked_at": "2026-07-19T08:10:00+02:00",
                "material": True,
                "summary": "Release state passed.",
                "assertion_sha256": "b" * 64,
                "source_ids": ["src-clean-validation"],
                "checks": [{"id": "release-state", "status": "PASS"}],
            }
        )
        first_package["changes"] = []
        first = orient(first_package)
        self.assertEqual("Release state passed.", first["checkpoint"]["city_position"])

        follow_up = copy.deepcopy(first_package)
        follow_up["as_of"] = "2026-07-19T08:40:00+02:00"
        follow_up["checkpoints"] = {"primary": first["checkpoint"], "fallbacks": []}
        follow_up["validation_receipts"].append(
            {
                "receipt_id": "vr-release-fail",
                "validator_id": "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
                "subject": "release.state",
                "status": "FAIL",
                "checked_at": "2026-07-19T08:35:00+02:00",
                "material": True,
                "summary": "Release state failed.",
                "assertion_sha256": "b" * 64,
                "source_ids": ["src-clean-validation"],
                "checks": [{"id": "release-state", "status": "FAIL"}],
            }
        )

        result = orient(follow_up)
        self.assertEqual(
            "Current position is UNKNOWN because trusted validation receipts for release.state disagree.",
            result["checkpoint"]["city_position"],
        )
        self.assertEqual("BLOCKED", result["checkpoint"]["voltage"])
        self.assertEqual("PASS", result["run_receipt"]["status"])

    def test_second_goal_is_rejected_while_primary_goal_is_disputed(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["changes"] = [
            {
                "change_id": "chg-contest-goal-before-second",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "GOAL",
                "operation": "UPDATE",
                "subject": "project.primary",
                "value": "A competing primary goal.",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-pin-001"],
            },
            {
                "change_id": "chg-create-second-during-goal-conflict",
                "object_type": "STATE_CHANGE",
                "sequence": 6,
                "observed_at": "2026-07-19T08:01:00+02:00",
                "content_type": "GOAL",
                "operation": "CREATE",
                "subject": "project.secondary",
                "value": "A second active goal.",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-pin-001"],
            },
        ]

        result = orient(package)
        intake = intake_by_id(result)
        self.assertEqual("DISPUTED", intake["chg-contest-goal-before-second"]["status"])
        self.assertEqual("REJECTED", intake["chg-create-second-during-goal-conflict"]["status"])
        self.assertEqual(
            "MULTIPLE_GOAL_CONTEXTS_NOT_ALLOWED",
            intake["chg-create-second-during-goal-conflict"]["reason"],
        )
        self.assertEqual("BLOCKED", result["checkpoint"]["voltage"])

    def test_same_value_materiality_upgrade_is_a_semantic_change(self):
        package = demo_package()
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        base_change = {
            "object_type": "STATE_CHANGE",
            "content_type": "RISK",
            "subject": "risk.same-value",
            "value": "Risk exists.",
            "epistemic": "SUPPORTED",
            "authority": "NOT_APPLICABLE",
            "expected_checkpoint_id": "cp-old-valid-001",
            "source_ids": ["src-clean-validation"],
        }
        package["changes"] = [
            {
                **base_change,
                "change_id": "chg-risk-nonmaterial",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "operation": "CREATE",
                "material": False,
            },
            {
                **base_change,
                "change_id": "chg-risk-material",
                "sequence": 6,
                "observed_at": "2026-07-19T08:01:00+02:00",
                "operation": "UPDATE",
                "material": True,
            },
        ]

        result = orient(package)
        intake = intake_by_id(result)
        self.assertEqual("STATE_METADATA_UPDATED", intake["chg-risk-material"]["reason"])
        risk = next(
            lamp for lamp in result["checkpoint"]["active_lamps"] if lamp["subject"] == "risk.same-value"
        )
        self.assertTrue(risk["material"])
        self.assertEqual("WEAK", result["checkpoint"]["voltage"])

    def test_same_value_corroboration_uses_instant_order_across_offsets(self):
        package = demo_package()
        package["as_of"] = "2026-07-19T10:00:00+02:00"
        package["validation_receipts"] = [receipt_by_id(package, "vr-core-001")]
        package["sources"].append(
            {
                "source_id": "src-offset-corroboration",
                "kind": "USER_DECISION",
                "locator": "demo://decisions/offset-corroboration",
                "captured_at": "2026-07-19T07:00:00+00:00",
                "authority": "AUTHORIZED",
                "excerpt": "Same risk corroborated in a different timezone offset.",
            }
        )
        base_change = {
            "object_type": "STATE_CHANGE",
            "content_type": "RISK",
            "subject": "risk.offset",
            "value": "Risk exists.",
            "epistemic": "SUPPORTED",
            "authority": "NOT_APPLICABLE",
            "material": True,
            "expected_checkpoint_id": "cp-old-valid-001",
        }
        package["changes"] = [
            {
                **base_change,
                "change_id": "chg-risk-offset-create",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "operation": "CREATE",
                "source_ids": ["src-clean-validation"],
            },
            {
                **base_change,
                "change_id": "chg-risk-offset-update",
                "sequence": 6,
                "observed_at": "2026-07-19T07:30:00+00:00",
                "operation": "UPDATE",
                "source_ids": ["src-offset-corroboration"],
            },
        ]

        result = orient(package)
        risk = next(
            lamp for lamp in result["checkpoint"]["active_lamps"] if lamp["subject"] == "risk.offset"
        )
        self.assertEqual("2026-07-19T07:30:00+00:00", risk["updated_at"])
        self.assertEqual(
            {"src-clean-validation", "src-offset-corroboration"},
            set(risk["source_ids"]),
        )

    def test_success_condition_evaluator_rejects_open_or_unsupported_shapes(self):
        result = orient(demo_package())
        valid_conditions = [
            {
                "type": "conflict_resolved",
                "subject": "demo.entrypoint",
                "content_type": "DECISION",
                "required_authority": "AUTHORIZED",
            },
            {
                "type": "constraint_policy_allows",
                "subject": "network.policy",
                "policy_class": "GOAL_VALIDATION",
            },
            {"type": "unknown_resolved", "subject": "absent.unknown"},
            {"type": "risk_mitigated", "subject": "absent.risk"},
            {
                "type": "validation_pass",
                "status": "PASS",
                "subject": "project.completion",
                "checked_after": "2026-07-19T08:00:00+02:00",
                "assertion_sha256": "a" * 64,
            },
            {
                "type": "validation_receipt_retained",
                "status": "PASS",
                "subject": "project.primary",
                "checked_after": "2026-07-19T08:00:00+02:00",
                "assertion_sha256": "a" * 64,
            },
        ]

        for condition in valid_conditions:
            with self.subTest(condition_type=condition["type"]):
                malformed = {**condition, "extra": "must not be ignored"}
                self.assertFalse(evaluate_success_condition(result, malformed))
        self.assertFalse(
            evaluate_success_condition(
                result,
                {"type": "unsupported", "subject": "absent.risk"},
            )
        )

    @staticmethod
    def _trusted_completion_pass():
        return {
            "receipt_id": "vr-clean-pass-success-condition",
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

    def test_old_object_conditions_stay_false_when_material_conflict_replaces_active_state(self):
        constraint_package = demo_package()
        constraint_package["validation_receipts"] = [
            receipt_by_id(constraint_package, "vr-core-001")
        ]
        constraint_package["changes"] = [
            {
                "change_id": "chg-dispute-network-policy-for-condition",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "CONSTRAINT",
                "operation": "UPDATE",
                "subject": "network.policy",
                "value": "LOCAL_ONLY",
                "epistemic": "VERIFIED",
                "authority": "AUTHORIZED",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-authorized-change"],
            }
        ]
        constraint_result = orient(constraint_package)
        constraint_conflict = next(
            item for item in constraint_result["checkpoint"]["conflicts"]
            if item["type"] == "CONSTRAINT" and item["subject"] == "network.policy"
        )
        self.assertEqual("DISPUTED", constraint_conflict["status"])
        self.assertTrue(constraint_conflict["material"])
        self.assertFalse(
            any(
                lamp["type"] == "CONSTRAINT" and lamp["subject"] == "network.policy"
                for lamp in constraint_result["checkpoint"]["active_lamps"]
            )
        )
        self.assertFalse(
            evaluate_success_condition(
                constraint_result,
                {
                    "type": "constraint_policy_allows",
                    "subject": "network.policy",
                    "policy_class": "GOAL_VALIDATION",
                },
            )
        )

        risk_package = demo_package()
        risk_package["validation_receipts"] = [receipt_by_id(risk_package, "vr-core-001")]
        risk_package["changes"] = [
            {
                "change_id": "chg-create-risk-for-condition",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "RISK",
                "operation": "CREATE",
                "subject": "storage.integrity",
                "value": "Backup has not been verified.",
                "epistemic": "SUPPORTED",
                "authority": "NOT_APPLICABLE",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-clean-validation"],
            },
            {
                "change_id": "chg-dispute-risk-for-condition",
                "object_type": "STATE_CHANGE",
                "sequence": 6,
                "observed_at": "2026-07-19T08:01:00+02:00",
                "content_type": "RISK",
                "operation": "UPDATE",
                "subject": "storage.integrity",
                "value": "Backup verification is sufficient.",
                "epistemic": "SUPPORTED",
                "authority": "NOT_APPLICABLE",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-clean-validation"],
            },
        ]
        risk_result = orient(risk_package)
        risk_conflict = next(
            item for item in risk_result["checkpoint"]["conflicts"]
            if item["type"] == "RISK" and item["subject"] == "storage.integrity"
        )
        self.assertEqual("DISPUTED", risk_conflict["status"])
        self.assertTrue(risk_conflict["material"])
        self.assertFalse(
            any(
                lamp["type"] == "RISK" and lamp["subject"] == "storage.integrity"
                for lamp in risk_result["checkpoint"]["active_lamps"]
            )
        )
        self.assertFalse(
            evaluate_success_condition(
                risk_result,
                {"type": "risk_mitigated", "subject": "storage.integrity"},
            )
        )

        unknown_package = demo_package()
        unknown_package["validation_receipts"] = [
            receipt_by_id(unknown_package, "vr-core-001")
        ]
        unknown_package["changes"] = [
            {
                "change_id": "chg-create-unknown-for-condition",
                "object_type": "STATE_CHANGE",
                "sequence": 5,
                "observed_at": "2026-07-19T08:00:00+02:00",
                "content_type": "UNKNOWN",
                "operation": "CREATE",
                "subject": "release.owner",
                "value": "Release owner is unknown.",
                "epistemic": "UNKNOWN",
                "authority": "NOT_APPLICABLE",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-clean-validation"],
            },
            {
                "change_id": "chg-dispute-unknown-for-condition",
                "object_type": "STATE_CHANGE",
                "sequence": 6,
                "observed_at": "2026-07-19T08:01:00+02:00",
                "content_type": "UNKNOWN",
                "operation": "UPDATE",
                "subject": "release.owner",
                "value": "Release owner may be assigned.",
                "epistemic": "UNKNOWN",
                "authority": "NOT_APPLICABLE",
                "material": True,
                "expected_checkpoint_id": "cp-old-valid-001",
                "source_ids": ["src-clean-validation"],
            },
        ]
        unknown_result = orient(unknown_package)
        unknown_conflict = next(
            item for item in unknown_result["checkpoint"]["conflicts"]
            if item["type"] == "UNKNOWN" and item["subject"] == "release.owner"
        )
        self.assertEqual("DISPUTED", unknown_conflict["status"])
        self.assertTrue(unknown_conflict["material"])
        self.assertFalse(
            any(
                lamp["type"] == "UNKNOWN" and lamp["subject"] == "release.owner"
                for lamp in unknown_result["checkpoint"]["active_lamps"]
            )
        )
        self.assertFalse(
            evaluate_success_condition(
                unknown_result,
                {"type": "unknown_resolved", "subject": "release.owner"},
            )
        )

    def test_unknown_resolved_follows_validation_lineage_after_contradictory_receipts(self):
        package = demo_package()
        package["changes"] = []
        package["validation_receipts"].append(self._trusted_completion_pass())

        result = orient(package)
        self.assertTrue(
            any(
                item["status"] == "DISPUTED"
                and item["type"] == "FACT"
                and item["subject"] == "validation.project.completion"
                for item in result["checkpoint"]["conflicts"]
            )
        )
        self.assertTrue(
            any(
                item["subject"] == "validation.project.completion"
                for item in result["checkpoint"]["unknowns"]
            )
        )
        for subject in ("project.completion", "project.completion.failure_cause"):
            with self.subTest(subject=subject):
                self.assertFalse(
                    evaluate_success_condition(
                        result,
                        {"type": "unknown_resolved", "subject": subject},
                    )
                )

    def test_validation_conditions_fail_closed_on_contradictory_trusted_receipts(self):
        package = demo_package()
        package["changes"] = []
        passing_receipt = self._trusted_completion_pass()
        package["validation_receipts"].append(passing_receipt)
        result = orient(package)

        for condition_type in ("validation_pass", "validation_receipt_retained"):
            with self.subTest(condition_type=condition_type):
                self.assertFalse(
                    evaluate_success_condition(
                        result,
                        {
                            "type": condition_type,
                            "status": "PASS",
                            "subject": passing_receipt["subject"],
                            "checked_after": "2026-07-19T08:10:00+02:00",
                            "assertion_sha256": passing_receipt["assertion_sha256"],
                        },
                    )
                )

    def test_validation_conditions_require_matching_hash_and_strictly_later_receipt(self):
        package = demo_package()
        package["changes"] = []
        passing_receipt = self._trusted_completion_pass()
        package["validation_receipts"] = [
            receipt_by_id(package, "vr-core-001"),
            passing_receipt,
        ]
        result = orient(package)

        for condition_type in ("validation_pass", "validation_receipt_retained"):
            valid = {
                "type": condition_type,
                "status": "PASS",
                "subject": passing_receipt["subject"],
                "checked_after": "2026-07-19T08:14:00+02:00",
                "assertion_sha256": passing_receipt["assertion_sha256"],
            }
            with self.subTest(condition_type=condition_type, variant="valid"):
                self.assertTrue(evaluate_success_condition(result, valid))

            wrong_hash = copy.deepcopy(valid)
            wrong_hash["assertion_sha256"] = "a" * 64
            with self.subTest(condition_type=condition_type, variant="wrong_hash"):
                self.assertFalse(evaluate_success_condition(result, wrong_hash))

            equal_time = copy.deepcopy(valid)
            equal_time["checked_after"] = passing_receipt["checked_at"]
            with self.subTest(condition_type=condition_type, variant="equal_time"):
                self.assertFalse(evaluate_success_condition(result, equal_time))

    def test_receipt_and_change_material_must_be_json_boolean(self):
        invalid_material_values = (1, "true", None)
        for value in invalid_material_values:
            with self.subTest(contract="receipt", value=value):
                package = demo_package()
                package["validation_receipts"][0]["material"] = value
                with self.assertRaisesRegex(
                    OrientationError,
                    "receipt.material must be a JSON boolean",
                ):
                    orient(package)

            with self.subTest(contract="change", value=value):
                package = demo_package()
                state_change = next(
                    item for item in package["changes"]
                    if item.get("object_type") == "STATE_CHANGE"
                )
                state_change["material"] = value
                with self.assertRaisesRegex(
                    OrientationError,
                    "change.material must be a JSON boolean",
                ):
                    orient(package)

    def test_checkpoint_non_fact_lamp_rejects_existing_validation_receipt(self):
        package = demo_package()
        fallback = copy.deepcopy(package["checkpoints"]["primary"])
        malformed = copy.deepcopy(fallback)
        decision = next(item for item in malformed["active_lamps"] if item["type"] == "DECISION")
        decision["validation_receipt_id"] = "vr-core-001"
        package["checkpoints"] = {
            "primary": seal_checkpoint(malformed),
            "fallbacks": [fallback],
        }
        package["changes"] = []

        result = orient(package)
        self.assertEqual("FALLBACK_VALID_AFTER_CORRUPTION", result["base_checkpoint"]["status"])
        self.assertIn(
            "non-FACT lamp cannot retain a validation receipt",
            result["base_checkpoint"]["rejected_candidates"][0]["reason"],
        )
        self.assertEqual(fallback["checkpoint_id"], result["base_checkpoint"]["checkpoint_id"])


if __name__ == "__main__":
    unittest.main()
