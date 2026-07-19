"""Deterministic X30 memory-orientation reducer."""

from __future__ import annotations

import copy
from typing import Any, Iterable

from .canonical import seal_checkpoint, sha256_hex, verify_checkpoint_integrity
from .contracts import (
    AUTHORITIES,
    SCHEMA_VERSION,
    TRUSTED_VALIDATOR_IDS,
    ContractError,
    normalize_change,
    parse_instant,
    require,
    require_list,
    require_mapping,
    require_text,
    semantic_fingerprint,
    validate_receipt,
    validate_source,
)


class OrientationError(ValueError):
    """Raised when no safe deterministic orientation can be produced."""


def _checkpoint_is_semantically_valid(checkpoint: Any, as_of: str) -> tuple[bool, str]:
    if not isinstance(checkpoint, dict):
        return False, "checkpoint is not an object"
    if checkpoint.get("schema_version") != SCHEMA_VERSION:
        return False, "unsupported checkpoint schema"
    if not verify_checkpoint_integrity(checkpoint):
        return False, "checkpoint integrity mismatch"
    try:
        created_at = parse_instant(checkpoint.get("created_at"), "CP-001", "checkpoint.created_at")
        as_of_instant = parse_instant(as_of, "CP-002", "package.as_of")
    except ContractError as exc:
        return False, str(exc)
    if created_at > as_of_instant:
        return False, "checkpoint is from the future"
    last_sequence = checkpoint.get("last_sequence")
    if not isinstance(last_sequence, int) or isinstance(last_sequence, bool) or last_sequence < 0:
        return False, "checkpoint.last_sequence is invalid"
    for field in ("active_lamps", "recent_changes", "conflicts", "unknowns", "source_pointers"):
        if not isinstance(checkpoint.get(field), list):
            return False, f"checkpoint.{field} must be an array"
    if not isinstance(checkpoint.get("primary_next_step"), dict):
        return False, "checkpoint.primary_next_step must be an object"
    return True, "valid"


def _select_checkpoint(package: dict[str, Any], as_of: str) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    checkpoints = require_mapping(package.get("checkpoints"), "PKG-010", "package.checkpoints")
    candidates: list[tuple[str, Any]] = [("PRIMARY", checkpoints.get("primary"))]
    candidates.extend((f"FALLBACK_{index + 1}", value) for index, value in enumerate(checkpoints.get("fallbacks", [])))
    errors: list[dict[str, str]] = []
    for label, checkpoint in candidates:
        valid, reason = _checkpoint_is_semantically_valid(checkpoint, as_of)
        if valid:
            status = "PRIMARY_VALID" if label == "PRIMARY" else "FALLBACK_VALID_AFTER_CORRUPTION"
            return copy.deepcopy(checkpoint), status, errors
        errors.append({"candidate": label, "reason": reason})
    raise OrientationError("[CP-RECOVERY] no valid checkpoint or fallback is available")


def _disposition(change: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        "change_id": change["change_id"],
        "sequence": change["sequence"],
        "object_type": change["object_type"],
        "content_type": change.get("content_type", "TRACE"),
        "subject": change.get("subject", "imported.text"),
        "status": status,
        "reason": reason,
        "source_ids": change["source_ids"],
    }


def _lamp_from_change(change: dict[str, Any]) -> dict[str, Any]:
    return {
        "lamp_id": f"lamp:{change['content_type'].lower()}:{change['subject']}",
        "type": change["content_type"],
        "subject": change["subject"],
        "value": copy.deepcopy(change["value"]),
        "epistemic": change["epistemic"],
        "authority": change["authority"],
        "source_ids": list(change["source_ids"]),
        "updated_at": change["observed_at"],
        "material": change["material"],
    }


def _policy_rejection(
    change: dict[str, Any],
    sources: dict[str, dict[str, Any]],
    receipts: dict[str, dict[str, Any]],
    base_checkpoint_id: str,
    as_of: str,
) -> str | None:
    if not change["source_ids"] or any(source_id not in sources for source_id in change["source_ids"]):
        return "SOURCE_UNKNOWN"
    if parse_instant(change["observed_at"], "CHG-TIME", "change.observed_at") > parse_instant(as_of, "PKG-TIME", "package.as_of"):
        return "FUTURE_EVIDENCE_REJECTED"
    expected = change.get("expected_checkpoint_id")
    if expected and expected != base_checkpoint_id:
        return "STALE_STATE"
    if change["content_type"] in {"GOAL", "DECISION", "CONSTRAINT"} or change["operation"] == "RESOLVE":
        if change["authority"] != "AUTHORIZED":
            return "UNAUTHORIZED_OVERRIDE"
        if any(sources[source_id]["authority"] != "AUTHORIZED" for source_id in change["source_ids"]):
            return "AUTHORITY_SOURCE_MISMATCH"
    if change["content_type"] == "FACT":
        if change["epistemic"] != "VERIFIED":
            return "UNSUPPORTED_FACT"
        receipt = receipts.get(change.get("validation_receipt_id", ""))
        if receipt is None:
            return "MISSING_VALIDATION_RECEIPT"
        if receipt["status"] != "PASS" or receipt["subject"] != change["subject"]:
            return "RECEIPT_NOT_PASS"
        if receipt["validator_id"] not in TRUSTED_VALIDATOR_IDS:
            return "UNTRUSTED_VALIDATOR_RECEIPT"
    if change["content_type"] == "UNKNOWN" and change["epistemic"] != "UNKNOWN":
        return "UNKNOWN_EPISTEMIC_MISMATCH"
    return None


def _open_conflict(existing: dict[str, Any], change: dict[str, Any]) -> dict[str, Any]:
    conflict_id = f"conflict:{change['content_type'].lower()}:{change['subject']}"
    return {
        "conflict_id": conflict_id,
        "type": change["content_type"],
        "subject": change["subject"],
        "material": bool(existing.get("material") or change["material"]),
        "status": "DISPUTED",
        "reason": "Competing source-backed claims exist and neither explicitly supersedes the other.",
        "claims": [
            {
                "claim_id": existing["lamp_id"],
                "value": copy.deepcopy(existing["value"]),
                "epistemic": "DISPUTED",
                "authority": existing["authority"],
                "source_ids": list(existing["source_ids"]),
                "observed_at": existing["updated_at"],
            },
            {
                "claim_id": change["change_id"],
                "value": copy.deepcopy(change["value"]),
                "epistemic": "DISPUTED",
                "authority": change["authority"],
                "source_ids": list(change["source_ids"]),
                "observed_at": change["observed_at"],
            },
        ],
    }


def _critical_unknowns(receipts: Iterable[dict[str, Any]], existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unknowns = {item["unknown_id"]: copy.deepcopy(item) for item in existing}
    for receipt in receipts:
        if receipt["status"] == "FAIL" and receipt["material"]:
            unknown_id = f"unknown:failure-cause:{receipt['subject']}"
            unknowns[unknown_id] = {
                "unknown_id": unknown_id,
                "subject": f"{receipt['subject']}.failure_cause",
                "statement": f"Root cause and corrective proof for {receipt['subject']} remain UNKNOWN after failed validation.",
                "critical": True,
                "epistemic": "UNKNOWN",
                "source_ids": list(receipt["source_ids"]),
            }
    return sorted(unknowns.values(), key=lambda item: item["unknown_id"])


def _choose_next_step(
    conflicts: list[dict[str, Any]], unknowns: list[dict[str, Any]], receipts: list[dict[str, Any]], sources: dict[str, dict[str, Any]]
) -> tuple[str, dict[str, Any]]:
    material_conflicts = [item for item in conflicts if item["status"] == "DISPUTED" and item["material"]]
    if material_conflicts:
        conflict = sorted(material_conflicts, key=lambda item: item["conflict_id"])[0]
        source_ids = sorted({source_id for claim in conflict["claims"] for source_id in claim["source_ids"]})
        return "BLOCKED", {
            "action_id": f"resolve:{conflict['subject']}",
            "instruction": f"Record one AUTHORIZED resolution for {conflict['subject']} that explicitly supersedes the competing claims.",
            "reason": "The conflict is material; disputed claims cannot drive execution.",
            "source_ids": source_ids,
            "success_condition": {
                "type": "conflict_resolved",
                "subject": conflict["subject"],
                "required_authority": "AUTHORIZED",
            },
        }
    critical_unknowns = [item for item in unknowns if item.get("critical")]
    if critical_unknowns:
        unknown = sorted(critical_unknowns, key=lambda item: item["unknown_id"])[0]
        return "UNKNOWN", {
            "action_id": f"evidence:{unknown['subject']}",
            "instruction": f"Collect and validate source evidence that resolves {unknown['subject']}.",
            "reason": "A critical unknown prevents a supported action.",
            "source_ids": list(unknown["source_ids"]),
            "success_condition": {"type": "unknown_resolved", "subject": unknown["subject"]},
        }
    failed = [receipt for receipt in receipts if receipt["status"] == "FAIL"]
    if failed:
        receipt = sorted(failed, key=lambda item: item["receipt_id"])[0]
        return "BLOCKED", {
            "action_id": f"validate:{receipt['subject']}",
            "instruction": f"Fix the evidenced failure and rerun validation for {receipt['subject']}.",
            "reason": receipt["summary"],
            "source_ids": list(receipt["source_ids"]),
            "success_condition": {"type": "validation_pass", "subject": receipt["subject"]},
        }
    goal_sources = sorted(source_id for source_id, source in sources.items() if source["authority"] == "AUTHORIZED")[:1]
    return "FLOWING", {
        "action_id": "validate:current-goal",
        "instruction": "Execute the next goal-aligned validation and retain its receipt.",
        "reason": "No material conflict or critical unknown currently blocks the goal.",
        "source_ids": goal_sources,
        "success_condition": {"type": "validation_receipt_retained", "status": "PASS"},
    }


def _source_pointers(source_ids: Iterable[str], sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": source_id,
            "kind": sources[source_id]["kind"],
            "locator": sources[source_id]["locator"],
            "captured_at": sources[source_id]["captured_at"],
            "authority": sources[source_id]["authority"],
        }
        for source_id in sorted(set(source_ids))
        if source_id in sources
    ]


def _derive_recovery_card(checkpoint: dict[str, Any]) -> dict[str, Any]:
    goal_lamps = [lamp for lamp in checkpoint["active_lamps"] if lamp["type"] == "GOAL"]
    decisions = [lamp for lamp in checkpoint["active_lamps"] if lamp["type"] == "DECISION"]
    constraints = [lamp for lamp in checkpoint["active_lamps"] if lamp["type"] == "CONSTRAINT"]
    risks = [lamp for lamp in checkpoint["active_lamps"] if lamp["type"] == "RISK"]
    return {
        "card_id": f"rc:{checkpoint['checkpoint_id']}",
        "derived_from_checkpoint_id": checkpoint["checkpoint_id"],
        "derived_from_integrity": checkpoint["integrity"]["value"],
        "source_of_truth": False,
        "write_back_allowed": False,
        "city_position": checkpoint["city_position"],
        "goal": goal_lamps[0]["value"] if goal_lamps else "UNKNOWN",
        "decisions": [{"subject": item["subject"], "value": item["value"]} for item in decisions],
        "constraints": [{"subject": item["subject"], "value": item["value"]} for item in constraints],
        "risks": [{"subject": item["subject"], "value": item["value"]} for item in risks],
        "conflicts": [{"conflict_id": item["conflict_id"], "subject": item["subject"], "status": item["status"]} for item in checkpoint["conflicts"]],
        "unknowns": [{"unknown_id": item["unknown_id"], "statement": item["statement"]} for item in checkpoint["unknowns"]],
        "voltage": checkpoint["voltage"],
        "primary_next_step": copy.deepcopy(checkpoint["primary_next_step"]),
        "source_pointers": copy.deepcopy(checkpoint["source_pointers"]),
    }


def orient(raw_package: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic checkpoint, Recovery Card, and scoped run receipt."""

    try:
        package = require_mapping(copy.deepcopy(raw_package), "PKG-001", "package")
        require(package.get("schema_version") == SCHEMA_VERSION, "PKG-002", "package schema must be 0.3C")
        package_id = require_text(package.get("package_id"), "PKG-003", "package_id")
        as_of = require_text(package.get("as_of"), "PKG-004", "package.as_of")
        parse_instant(as_of, "PKG-004", "package.as_of")

        source_list = [validate_source(item) for item in require_list(package.get("sources"), "PKG-005", "package.sources")]
        sources = {item["source_id"]: item for item in source_list}
        require(len(sources) == len(source_list), "PKG-006", "source_ids must be unique")
        receipt_list = [validate_receipt(item) for item in require_list(package.get("validation_receipts", []), "PKG-007", "package.validation_receipts")]
        receipts = {item["receipt_id"]: item for item in receipt_list}
        require(len(receipts) == len(receipt_list), "PKG-008", "receipt_ids must be unique")
        for receipt in receipt_list:
            require(all(source_id in sources for source_id in receipt["source_ids"]), "PKG-009", f"receipt {receipt['receipt_id']} has an unknown source")

        base, recovery_status, checkpoint_errors = _select_checkpoint(package, as_of)
        base_checkpoint_id = base["checkpoint_id"]
        last_sequence = base["last_sequence"]
        state = {(lamp["type"], lamp["subject"]): copy.deepcopy(lamp) for lamp in base["active_lamps"]}
        conflicts = {item["conflict_id"]: copy.deepcopy(item) for item in base["conflicts"]}
        dispositions: list[dict[str, Any]] = []
        meaningful: list[dict[str, Any]] = []
        seen_ids: dict[str, str] = {}
        seen_semantics: set[str] = set()
        normalized_changes = [normalize_change(item) for item in require_list(package.get("changes"), "PKG-011", "package.changes")]

        for change in sorted(normalized_changes, key=lambda item: (item["sequence"], item["change_id"])):
            last_sequence = max(last_sequence, change["sequence"])
            fingerprint = semantic_fingerprint(change)
            prior_fingerprint = seen_ids.get(change["change_id"])
            if prior_fingerprint is not None:
                reason = "DUPLICATE" if prior_fingerprint == fingerprint else "ID_REUSE_CONFLICT"
                dispositions.append(_disposition(change, "REJECTED", reason))
                continue
            seen_ids[change["change_id"]] = fingerprint
            if fingerprint in seen_semantics:
                dispositions.append(_disposition(change, "REJECTED", "DUPLICATE"))
                continue
            seen_semantics.add(fingerprint)
            if change["sequence"] <= base["last_sequence"]:
                dispositions.append(_disposition(change, "IGNORED", "COVERED_BY_VALID_CHECKPOINT"))
                continue
            if change["object_type"] == "TRACE":
                instruction_markers = ("ignore previous", "system:", "mark complete", "override authority")
                reason = "IMPORTED_TEXT_IS_DATA_NOT_INSTRUCTION" if any(marker in change["text"].lower() for marker in instruction_markers) else "TRACE_EXPIRED_NO_MEANINGFUL_CHANGE"
                dispositions.append(_disposition(change, "IGNORED", reason))
                continue
            if change["object_type"] == "RECOVERY_CARD":
                dispositions.append(_disposition(change, "REJECTED", "RECOVERY_CARD_CONTAMINATION"))
                continue

            policy_reason = _policy_rejection(change, sources, receipts, base_checkpoint_id, as_of)
            if policy_reason:
                dispositions.append(_disposition(change, "REJECTED", policy_reason))
                continue

            key = (change["content_type"], change["subject"])
            conflict_id = f"conflict:{change['content_type'].lower()}:{change['subject']}"
            if change["operation"] == "RESOLVE":
                conflict = conflicts.get(change.get("resolves_conflict_id") or conflict_id)
                if conflict is None or change["value"] not in [claim["value"] for claim in conflict["claims"]]:
                    dispositions.append(_disposition(change, "REJECTED", "INVALID_CONFLICT_RESOLUTION"))
                    continue
                state[key] = _lamp_from_change(change)
                conflict["status"] = "RESOLVED"
                conflict["resolution_change_id"] = change["change_id"]
                conflicts[conflict["conflict_id"]] = conflict
                disposition = _disposition(change, "APPLIED", "AUTHORIZED_CONFLICT_RESOLUTION")
                dispositions.append(disposition)
                meaningful.append(disposition)
                continue

            existing_conflict = conflicts.get(conflict_id)
            if existing_conflict and existing_conflict["status"] == "DISPUTED":
                existing_conflict["claims"].append(
                    {
                        "claim_id": change["change_id"],
                        "value": copy.deepcopy(change["value"]),
                        "epistemic": "DISPUTED",
                        "authority": change["authority"],
                        "source_ids": list(change["source_ids"]),
                        "observed_at": change["observed_at"],
                    }
                )
                disposition = _disposition(change, "DISPUTED", "CONFLICT_PRESERVED")
                dispositions.append(disposition)
                meaningful.append(disposition)
                continue

            existing = state.get(key)
            if existing is not None and parse_instant(change["observed_at"], "CHG-TIME", "change.observed_at") < parse_instant(existing["updated_at"], "LAMP-TIME", "lamp.updated_at"):
                dispositions.append(_disposition(change, "REJECTED", "STALE_STATE"))
                continue
            if change["operation"] in {"INVALIDATE", "DEACTIVATE"}:
                if existing is None:
                    dispositions.append(_disposition(change, "REJECTED", "TARGET_NOT_ACTIVE"))
                    continue
                state.pop(key)
                disposition = _disposition(change, "APPLIED", "STATE_DEACTIVATED")
                dispositions.append(disposition)
                meaningful.append(disposition)
                continue
            if existing is not None and existing["value"] != change["value"]:
                if change.get("supersedes") == existing["lamp_id"] or change["operation"] == "SUPERSEDE":
                    state[key] = _lamp_from_change(change)
                    disposition = _disposition(change, "APPLIED", "EXPLICIT_SUPERSESSION")
                else:
                    conflicts[conflict_id] = _open_conflict(existing, change)
                    state.pop(key)
                    disposition = _disposition(change, "DISPUTED", "CONFLICT_PRESERVED")
                dispositions.append(disposition)
                meaningful.append(disposition)
                continue
            if existing is not None and existing["value"] == change["value"]:
                merged = copy.deepcopy(existing)
                merged["source_ids"] = sorted(set(merged["source_ids"] + change["source_ids"]))
                state[key] = merged
                dispositions.append(_disposition(change, "IGNORED", "NO_NEW_MEANING_SOURCE_MERGED"))
                continue
            state[key] = _lamp_from_change(change)
            disposition = _disposition(change, "APPLIED", "AUTHORIZED_MEANINGFUL_CHANGE")
            dispositions.append(disposition)
            meaningful.append(disposition)

        unknowns = _critical_unknowns(receipt_list, base["unknowns"])
        open_conflicts = sorted((item for item in conflicts.values() if item["status"] == "DISPUTED"), key=lambda item: item["conflict_id"])
        retained_conflicts = sorted(conflicts.values(), key=lambda item: item["conflict_id"])
        voltage, next_step = _choose_next_step(open_conflicts, unknowns, receipt_list, sources)
        failed_material = sorted((item for item in receipt_list if item["status"] == "FAIL" and item["material"]), key=lambda item: item["receipt_id"])
        if failed_material:
            city_position = failed_material[0]["summary"]
            position_sources = failed_material[0]["source_ids"]
        else:
            city_position = base["city_position"]
            position_sources = [source_id for pointer in base["source_pointers"] for source_id in [pointer["source_id"]]]

        referenced_sources = set(position_sources + next_step["source_ids"])
        for lamp in state.values():
            referenced_sources.update(lamp["source_ids"])
        for conflict in retained_conflicts:
            for claim in conflict["claims"]:
                referenced_sources.update(claim["source_ids"])
        for unknown in unknowns:
            referenced_sources.update(unknown["source_ids"])

        checkpoint_payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "checkpoint_id": "pending",
            "created_at": as_of,
            "last_sequence": last_sequence,
            "city_position": city_position,
            "city_position_source_ids": sorted(set(position_sources)),
            "active_lamps": sorted(state.values(), key=lambda item: (item["type"], item["subject"])),
            "recent_changes": meaningful,
            "conflicts": retained_conflicts,
            "unknowns": unknowns,
            "voltage": voltage,
            "primary_next_step": next_step,
            "source_pointers": _source_pointers(referenced_sources, sources),
        }
        checkpoint_payload["checkpoint_id"] = f"cp:{sha256_hex({key: value for key, value in checkpoint_payload.items() if key != 'checkpoint_id'})[:16]}"
        checkpoint = seal_checkpoint(checkpoint_payload)
        recovery_card = _derive_recovery_card(checkpoint)
        executed_untrusted = any(item["reason"] == "IMPORTED_TEXT_IS_DATA_NOT_INSTRUCTION" and item["status"] != "IGNORED" for item in dispositions)
        checks = {
            "checkpoint_integrity": verify_checkpoint_integrity(checkpoint),
            "exactly_one_next_step": isinstance(checkpoint["primary_next_step"], dict) and bool(checkpoint["primary_next_step"]),
            "recovery_card_non_authoritative": recovery_card["source_of_truth"] is False and recovery_card["write_back_allowed"] is False,
            "untrusted_instruction_not_executed": not executed_untrusted,
            "material_outputs_have_sources": bool(checkpoint["city_position_source_ids"]) and bool(checkpoint["primary_next_step"]["source_ids"]),
        }
        run_status = "PASS" if all(checks.values()) else "FAIL"
        return {
            "schema_version": SCHEMA_VERSION,
            "package_id": package_id,
            "execution_mode": "LOCAL_DETERMINISTIC_NO_MODEL_CALLS",
            "base_checkpoint": {
                "checkpoint_id": base_checkpoint_id,
                "status": recovery_status,
                "rejected_candidates": checkpoint_errors,
            },
            "intake": dispositions,
            "checkpoint": checkpoint,
            "recovery_card": recovery_card,
            "source_evidence": [sources[source_id] for source_id in sorted(sources)],
            "validation_receipts": sorted(receipt_list, key=lambda item: item["receipt_id"]),
            "run_receipt": {
                "receipt_id": f"run:{checkpoint['checkpoint_id']}",
                "scope": "ORIENTATION_TRANSFORM_ONLY",
                "status": run_status,
                "checks": checks,
                "claim_limit": "This receipt does not claim project completion or repair imported validation failures.",
            },
        }
    except (ContractError, TypeError) as exc:
        raise OrientationError(str(exc)) from exc


def evaluate_success_condition(result: dict[str, Any], condition: dict[str, Any]) -> bool:
    """Evaluate the closed, machine-verifiable success-condition vocabulary."""

    condition_type = condition.get("type")
    checkpoint = result.get("checkpoint", {})
    if condition_type == "conflict_resolved":
        subject = condition.get("subject")
        authority = condition.get("required_authority")
        open_conflict = any(item.get("subject") == subject and item.get("status") == "DISPUTED" for item in checkpoint.get("conflicts", []))
        active = any(item.get("subject") == subject and item.get("authority") == authority for item in checkpoint.get("active_lamps", []))
        return not open_conflict and active
    if condition_type == "unknown_resolved":
        subject = condition.get("subject")
        return not any(item.get("subject") == subject for item in checkpoint.get("unknowns", []))
    if condition_type == "validation_pass":
        subject = condition.get("subject")
        return any(item.get("subject") == subject and item.get("status") == "PASS" for item in result.get("validation_receipts", []))
    if condition_type == "validation_receipt_retained":
        return any(item.get("status") == condition.get("status") for item in result.get("validation_receipts", []))
    return False
