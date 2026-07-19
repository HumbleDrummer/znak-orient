"""Deterministic X30 memory-orientation reducer."""

from __future__ import annotations

import copy
from typing import Any, Iterable

from .canonical import canonical_json_bytes, seal_checkpoint, sha256_hex, verify_checkpoint_integrity
from .contracts import (
    AUTHORITIES,
    CONTENT_TYPES,
    EPISTEMIC_STATES,
    OPERATIONS,
    SCHEMA_VERSION,
    STATE_CHANGE_IMPACTS,
    STATE_CHANGE_OPERATION_IMPACTS,
    TRUSTED_AUTHORITY_SOURCE_KINDS,
    TRUSTED_VALIDATOR_IDS,
    ContractError,
    normalize_change,
    parse_instant,
    require,
    require_closed_keys,
    require_list,
    require_mapping,
    require_text,
    semantic_fingerprint,
    validate_receipt,
    validate_source,
)


class OrientationError(ValueError):
    """Raised when no safe deterministic orientation can be produced."""


VOLTAGES = {"FLOWING", "WEAK", "BLOCKED", "BROKEN", "UNKNOWN"}
POLICY_CLASSES = {
    "CORRECTIVE_CONFLICT_RESOLUTION",
    "CORRECTIVE_CONSTRAINT_RESOLUTION",
    "CORRECTIVE_EVIDENCE_COLLECTION",
    "CORRECTIVE_RISK_MITIGATION",
    "CORRECTIVE_VALIDATION",
    "GOAL_VALIDATION",
}
FORBIDDABLE_POLICY_CLASSES = POLICY_CLASSES - {"CORRECTIVE_CONSTRAINT_RESOLUTION"}
KNOWN_CONSTRAINT_LITERALS = {
    "LOCAL_ONLY",
    "LOCAL_ONLY_NO_EXTERNAL_APIS",
    "REQUIRES_SEPARATE_USER_CONFIRMATION",
}
SUCCESS_CONDITION_TYPES = {
    "constraint_policy_allows",
    "conflict_resolved",
    "risk_mitigated",
    "unknown_resolved",
    "validation_pass",
    "validation_receipt_retained",
}
_IMPACT_REASONS = {
    "STATE_ACTIVATED": "AUTHORIZED_MEANINGFUL_CHANGE",
    "STATE_REPLACED": "EXPLICIT_SUPERSESSION",
    "STATE_DEACTIVATED": "STATE_DEACTIVATED",
    "STATE_METADATA_UPDATED": "STATE_METADATA_UPDATED",
    "EVIDENCE_EXTENDED": "CORROBORATING_SOURCE_MERGED",
    "CONFLICT_OPENED": "CONFLICT_PRESERVED",
    "CONFLICT_EXTENDED": "CONFLICT_PRESERVED",
    "CONFLICT_RESOLVED": "AUTHORIZED_CONFLICT_RESOLUTION",
}
_LEGACY_RECENT_CHANGE_FIELDS = {
    "change_id",
    "sequence",
    "object_type",
    "content_type",
    "subject",
    "status",
    "reason",
    "source_ids",
    "observed_at",
    "operation",
    "epistemic",
    "authority",
    "material",
    "meaning",
    "before",
    "after",
}
_CURRENT_RECENT_CHANGE_FIELDS = _LEGACY_RECENT_CHANGE_FIELDS | {"impact"}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _same_value(left: Any, right: Any) -> bool:
    try:
        return sha256_hex(left) == sha256_hex(right)
    except TypeError:
        return False


def _lamp_snapshot_matches_change(
    change: dict[str, Any], lamp: Any, *, bind_to_meaning: bool
) -> bool:
    if not isinstance(lamp, dict):
        return False
    required = {
        "lamp_id",
        "type",
        "subject",
        "value",
        "epistemic",
        "authority",
        "source_ids",
        "updated_at",
        "material",
    }
    if not required.issubset(lamp) or not set(lamp).issubset(
        required | {"validation_receipt_id"}
    ):
        return False
    if (
        lamp.get("lamp_id")
        != f"lamp:{change.get('content_type', '').lower()}:{change.get('subject', '')}"
        or lamp.get("type") != change.get("content_type")
        or lamp.get("subject") != change.get("subject")
    ):
        return False
    if not bind_to_meaning:
        return True
    return (
        _same_value(lamp.get("value"), change.get("meaning"))
        and lamp.get("epistemic") == change.get("epistemic")
        and lamp.get("authority") == change.get("authority")
        and lamp.get("material") == change.get("material")
        and lamp.get("updated_at") == change.get("observed_at")
        and isinstance(lamp.get("source_ids"), list)
        and set(change.get("source_ids", [])).issubset(lamp["source_ids"])
    )


def _conflict_snapshot_matches_change(
    change: dict[str, Any], conflict: Any, *, status: str
) -> bool:
    if not isinstance(conflict, dict):
        return False
    required = {
        "conflict_id",
        "type",
        "subject",
        "material",
        "status",
        "classification",
        "reason",
        "claims",
    }
    return (
        required.issubset(conflict)
        and set(conflict).issubset(
            required | {"resolution_history", "resolution_change_id"}
        )
        and conflict.get("conflict_id")
        == f"conflict:{change.get('content_type', '').lower()}:{change.get('subject', '')}"
        and conflict.get("type") == change.get("content_type")
        and conflict.get("subject") == change.get("subject")
        and conflict.get("status") == status
        and isinstance(conflict.get("claims"), list)
    )


def _claim_matches_change(change: dict[str, Any], claim: Any) -> bool:
    return (
        isinstance(claim, dict)
        and claim.get("claim_id") == change.get("change_id")
        and _same_value(claim.get("value"), change.get("meaning"))
        and claim.get("epistemic") == "DISPUTED"
        and claim.get("asserted_epistemic") == change.get("epistemic")
        and claim.get("authority") == change.get("authority")
        and claim.get("observed_at") == change.get("observed_at")
        and isinstance(claim.get("source_ids"), list)
        and set(change.get("source_ids", [])).issubset(claim["source_ids"])
    )


def _claim_matches_lamp(claim: Any, lamp: dict[str, Any]) -> bool:
    return (
        isinstance(claim, dict)
        and claim.get("claim_id") == lamp.get("lamp_id")
        and _same_value(claim.get("value"), lamp.get("value"))
        and claim.get("epistemic") == "DISPUTED"
        and claim.get("asserted_epistemic") == lamp.get("epistemic")
        and claim.get("authority") == lamp.get("authority")
        and claim.get("source_ids") == lamp.get("source_ids")
        and claim.get("observed_at") == lamp.get("updated_at")
    )


def _recent_change_impact_is_consistent(change: dict[str, Any]) -> bool:
    impact = change.get("impact")
    operation = change.get("operation")
    before = change.get("before")
    after = change.get("after")
    if (
        impact not in STATE_CHANGE_IMPACTS
        or impact not in STATE_CHANGE_OPERATION_IMPACTS.get(operation, set())
        or change.get("reason") != _IMPACT_REASONS[impact]
    ):
        return False
    if impact == "STATE_ACTIVATED":
        return (
            change.get("status") == "APPLIED"
            and before is None
            and _lamp_snapshot_matches_change(change, after, bind_to_meaning=True)
        )
    if impact == "STATE_DEACTIVATED":
        return (
            change.get("status") == "APPLIED"
            and _lamp_snapshot_matches_change(change, before, bind_to_meaning=False)
            and _same_value(before.get("value"), change.get("meaning"))
            and after is None
        )
    if impact == "STATE_REPLACED":
        return (
            change.get("status") == "APPLIED"
            and _lamp_snapshot_matches_change(change, before, bind_to_meaning=False)
            and _lamp_snapshot_matches_change(change, after, bind_to_meaning=True)
            and before.get("lamp_id") == after.get("lamp_id")
        )
    if impact in {"STATE_METADATA_UPDATED", "EVIDENCE_EXTENDED"}:
        if not (
            change.get("status") == "APPLIED"
            and _lamp_snapshot_matches_change(change, before, bind_to_meaning=False)
            and _lamp_snapshot_matches_change(change, after, bind_to_meaning=True)
            and before.get("lamp_id") == after.get("lamp_id")
            and _same_value(before.get("value"), after.get("value"))
        ):
            return False
        if impact == "EVIDENCE_EXTENDED":
            return (
                before.get("epistemic") == after.get("epistemic")
                and before.get("authority") == after.get("authority")
                and before.get("material") == after.get("material")
                and before.get("validation_receipt_id")
                == after.get("validation_receipt_id")
                and isinstance(before.get("source_ids"), list)
                and isinstance(after.get("source_ids"), list)
                and set(before["source_ids"]) < set(after["source_ids"])
            )
        return any(
            before.get(field) != after.get(field)
            for field in ("epistemic", "authority", "material", "validation_receipt_id")
        )
    if impact == "CONFLICT_OPENED":
        if not (
            change.get("status") == "DISPUTED"
            and _lamp_snapshot_matches_change(change, before, bind_to_meaning=False)
            and _conflict_snapshot_matches_change(change, after, status="DISPUTED")
        ):
            return False
        new_claim_is_bound = any(
            _claim_matches_change(change, claim) for claim in after["claims"]
        )
        if after.get("classification") == "CONTRADICTION_UNRESOLVED":
            return (
                len(after["claims"]) == 2
                and after.get("material")
                == bool(before.get("material") or change.get("material"))
                and any(_claim_matches_lamp(claim, before) for claim in after["claims"])
                and new_claim_is_bound
            )
        history = after.get("resolution_history")
        return (
            after.get("classification") == "CONTRADICTION_REOPENED"
            and isinstance(history, list)
            and bool(history)
            and (
                after.get("material") is True
                or not (before.get("material") or change.get("material"))
            )
            and _same_value(history[-1].get("value"), before.get("value"))
            and new_claim_is_bound
        )
    if impact == "CONFLICT_EXTENDED":
        if not (
            change.get("status") == "DISPUTED"
            and _conflict_snapshot_matches_change(change, before, status="DISPUTED")
            and _conflict_snapshot_matches_change(change, after, status="DISPUTED")
            and len(after["claims"]) == len(before["claims"]) + 1
            and all(claim in after["claims"] for claim in before["claims"])
            and all(
                before.get(field) == after.get(field)
                for field in set(before) | set(after)
                if field not in {"claims", "material"}
            )
            and after.get("material")
            == bool(before.get("material") or change.get("material"))
        ):
            return False
        return any(_claim_matches_change(change, claim) for claim in after["claims"])
    if impact == "CONFLICT_RESOLVED":
        return (
            change.get("status") == "APPLIED"
            and _conflict_snapshot_matches_change(change, before, status="DISPUTED")
            and _lamp_snapshot_matches_change(change, after, bind_to_meaning=True)
        )
    return False


def _derive_legacy_impact(change: dict[str, Any]) -> str | None:
    candidates = [
        impact
        for impact in sorted(STATE_CHANGE_IMPACTS)
        if _recent_change_impact_is_consistent({**change, "impact": impact})
    ]
    return candidates[0] if len(candidates) == 1 else None


def _fact_lamp_has_explicit_receipt_suspension(
    checkpoint: dict[str, Any],
    lamp: Any,
    receipts: dict[str, dict[str, Any]],
    *,
    suspended_by: str | None = None,
) -> bool:
    if not isinstance(lamp, dict) or lamp.get("type") != "FACT":
        return False
    receipt_id = lamp.get("validation_receipt_id")
    proof_receipt = receipts.get(receipt_id) if _text(receipt_id) else None
    receipt_pointers = {
        pointer.get("receipt_id"): pointer
        for pointer in checkpoint.get("validation_receipt_pointers", [])
        if isinstance(pointer, dict) and _text(pointer.get("receipt_id"))
    }
    retained_pointer = receipt_pointers.get(receipt_id)
    if (
        not _text(receipt_id)
        or proof_receipt is None
        or not _receipt_is_trusted_pass(proof_receipt)
        or proof_receipt.get("subject") != lamp.get("subject")
        or proof_receipt.get("assertion_sha256")
        != _assertion_hash(lamp.get("subject"), lamp.get("value"))
        or not set(proof_receipt.get("source_ids", [])).issubset(
            lamp.get("source_ids", [])
        )
        or retained_pointer is None
        or retained_pointer.get("subject") != lamp.get("subject")
    ):
        return False
    conflict_subject = f"validation.{lamp.get('subject', '')}"
    receipt_conflict = next(
        (
            conflict
            for conflict in checkpoint.get("conflicts", [])
            if isinstance(conflict, dict)
            and conflict.get("conflict_id") == f"conflict:fact:{conflict_subject}"
            and conflict.get("type") == "FACT"
            and conflict.get("subject") == conflict_subject
            and conflict.get("classification") == "CONTRADICTORY_VALIDATION_RECEIPTS"
        ),
        None,
    )
    if receipt_conflict is None:
        return False
    suspended_claim = {
        "claim_id": lamp.get("lamp_id"),
        "value": {
            "fact_subject": lamp.get("subject"),
            "fact_value": copy.deepcopy(lamp.get("value")),
            "validation_receipt_id": receipt_id,
        },
        "epistemic": "DISPUTED",
        "asserted_epistemic": lamp.get("epistemic"),
        "authority": lamp.get("authority"),
        "source_ids": lamp.get("source_ids"),
        "observed_at": lamp.get("updated_at"),
    }
    claims = receipt_conflict.get("claims", [])
    if suspended_claim not in claims:
        return False
    try:
        lamp_time = parse_instant(
            lamp.get("updated_at"), "CP-LAMP-TIME", "lamp.updated_at"
        )
        if parse_instant(
            proof_receipt.get("checked_at"),
            "CP-RECEIPT-TIME",
            "receipt.checked_at",
        ) > lamp_time:
            return False
        suspension_deadline = (
            parse_instant(suspended_by, "CP-CHANGE-TIME", "change.observed_at")
            if suspended_by is not None
            else None
        )
        return any(
            claim.get("claim_id") in receipts
            and receipts[claim["claim_id"]].get("validator_id")
            in TRUSTED_VALIDATOR_IDS
            and receipts[claim["claim_id"]].get("subject")
            == lamp.get("subject")
            and _receipt_claim_identity(receipts[claim["claim_id"]])
            != _receipt_claim_identity(proof_receipt)
            and parse_instant(
                claim.get("observed_at"), "CP-CLAIM-TIME", "claim.observed_at"
            )
            > lamp_time
            and (
                suspension_deadline is None
                or parse_instant(
                    claim.get("observed_at"),
                    "CP-CLAIM-TIME",
                    "claim.observed_at",
                )
                <= suspension_deadline
            )
            for claim in claims
            if isinstance(claim, dict)
        )
    except ContractError:
        return False


def _recent_change_chain_is_continuous(
    checkpoint: dict[str, Any], receipts: dict[str, dict[str, Any]]
) -> bool:
    previous_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for change in checkpoint.get("recent_changes", []):
        key = (change["content_type"], change["subject"])
        previous = previous_by_key.get(key)
        if previous is not None and previous["after"] != change["before"]:
            receipt_suspended_between_changes = (
                key[0] == "FACT"
                and change["before"] is None
                and _fact_lamp_has_explicit_receipt_suspension(
                    checkpoint,
                    previous.get("after"),
                    receipts,
                    suspended_by=change["observed_at"],
                )
            )
            if not receipt_suspended_between_changes:
                return False
        previous_by_key[key] = change
    return True


def _latest_recent_changes_match_projection(
    checkpoint: dict[str, Any], receipts: dict[str, dict[str, Any]]
) -> bool:
    recent_changes = checkpoint.get("recent_changes", [])
    ordered = [(change["sequence"], change["change_id"]) for change in recent_changes]
    if ordered != sorted(ordered):
        return False
    latest_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for change in recent_changes:
        latest_by_key[(change["content_type"], change["subject"])] = change
    lamps = {
        (lamp["type"], lamp["subject"]): lamp
        for lamp in checkpoint.get("active_lamps", [])
    }
    conflicts = {
        (conflict["type"], conflict["subject"]): conflict
        for conflict in checkpoint.get("conflicts", [])
    }
    for key, change in latest_by_key.items():
        impact = change["impact"]
        lamp = lamps.get(key)
        conflict = conflicts.get(key)
        if impact in {
            "STATE_ACTIVATED",
            "STATE_REPLACED",
            "STATE_METADATA_UPDATED",
            "EVIDENCE_EXTENDED",
        }:
            receipt_suspended = (
                key[0] == "FACT"
                and lamp is None
                and conflict is None
                and _fact_lamp_has_explicit_receipt_suspension(
                    checkpoint, change["after"], receipts
                )
            )
            if not receipt_suspended and (
                lamp != change["after"] or conflict is not None
            ):
                return False
        elif impact == "STATE_DEACTIVATED":
            if lamp is not None or conflict is not None:
                return False
        elif impact in {"CONFLICT_OPENED", "CONFLICT_EXTENDED"}:
            if lamp is not None or conflict != change["after"]:
                return False
        elif impact == "CONFLICT_RESOLVED":
            history = conflict.get("resolution_history") if isinstance(conflict, dict) else None
            receipt_suspended = (
                key[0] == "FACT"
                and lamp is None
                and _fact_lamp_has_explicit_receipt_suspension(
                    checkpoint, change["after"], receipts
                )
            )
            if (
                (not receipt_suspended and lamp != change["after"])
                or not isinstance(conflict, dict)
                or conflict.get("status") != "RESOLVED"
                or conflict.get("resolution_change_id") != change["change_id"]
                or not isinstance(history, list)
                or not history
                or history[-1].get("change_id") != change["change_id"]
                or not _same_value(history[-1].get("value"), change["meaning"])
            ):
                return False
        else:
            return False
    return True


def _checkpoint_integrity_shape_is_valid(checkpoint: dict[str, Any]) -> bool:
    integrity = checkpoint.get("integrity")
    return (
        isinstance(integrity, dict)
        and set(integrity) == {"algorithm", "value"}
        and integrity.get("algorithm") == "sha256"
        and isinstance(integrity.get("value"), str)
        and len(integrity["value"]) == 64
        and all(character in "0123456789abcdef" for character in integrity["value"])
    )


def _prepare_checkpoint_candidate(
    checkpoint: Any,
) -> tuple[Any, bool, str | None]:
    candidate = copy.deepcopy(checkpoint)
    if not isinstance(candidate, dict) or not _checkpoint_integrity_shape_is_valid(candidate):
        return candidate, False, None
    try:
        if not verify_checkpoint_integrity(candidate):
            return candidate, False, None
    except TypeError:
        return candidate, False, None
    recent_changes = candidate.get("recent_changes")
    if not isinstance(recent_changes, list) or not recent_changes:
        return candidate, False, None
    shapes = [set(change) if isinstance(change, dict) else set() for change in recent_changes]
    if all(shape == _CURRENT_RECENT_CHANGE_FIELDS for shape in shapes):
        return candidate, False, None
    if not all(shape == _LEGACY_RECENT_CHANGE_FIELDS for shape in shapes):
        return candidate, False, None
    migrated = copy.deepcopy(candidate)
    for change in migrated["recent_changes"]:
        impact = _derive_legacy_impact(change)
        if impact is None:
            return (
                candidate,
                False,
                "legacy checkpoint impact is not unambiguously derivable",
            )
        change["impact"] = impact
    return seal_checkpoint(migrated), True, None


def _assertion_hash(subject: str, value: Any) -> str:
    return sha256_hex({"subject": subject, "value": value})


def _receipt_is_trusted_pass(receipt: dict[str, Any]) -> bool:
    checks = receipt.get("checks")
    return (
        receipt.get("status") == "PASS"
        and receipt.get("validator_id") in TRUSTED_VALIDATOR_IDS
        and isinstance(checks, list)
        and bool(checks)
        and all(isinstance(check, dict) and check.get("status") == "PASS" for check in checks)
        and _text(receipt.get("assertion_sha256"))
    )


def _receipt_claim_identity(receipt: dict[str, Any]) -> tuple[str, str, str]:
    # The human-readable summary is itself consumed as the canonical city
    # position. Two receipts that bind the same assertion but describe its
    # outcome differently therefore remain incompatible claims; silently
    # choosing one summary would turn ambiguous evidence into orientation.
    return receipt["status"], receipt.get("assertion_sha256", ""), receipt["summary"]


def _receipt_claim_value(receipt: dict[str, Any]) -> dict[str, str]:
    return {
        "status": receipt["status"],
        "summary": receipt["summary"],
        "assertion_sha256": receipt["assertion_sha256"],
    }


def _receipt_conflict_claim(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": receipt["receipt_id"],
        "value": _receipt_claim_value(receipt),
        "epistemic": "DISPUTED",
        "asserted_epistemic": "VERIFIED",
        "authority": "NOT_APPLICABLE",
        "source_ids": list(receipt["source_ids"]),
        "observed_at": receipt["checked_at"],
    }


def _receipt_resolution_selection(
    receipt: dict[str, Any],
    conflicts: Iterable[dict[str, Any]],
    active_lamps: Iterable[dict[str, Any]],
) -> str:
    """Return NO_CONFLICT, OPEN, SELECTED, or NOT_SELECTED for a proof receipt."""

    conflict_subject = f"validation.{receipt['subject']}"
    matching = [
        conflict
        for conflict in conflicts
        if conflict.get("classification") == "CONTRADICTORY_VALIDATION_RECEIPTS"
        and conflict.get("type") == "FACT"
        and conflict.get("subject") == conflict_subject
    ]
    if not matching:
        return "NO_CONFLICT"
    if len(matching) != 1 or matching[0].get("status") != "RESOLVED":
        return "OPEN"
    selected = [
        lamp
        for lamp in active_lamps
        if lamp.get("type") == "FACT" and lamp.get("subject") == conflict_subject
    ]
    if len(selected) != 1:
        return "OPEN"
    return (
        "SELECTED"
        if sha256_hex(selected[0].get("value")) == sha256_hex(_receipt_claim_value(receipt))
        else "NOT_SELECTED"
    )


def _constraint_value_is_valid(value: Any) -> bool:
    if isinstance(value, str):
        return value in KNOWN_CONSTRAINT_LITERALS
    if not isinstance(value, dict) or set(value) != {"forbidden_policy_classes"}:
        return False
    forbidden = value["forbidden_policy_classes"]
    return (
        isinstance(forbidden, list)
        and bool(forbidden)
        and len(forbidden) == len(set(forbidden))
        and all(item in FORBIDDABLE_POLICY_CLASSES for item in forbidden)
    )


def _constraint_forbids(value: Any, policy_class: str) -> bool:
    return isinstance(value, dict) and policy_class in value.get("forbidden_policy_classes", [])


def _source_id_list(value: Any, known_sources: set[str], *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(_text(item) and item in known_sources for item in value)
        and len(value) == len(set(value))
    )


def _success_condition_is_valid(value: Any) -> bool:
    if not isinstance(value, dict) or value.get("type") not in SUCCESS_CONDITION_TYPES:
        return False
    condition_type = value["type"]
    if condition_type == "conflict_resolved":
        return (
            set(value) == {"type", "subject", "content_type", "required_authority"}
            and _text(value.get("subject"))
            and value.get("content_type") in CONTENT_TYPES
            and value.get("required_authority") == "AUTHORIZED"
        )
    if condition_type == "constraint_policy_allows":
        return (
            set(value) == {"type", "subject", "policy_class"}
            and _text(value.get("subject"))
            and value.get("policy_class") in POLICY_CLASSES
        )
    if condition_type in {"risk_mitigated", "unknown_resolved"}:
        return set(value) == {"type", "subject"} and _text(value.get("subject"))
    if set(value) != {"type", "status", "subject", "checked_after", "assertion_sha256"}:
        return False
    assertion_sha256 = value.get("assertion_sha256")
    if (
        value.get("status") != "PASS"
        or not _text(value.get("subject"))
        or not isinstance(assertion_sha256, str)
        or len(assertion_sha256) != 64
        or any(character not in "0123456789abcdef" for character in assertion_sha256)
    ):
        return False
    try:
        parse_instant(value.get("checked_after"), "STEP-TIME", "success_condition.checked_after")
    except ContractError:
        return False
    return True


def _next_step_is_valid(value: Any, known_sources: set[str]) -> bool:
    if not isinstance(value, dict):
        return False
    allowed_keys = {
        "action_id",
        "constraints",
        "goal",
        "instruction",
        "policy_class",
        "reason",
        "source_ids",
        "success_condition",
    }
    if not set(value).issubset(allowed_keys):
        return False
    if not all(_text(value.get(field)) for field in ("action_id", "instruction", "reason")):
        return False
    if value.get("policy_class") not in POLICY_CLASSES:
        return False
    if not _source_id_list(value.get("source_ids"), known_sources):
        return False
    if not _success_condition_is_valid(value.get("success_condition")):
        return False
    goal = value.get("goal")
    if goal is not None and (
        not isinstance(goal, dict)
        or set(goal) != {"subject", "source_ids"}
        or not _text(goal.get("subject"))
        or not _source_id_list(goal.get("source_ids"), known_sources)
    ):
        return False
    constraints = value.get("constraints", [])
    if not isinstance(constraints, list):
        return False
    if len(constraints) != len({item.get("subject") for item in constraints if isinstance(item, dict)}):
        return False
    return all(
        isinstance(item, dict)
        and set(item) == {"subject", "value", "source_ids"}
        and _text(item.get("subject"))
        and _constraint_value_is_valid(item.get("value"))
        and _source_id_list(item.get("source_ids"), known_sources)
        for item in constraints
    )


def _checkpoint_is_semantically_valid(
    checkpoint: Any,
    as_of: str,
    sources: dict[str, dict[str, Any]],
    receipts: dict[str, dict[str, Any]],
) -> tuple[bool, str]:
    if not isinstance(checkpoint, dict):
        return False, "checkpoint is not an object"
    required_checkpoint_fields = {
        "schema_version",
        "checkpoint_id",
        "created_at",
        "last_sequence",
        "city_position",
        "city_position_source_ids",
        "active_lamps",
        "recent_changes",
        "conflicts",
        "unknowns",
        "voltage",
        "primary_next_step",
        "source_pointers",
        "validation_receipt_pointers",
        "integrity",
    }
    if set(checkpoint) != required_checkpoint_fields:
        return False, "checkpoint top-level shape is not closed"
    if not _checkpoint_integrity_shape_is_valid(checkpoint):
        return False, "checkpoint integrity shape is not closed"
    if checkpoint.get("schema_version") != SCHEMA_VERSION:
        return False, "unsupported checkpoint schema"
    try:
        if not verify_checkpoint_integrity(checkpoint):
            return False, "checkpoint integrity mismatch"
        created_at = parse_instant(checkpoint.get("created_at"), "CP-001", "checkpoint.created_at")
        as_of_instant = parse_instant(as_of, "CP-002", "package.as_of")
    except (ContractError, TypeError) as exc:
        return False, str(exc)
    if created_at > as_of_instant:
        return False, "checkpoint is from the future"
    if not _text(checkpoint.get("checkpoint_id")) or not _text(checkpoint.get("city_position")):
        return False, "checkpoint identity or city position is invalid"
    last_sequence = checkpoint.get("last_sequence")
    if not isinstance(last_sequence, int) or isinstance(last_sequence, bool) or last_sequence < 0:
        return False, "checkpoint.last_sequence is invalid"
    for field in ("active_lamps", "recent_changes", "conflicts", "unknowns", "source_pointers"):
        if not isinstance(checkpoint.get(field), list):
            return False, f"checkpoint.{field} must be an array"
    known_source_ids = set(sources)
    if not _source_id_list(checkpoint.get("city_position_source_ids"), known_source_ids):
        return False, "checkpoint city-position sources are unresolved"
    eligible_position_sources = {
        source_id
        for source_id, source in sources.items()
        if source["kind"] == "CHECKPOINT" and source["authority"] == "AUTHORIZED"
    }
    checkpoint_receipts = [
        receipt
        for receipt in receipts.values()
        if receipt["validator_id"] in TRUSTED_VALIDATOR_IDS
        and parse_instant(receipt["checked_at"], "CP-RECEIPT-TIME", "receipt.checked_at") <= created_at
    ]
    receipt_pointers = checkpoint["validation_receipt_pointers"]
    if not isinstance(receipt_pointers, list):
        return False, "checkpoint validation receipt pointers must be an array"
    receipt_pointer_by_id: dict[str, dict[str, Any]] = {}
    for pointer in receipt_pointers:
        if (
            not isinstance(pointer, dict)
            or set(pointer)
            != {"receipt_id", "receipt_sha256", "subject", "checked_at", "source_ids"}
            or not _text(pointer.get("receipt_id"))
            or not _text(pointer.get("subject"))
            or not isinstance(pointer.get("receipt_sha256"), str)
            or len(pointer["receipt_sha256"]) != 64
            or any(character not in "0123456789abcdef" for character in pointer["receipt_sha256"])
            or not _source_id_list(pointer.get("source_ids"), known_source_ids)
        ):
            return False, "checkpoint validation receipt pointer is invalid"
        receipt_id = pointer["receipt_id"]
        if receipt_id in receipt_pointer_by_id:
            return False, "checkpoint validation receipt pointer is duplicated"
        try:
            checked_at = parse_instant(
                pointer["checked_at"], "CP-RECEIPT-TIME", "validation_receipt_pointer.checked_at"
            )
        except ContractError as exc:
            return False, str(exc)
        if checked_at > created_at or any(
            parse_instant(sources[source_id]["captured_at"], "CP-SOURCE-TIME", "source.captured_at")
            > checked_at
            for source_id in pointer["source_ids"]
        ):
            return False, "checkpoint validation receipt pointer has impossible chronology"
        current_receipt = receipts.get(receipt_id)
        if current_receipt is not None:
            if sha256_hex(current_receipt) != pointer["receipt_sha256"]:
                return False, f"RECEIPT_ID_REUSE:{receipt_id} changed after checkpointing"
            if (
                current_receipt["subject"] != pointer["subject"]
                or current_receipt["checked_at"] != pointer["checked_at"]
                or current_receipt["source_ids"] != pointer["source_ids"]
            ):
                return False, f"RECEIPT_ID_REUSE:{receipt_id} pointer metadata changed"
        receipt_pointer_by_id[receipt_id] = pointer
    if any(
        receipt["receipt_id"] not in receipt_pointer_by_id for receipt in checkpoint_receipts
    ):
        return False, "checkpoint validation receipt pointers do not cover retained receipts"
    checkpoint_receipt_claims: dict[str, set[tuple[str, str, str]]] = {}
    for receipt in checkpoint_receipts:
        checkpoint_receipt_claims.setdefault(receipt["subject"], set()).add(_receipt_claim_identity(receipt))
    disputed_checkpoint_receipt_subjects = {
        subject for subject, identities in checkpoint_receipt_claims.items() if len(identities) > 1
    }
    for receipt in checkpoint_receipts:
        if (
            receipt["subject"] not in disputed_checkpoint_receipt_subjects
            and receipt["status"] in {"PASS", "FAIL"}
            and receipt["material"]
            and receipt["summary"] == checkpoint["city_position"]
        ):
            eligible_position_sources.update(receipt["source_ids"])
    if checkpoint.get("voltage") not in VOLTAGES:
        return False, "checkpoint.voltage is invalid"
    if not _next_step_is_valid(checkpoint.get("primary_next_step"), known_source_ids):
        return False, "checkpoint.primary_next_step is invalid"

    lamps = checkpoint["active_lamps"]
    lamp_ids: set[str] = set()
    lamp_keys: set[tuple[str, str]] = set()
    lamp_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for lamp in lamps:
        if not isinstance(lamp, dict):
            return False, "checkpoint lamp is not an object"
        required_lamp_fields = {
            "lamp_id",
            "type",
            "subject",
            "value",
            "epistemic",
            "authority",
            "source_ids",
            "updated_at",
            "material",
        }
        if not required_lamp_fields.issubset(lamp) or not set(lamp).issubset(
            required_lamp_fields | {"validation_receipt_id"}
        ):
            return False, "checkpoint lamp shape is not closed"
        lamp_id, lamp_type, subject = lamp.get("lamp_id"), lamp.get("type"), lamp.get("subject")
        if not _text(lamp_id) or lamp_type not in CONTENT_TYPES or not _text(subject) or "value" not in lamp:
            return False, "checkpoint lamp identity is invalid"
        if lamp_id != f"lamp:{lamp_type.lower()}:{subject}":
            return False, "checkpoint lamp ID does not match its type and subject"
        if lamp_id in lamp_ids or (lamp_type, subject) in lamp_keys:
            return False, "checkpoint contains duplicate lamps"
        lamp_ids.add(lamp_id)
        lamp_keys.add((lamp_type, subject))
        lamp_by_key[(lamp_type, subject)] = lamp
        if lamp.get("epistemic") not in EPISTEMIC_STATES or lamp.get("epistemic") == "DISPUTED":
            return False, "checkpoint contains an action-driving disputed lamp"
        if lamp.get("authority") not in AUTHORITIES or not isinstance(lamp.get("material"), bool):
            return False, "checkpoint lamp policy fields are invalid"
        if not _source_id_list(lamp.get("source_ids"), known_source_ids):
            return False, "checkpoint lamp sources are unresolved"
        lamp_sources = [sources[source_id] for source_id in lamp["source_ids"]]
        try:
            lamp_updated_at = parse_instant(lamp.get("updated_at"), "CP-LAMP-TIME", "lamp.updated_at")
        except ContractError as exc:
            return False, str(exc)
        if lamp_updated_at > created_at:
            return False, "checkpoint lamp is newer than the checkpoint"
        if any(
            parse_instant(source["captured_at"], "CP-SOURCE-TIME", "source.captured_at") > lamp_updated_at
            for source in lamp_sources
        ):
            return False, "checkpoint lamp source postdates the lamp"
        receipt = None
        if "validation_receipt_id" in lamp:
            if lamp_type != "FACT":
                return False, "checkpoint non-FACT lamp cannot retain a validation receipt"
            receipt_id = lamp.get("validation_receipt_id")
            if not _text(receipt_id) or receipt_id not in receipts:
                return False, "checkpoint lamp validation receipt is unresolved"
            receipt = receipts[receipt_id]
            if receipt["subject"] != subject or not set(receipt["source_ids"]).issubset(lamp["source_ids"]):
                return False, "checkpoint lamp validation receipt provenance is inconsistent"
            if parse_instant(
                receipt["checked_at"], "CP-RECEIPT-TIME", "receipt.checked_at"
            ) > lamp_updated_at:
                return False, "checkpoint lamp validation receipt postdates the lamp"
        if lamp_type in {"GOAL", "DECISION", "CONSTRAINT"}:
            if lamp["authority"] != "AUTHORIZED":
                return False, "checkpoint authority-driving lamp is not authorized"
            if any(
                source["authority"] != "AUTHORIZED" or source["kind"] not in TRUSTED_AUTHORITY_SOURCE_KINDS
                for source in lamp_sources
            ):
                return False, "checkpoint authority-driving lamp has an untrusted source"
        if lamp_type == "GOAL" and not lamp["material"]:
            return False, "checkpoint goal must be material"
        if lamp_type == "CONSTRAINT" and not _constraint_value_is_valid(lamp["value"]):
            return False, "checkpoint constraint policy is unsupported"
        if lamp_type == "FACT":
            if (
                lamp["epistemic"] != "VERIFIED"
                or receipt is None
                or not _receipt_is_trusted_pass(receipt)
                or receipt["subject"] != subject
                or receipt["assertion_sha256"] != _assertion_hash(subject, lamp["value"])
                or not set(receipt["source_ids"]).issubset(lamp["source_ids"])
            ):
                return False, "checkpoint fact lamp lacks a value-bound trusted PASS receipt"
    goal_lamps = sorted((lamp for lamp in lamps if lamp["type"] == "GOAL"), key=lambda item: item["subject"])

    conflict_ids: set[str] = set()
    for conflict in checkpoint["conflicts"]:
        if not isinstance(conflict, dict) or not _text(conflict.get("conflict_id")):
            return False, "checkpoint conflict is invalid"
        required_conflict_fields = {
            "conflict_id",
            "type",
            "subject",
            "material",
            "status",
            "classification",
            "reason",
            "claims",
        }
        if not required_conflict_fields.issubset(conflict) or not set(conflict).issubset(
            required_conflict_fields | {"resolution_history", "resolution_change_id"}
        ):
            return False, "checkpoint conflict shape is not closed"
        if conflict["conflict_id"] in conflict_ids:
            return False, "checkpoint contains duplicate conflicts"
        conflict_ids.add(conflict["conflict_id"])
        if conflict.get("type") not in CONTENT_TYPES or not _text(conflict.get("subject")):
            return False, "checkpoint conflict identity is invalid"
        if conflict["conflict_id"] != f"conflict:{conflict['type'].lower()}:{conflict['subject']}":
            return False, "checkpoint conflict ID does not match its type and subject"
        if conflict.get("status") not in {"DISPUTED", "RESOLVED"} or not isinstance(conflict.get("material"), bool):
            return False, "checkpoint conflict policy fields are invalid"
        if conflict["type"] == "GOAL" and not conflict["material"]:
            return False, "checkpoint goal conflict must be material"
        if not _text(conflict.get("reason")):
            return False, "checkpoint conflict reason is invalid"
        if conflict.get("classification") not in {
            "CONTRADICTION_UNRESOLVED",
            "CONTRADICTION_REOPENED",
            "CONTRADICTORY_VALIDATION_RECEIPTS",
        }:
            return False, "checkpoint conflict classification is invalid"
        claims = conflict.get("claims")
        if not isinstance(claims, list) or len(claims) < 2:
            return False, "checkpoint conflict must preserve at least two claims"
        claim_ids: set[str] = set()
        claim_times: list[Any] = []
        for claim in claims:
            if (
                not isinstance(claim, dict)
                or set(claim)
                != {
                    "claim_id",
                    "value",
                    "epistemic",
                    "asserted_epistemic",
                    "authority",
                    "source_ids",
                    "observed_at",
                }
                or not _text(claim.get("claim_id"))
                or "value" not in claim
                or claim.get("epistemic") != "DISPUTED"
                or claim.get("authority") not in AUTHORITIES
                or not _source_id_list(claim.get("source_ids"), known_source_ids)
            ):
                return False, "checkpoint conflict claim is invalid"
            if "asserted_epistemic" in claim and claim["asserted_epistemic"] not in EPISTEMIC_STATES:
                return False, "checkpoint conflict claim asserted epistemic state is invalid"
            if claim["claim_id"] in claim_ids:
                return False, "checkpoint conflict contains duplicate claims"
            claim_ids.add(claim["claim_id"])
            try:
                claim_time = parse_instant(claim.get("observed_at"), "CP-CLAIM-TIME", "claim.observed_at")
            except ContractError as exc:
                return False, str(exc)
            if claim_time > created_at:
                return False, "checkpoint conflict claim is newer than the checkpoint"
            if any(
                parse_instant(sources[source_id]["captured_at"], "CP-SOURCE-TIME", "source.captured_at")
                > claim_time
                for source_id in claim["source_ids"]
            ):
                return False, "checkpoint conflict claim source postdates the claim"
            claim_times.append(claim_time)
        claim_value_hashes = {sha256_hex(claim["value"]) for claim in claims}
        history = conflict.get("resolution_history", [])
        if not isinstance(history, list):
            return False, "checkpoint conflict resolution history is invalid"
        history_ids: set[str] = set()
        resolution_times: list[Any] = []
        for resolution in history:
            if (
                not isinstance(resolution, dict)
                or set(resolution) != {"change_id", "value", "source_ids", "observed_at"}
                or not _text(resolution.get("change_id"))
                or resolution["change_id"] in history_ids
                or not _source_id_list(resolution.get("source_ids"), known_source_ids)
            ):
                return False, "checkpoint conflict resolution history entry is invalid"
            history_ids.add(resolution["change_id"])
            try:
                resolution_time = parse_instant(
                    resolution.get("observed_at"), "CP-RESOLUTION-TIME", "resolution.observed_at"
                )
            except ContractError as exc:
                return False, str(exc)
            if resolution_time > created_at:
                return False, "checkpoint conflict resolution is newer than the checkpoint"
            if any(
                parse_instant(sources[source_id]["captured_at"], "CP-SOURCE-TIME", "source.captured_at")
                > resolution_time
                for source_id in resolution["source_ids"]
            ):
                return False, "checkpoint conflict resolution source postdates the resolution"
            if any(
                sources[source_id]["authority"] != "AUTHORIZED"
                or sources[source_id]["kind"] not in TRUSTED_AUTHORITY_SOURCE_KINDS
                for source_id in resolution["source_ids"]
            ):
                return False, "checkpoint conflict resolution lacks authorized provenance"
            if sha256_hex(resolution["value"]) not in claim_value_hashes:
                return False, "checkpoint conflict resolution selects an unpreserved claim"
            resolution_times.append(resolution_time)
        if resolution_times != sorted(resolution_times):
            return False, "checkpoint conflict resolution history is not chronological"
        meaningful_claim_times = claim_times
        if conflict["classification"] == "CONTRADICTORY_VALIDATION_RECEIPTS":
            first_time_by_value: dict[str, Any] = {}
            for claim, claim_time in zip(claims, claim_times):
                value_hash = sha256_hex(claim["value"])
                prior_time = first_time_by_value.get(value_hash)
                if prior_time is None or claim_time < prior_time:
                    first_time_by_value[value_hash] = claim_time
            meaningful_claim_times = list(first_time_by_value.values())
        if len(meaningful_claim_times) < 2:
            return False, "checkpoint conflict does not preserve two distinct claims"
        if resolution_times:
            if resolution_times[0] < sorted(meaningful_claim_times)[1]:
                return False, "checkpoint conflict was resolved before competing claims existed"
            if conflict["status"] == "RESOLVED" and resolution_times[-1] < max(meaningful_claim_times):
                return False, "checkpoint conflict resolution predates an unresolved claim"
            if conflict["status"] == "DISPUTED" and resolution_times[-1] >= max(meaningful_claim_times):
                return False, "checkpoint disputed conflict lacks a later reopening claim"
        if conflict["status"] == "RESOLVED" and (
            not _text(conflict.get("resolution_change_id"))
            or not history
            or history[-1]["change_id"] != conflict["resolution_change_id"]
        ):
            return False, "checkpoint resolved conflict lacks retained resolution history"
        if conflict["status"] == "RESOLVED":
            resolved_lamp = lamp_by_key.get((conflict["type"], conflict["subject"]))
            latest_resolution = history[-1]
            expected_lamp_sources = set(latest_resolution["source_ids"])
            if resolved_lamp is not None and conflict["type"] == "FACT":
                receipt_id = resolved_lamp.get("validation_receipt_id")
                if receipt_id in receipts:
                    expected_lamp_sources.update(receipts[receipt_id]["source_ids"])
            if (
                resolved_lamp is None
                or resolved_lamp["authority"] != "AUTHORIZED"
                or sha256_hex(resolved_lamp["value"]) != sha256_hex(latest_resolution["value"])
                or set(resolved_lamp["source_ids"]) != expected_lamp_sources
                or resolved_lamp["updated_at"] != latest_resolution["observed_at"]
            ):
                return False, "checkpoint resolved conflict is inconsistent with its active lamp"

    for lamp in lamps:
        receipt_id = lamp.get("validation_receipt_id")
        if lamp["type"] != "FACT" or receipt_id not in receipts:
            continue
        selection = _receipt_resolution_selection(
            receipts[receipt_id], checkpoint["conflicts"], lamps
        )
        if selection == "OPEN":
            return False, "checkpoint FACT is backed by an unresolved receipt conflict"
        if selection == "NOT_SELECTED":
            return False, "checkpoint FACT uses a receipt rejected by the retained resolution"

    open_conflicts = [item for item in checkpoint["conflicts"] if item["status"] == "DISPUTED"]
    open_conflict_keys = {(item["type"], item["subject"]) for item in open_conflicts}
    if lamp_keys.intersection(open_conflict_keys):
        return False, "checkpoint active lamp overlaps an open conflict"
    disputed_receipt_subjects = {
        item["subject"][len("validation.") :]
        for item in open_conflicts
        if item.get("classification") == "CONTRADICTORY_VALIDATION_RECEIPTS"
        and item["subject"].startswith("validation.")
    }
    if any(("FACT", subject) in lamp_keys for subject in disputed_receipt_subjects):
        return False, "checkpoint active FACT is backed by disputed validation receipts"
    dispute_position = _receipt_dispute_position(checkpoint["conflicts"])
    if dispute_position and checkpoint["city_position"] == dispute_position[0]:
        eligible_position_sources.update(dispute_position[1])
    for conflict in checkpoint["conflicts"]:
        if (
            conflict["status"] != "RESOLVED"
            or conflict["classification"] != "CONTRADICTORY_VALIDATION_RECEIPTS"
            or not conflict["material"]
        ):
            continue
        resolved_lamp = lamp_by_key.get(("FACT", conflict["subject"]))
        if (
            resolved_lamp
            and isinstance(resolved_lamp["value"], dict)
            and resolved_lamp["value"].get("status") in {"PASS", "FAIL"}
            and resolved_lamp["value"].get("summary") == checkpoint["city_position"]
        ):
            eligible_position_sources.update(resolved_lamp["source_ids"])
    if "validation_receipt_pointers" in checkpoint:
        evidenced_position = _select_evidenced_city_position(
            checkpoint_receipts, checkpoint["conflicts"], lamps
        )
        if evidenced_position is not None and (
            checkpoint["city_position"] != evidenced_position[0]
            or sorted(checkpoint["city_position_source_ids"])
            != sorted(set(evidenced_position[1]))
        ):
            return False, "checkpoint city position does not match deterministic evidence policy"
    if not set(checkpoint["city_position_source_ids"]).issubset(eligible_position_sources):
        return False, "checkpoint city position lacks trusted checkpoint or receipt provenance"
    open_goal_conflicts = sorted(
        (item for item in open_conflicts if item["type"] == "GOAL"),
        key=lambda item: item["conflict_id"],
    )
    if len(goal_lamps) == 1 and not open_goal_conflicts:
        goal_context = {
            "subject": goal_lamps[0]["subject"],
            "source_ids": list(goal_lamps[0]["source_ids"]),
        }
    elif not goal_lamps and len(open_goal_conflicts) == 1:
        contested_goal = open_goal_conflicts[0]
        goal_context = {
            "subject": contested_goal["subject"],
            "source_ids": sorted(
                {source_id for claim in contested_goal["claims"] for source_id in claim["source_ids"]}
            ),
        }
    else:
        return False, "checkpoint must have exactly one active goal or one open material goal conflict"

    unknown_ids: set[str] = set()
    for unknown in checkpoint["unknowns"]:
        if (
            not isinstance(unknown, dict)
            or set(unknown)
            != {"unknown_id", "subject", "statement", "critical", "epistemic", "source_ids"}
            or not _text(unknown.get("unknown_id"))
            or not _text(unknown.get("subject"))
            or not _text(unknown.get("statement"))
            or unknown.get("epistemic") != "UNKNOWN"
            or not isinstance(unknown.get("critical"), bool)
            or not _source_id_list(unknown.get("source_ids"), known_source_ids)
        ):
            return False, "checkpoint unknown is invalid"
        if unknown["unknown_id"] in unknown_ids:
            return False, "checkpoint contains duplicate unknowns"
        unknown_ids.add(unknown["unknown_id"])

    recent_change_ids: set[str] = set()
    for change in checkpoint["recent_changes"]:
        if (
            not isinstance(change, dict)
            or set(change) != _CURRENT_RECENT_CHANGE_FIELDS
            or change.get("object_type") != "STATE_CHANGE"
            or not _text(change.get("change_id"))
            or not isinstance(change.get("sequence"), int)
            or isinstance(change.get("sequence"), bool)
            or change.get("status") not in {"APPLIED", "DISPUTED"}
            or not _text(change.get("reason"))
            or change.get("content_type") not in CONTENT_TYPES
            or change.get("operation") not in OPERATIONS
            or change.get("epistemic") not in EPISTEMIC_STATES
            or change.get("authority") not in AUTHORITIES
            or not isinstance(change.get("material"), bool)
            or not _source_id_list(change.get("source_ids"), known_source_ids)
            or "before" not in change
            or "after" not in change
            or not _recent_change_impact_is_consistent(change)
        ):
            return False, "checkpoint recent change is invalid"
        if (
            change["change_id"] in recent_change_ids
            or change["sequence"] <= 0
            or change["sequence"] > last_sequence
        ):
            return False, "checkpoint recent change identity or sequence is invalid"
        recent_change_ids.add(change["change_id"])
        try:
            change_time = parse_instant(change.get("observed_at"), "CP-CHANGE-TIME", "change.observed_at")
            if change_time > created_at:
                return False, "checkpoint recent change is newer than the checkpoint"
        except ContractError as exc:
            return False, str(exc)
        if any(
            parse_instant(sources[source_id]["captured_at"], "CP-SOURCE-TIME", "source.captured_at")
            > change_time
            for source_id in change["source_ids"]
        ):
            return False, "checkpoint recent change source postdates the change"

    if not _recent_change_chain_is_continuous(checkpoint, receipts):
        return False, "checkpoint recent change transition chain is discontinuous"
    if not _latest_recent_changes_match_projection(checkpoint, receipts):
        return False, "checkpoint recent change does not match final state projection"

    pointers: dict[str, dict[str, Any]] = {}
    for pointer in checkpoint["source_pointers"]:
        if (
            not isinstance(pointer, dict)
            or set(pointer)
            != {"source_id", "kind", "locator", "captured_at", "authority", "content_sha256"}
            or not _text(pointer.get("source_id"))
        ):
            return False, "checkpoint source pointer is invalid"
        source_id = pointer["source_id"]
        if source_id in pointers or source_id not in sources:
            return False, "checkpoint source pointer is duplicate or unresolved"
        source = sources[source_id]
        for field in ("kind", "locator", "captured_at", "authority"):
            if pointer.get(field) != source.get(field):
                return False, "checkpoint source pointer does not match package evidence"
        if pointer.get("content_sha256") != source["content_sha256"]:
            return False, "checkpoint source pointer hash does not match package evidence"
        if parse_instant(source["captured_at"], "CP-SOURCE-TIME", "source.captured_at") > created_at:
            return False, "checkpoint source pointer is newer than the checkpoint"
        pointers[source_id] = pointer

    referenced = set(checkpoint["city_position_source_ids"])
    referenced.update(checkpoint["primary_next_step"]["source_ids"])
    goal = checkpoint["primary_next_step"].get("goal")
    if goal:
        referenced.update(goal["source_ids"])
    for constraint in checkpoint["primary_next_step"].get("constraints", []):
        referenced.update(constraint["source_ids"])
    for lamp in lamps:
        referenced.update(lamp["source_ids"])
    for conflict in checkpoint["conflicts"]:
        for claim in conflict["claims"]:
            referenced.update(claim["source_ids"])
    for unknown in checkpoint["unknowns"]:
        referenced.update(unknown["source_ids"])
    for change in checkpoint["recent_changes"]:
        referenced.update(change["source_ids"])
    for conflict in checkpoint["conflicts"]:
        for resolution in conflict.get("resolution_history", []):
            referenced.update(resolution["source_ids"])
    for pointer in receipt_pointers:
        referenced.update(pointer["source_ids"])
    if not referenced.issubset(pointers):
        return False, "checkpoint source pointers do not cover material references"
    if checkpoint["primary_next_step"].get("goal") != goal_context:
        return False, "checkpoint next step is not linked to the active goal"
    expected_constraints = [
        {
            "subject": lamp["subject"],
            "value": copy.deepcopy(lamp["value"]),
            "source_ids": list(lamp["source_ids"]),
        }
        for lamp in sorted((item for item in lamps if item["type"] == "CONSTRAINT"), key=lambda item: item["subject"])
    ]
    if checkpoint["primary_next_step"].get("constraints") != expected_constraints:
        return False, "checkpoint next step does not carry the active constraint context"

    checkpoint_sources = {source_id: sources[source_id] for source_id in pointers}
    checkpoint_conflicts = {item["conflict_id"]: item for item in checkpoint["conflicts"]}
    for expected_receipt_conflict in _receipt_conflicts(checkpoint_receipts):
        actual_receipt_conflict = checkpoint_conflicts.get(expected_receipt_conflict["conflict_id"])
        if actual_receipt_conflict is None or not _receipt_conflict_matches(
            actual_receipt_conflict, expected_receipt_conflict
        ):
            return False, "checkpoint does not preserve contradictory trusted receipts"
    expected_voltage, expected_step = _choose_next_step(
        open_conflicts,
        checkpoint["unknowns"],
        _action_driving_receipts(checkpoint_receipts, checkpoint["conflicts"]),
        checkpoint_sources,
        lamps,
        checkpoint["created_at"],
    )
    expected_step = _attach_orientation_context(expected_step, lamps)
    if checkpoint["voltage"] != expected_voltage or checkpoint["primary_next_step"] != expected_step:
        return False, "checkpoint voltage or next step does not match deterministic policy"
    return True, "valid"


def _select_checkpoint(
    package: dict[str, Any],
    as_of: str,
    sources: dict[str, dict[str, Any]],
    receipts: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], str, list[dict[str, str]], bool]:
    checkpoints = require_mapping(package.get("checkpoints"), "PKG-010", "package.checkpoints")
    require_closed_keys(
        checkpoints,
        {"primary", "fallbacks"},
        {"primary", "fallbacks"},
        "PKG-010",
        "package.checkpoints",
    )
    candidates: list[tuple[str, Any]] = [("PRIMARY", checkpoints.get("primary"))]
    fallbacks = require_list(checkpoints.get("fallbacks"), "PKG-010", "package.checkpoints.fallbacks")
    candidates.extend((f"FALLBACK_{index + 1}", value) for index, value in enumerate(fallbacks))
    candidate_times: dict[str, Any] = {}
    reserved_receipt_hashes: dict[str, str] = {}
    for label, checkpoint in candidates:
        if not isinstance(checkpoint, dict):
            continue
        try:
            candidate_times[label] = parse_instant(
                checkpoint.get("created_at"), "CP-ROLLBACK-TIME", "checkpoint.created_at"
            )
        except ContractError:
            pass
        pointers = checkpoint.get("validation_receipt_pointers")
        if not isinstance(pointers, list):
            continue
        for pointer in pointers:
            if (
                not isinstance(pointer, dict)
                or not _text(pointer.get("receipt_id"))
                or not isinstance(pointer.get("receipt_sha256"), str)
                or len(pointer["receipt_sha256"]) != 64
                or any(character not in "0123456789abcdef" for character in pointer["receipt_sha256"])
            ):
                continue
            receipt_id = pointer["receipt_id"]
            prior_hash = reserved_receipt_hashes.get(receipt_id)
            if prior_hash is not None and prior_hash != pointer["receipt_sha256"]:
                raise OrientationError(
                    f"[RECEIPT-LEDGER-CONFLICT] checkpoints disagree about immutable receipt {receipt_id}"
                )
            reserved_receipt_hashes[receipt_id] = pointer["receipt_sha256"]
    for receipt_id, receipt in receipts.items():
        reserved_hash = reserved_receipt_hashes.get(receipt_id)
        if reserved_hash is not None and reserved_hash != sha256_hex(receipt):
            raise OrientationError(
                f"[RECEIPT-ID-REUSE] {receipt_id} changed after checkpointing"
            )
    errors: list[dict[str, str]] = []
    valid_candidates: list[tuple[Any, bool, str, dict[str, Any], bool]] = []
    for label, checkpoint in candidates:
        prepared, migrated_legacy, migration_error = _prepare_checkpoint_candidate(checkpoint)
        if migration_error is None:
            valid, reason = _checkpoint_is_semantically_valid(prepared, as_of, sources, receipts)
        else:
            valid, reason = False, migration_error
        if valid:
            valid_candidates.append(
                (
                    parse_instant(prepared["created_at"], "CP-SELECT-TIME", "checkpoint.created_at"),
                    label == "PRIMARY",
                    label,
                    prepared,
                    migrated_legacy,
                )
            )
        else:
            if reason.startswith("RECEIPT_ID_REUSE:"):
                raise OrientationError(f"[RECEIPT-ID-REUSE] {reason.split(':', 1)[1]}")
            errors.append({"candidate": label, "reason": reason})
    if not valid_candidates:
        raise OrientationError("[CP-RECOVERY] no valid checkpoint or fallback is available")
    _, is_primary, label, selected, migrated_legacy = max(
        valid_candidates,
        key=lambda item: (item[0], item[3]["last_sequence"], item[1], item[3]["checkpoint_id"]),
    )
    selected_time = parse_instant(selected["created_at"], "CP-SELECT-TIME", "checkpoint.created_at")
    valid_labels = {item[2] for item in valid_candidates}
    lost_history_boundaries = [
        candidate_time
        for candidate_label, candidate_time in candidate_times.items()
        if candidate_label not in valid_labels and candidate_time > selected_time
    ]
    if lost_history_boundaries:
        lost_history_boundary = max(lost_history_boundaries)
        for receipt in receipts.values():
            if (
                receipt["receipt_id"] not in reserved_receipt_hashes
                and parse_instant(receipt["checked_at"], "RECEIPT-TIME", "receipt.checked_at")
                <= lost_history_boundary
            ):
                raise OrientationError(
                    "[RECEIPT-LINEAGE-UNKNOWN] a newer invalid checkpoint may contain "
                    f"receipt {receipt['receipt_id']}; omit or restore the checkpoint ledger before replay"
                )
    primary_valid = any(item[2] == "PRIMARY" for item in valid_candidates)
    if is_primary:
        status = "PRIMARY_VALID"
    elif primary_valid:
        status = "LATEST_VALID_FALLBACK_SELECTED"
    else:
        status = "FALLBACK_VALID_AFTER_CORRUPTION"
    if migrated_legacy:
        status = f"{status}_LEGACY_MIGRATED"
    return copy.deepcopy(selected), status, errors, migrated_legacy


def _disposition(change: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    item = {
        "change_id": change["change_id"],
        "sequence": change["sequence"],
        "object_type": change["object_type"],
        "content_type": change.get("content_type", "TRACE"),
        "subject": change.get("subject", "imported.text"),
        "status": status,
        "reason": reason,
        "source_ids": change["source_ids"],
        "observed_at": change["observed_at"],
    }
    if change["object_type"] == "STATE_CHANGE":
        item.update(
            {
                "operation": change["operation"],
                "epistemic": change["epistemic"],
                "authority": change["authority"],
                "material": change["material"],
                "meaning": copy.deepcopy(change["value"]),
            }
        )
    return item


def _meaningful_state_change(
    change: dict[str, Any],
    status: str,
    reason: str,
    impact: str,
    before: Any,
    after: Any,
) -> dict[str, Any]:
    disposition = _disposition(change, status, reason)
    disposition.update(
        {
            "impact": impact,
            "before": copy.deepcopy(before),
            "after": copy.deepcopy(after),
        }
    )
    if not _recent_change_impact_is_consistent(disposition):
        raise OrientationError("[CHG-IMPACT] generated STATE_CHANGE impact is inconsistent")
    return disposition


def _evidence_source_ids(change: dict[str, Any], receipts: dict[str, dict[str, Any]]) -> list[str]:
    source_ids = set(change["source_ids"])
    receipt = receipts.get(change.get("validation_receipt_id", ""))
    if receipt is not None:
        source_ids.update(receipt["source_ids"])
    return sorted(source_ids)


def _lamp_from_change(change: dict[str, Any], receipts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    lamp = {
        "lamp_id": f"lamp:{change['content_type'].lower()}:{change['subject']}",
        "type": change["content_type"],
        "subject": change["subject"],
        "value": copy.deepcopy(change["value"]),
        "epistemic": change["epistemic"],
        "authority": change["authority"],
        "source_ids": _evidence_source_ids(change, receipts),
        "updated_at": change["observed_at"],
        "material": change["material"],
    }
    if change.get("validation_receipt_id"):
        lamp["validation_receipt_id"] = change["validation_receipt_id"]
    return lamp


def _policy_rejection(
    change: dict[str, Any],
    sources: dict[str, dict[str, Any]],
    receipts: dict[str, dict[str, Any]],
    conflicts: Iterable[dict[str, Any]],
    active_lamps: Iterable[dict[str, Any]],
    base_checkpoint_id: str,
    as_of: str,
) -> str | None:
    if not change["source_ids"] or any(source_id not in sources for source_id in change["source_ids"]):
        return "SOURCE_UNKNOWN"
    observed_at = parse_instant(change["observed_at"], "CHG-TIME", "change.observed_at")
    if observed_at > parse_instant(as_of, "PKG-TIME", "package.as_of"):
        return "FUTURE_EVIDENCE_REJECTED"
    if any(
        parse_instant(sources[source_id]["captured_at"], "SRC-TIME", "source.captured_at") > observed_at
        for source_id in change["source_ids"]
    ):
        return "SOURCE_POSTDATES_CHANGE"
    expected = change.get("expected_checkpoint_id")
    if not expected:
        return "MISSING_EXPECTED_CHECKPOINT"
    if expected != base_checkpoint_id:
        return "STALE_STATE"
    if change["operation"] == "MOVE":
        return "MOVE_NOT_IMPLEMENTED_IN_MVP"
    if change.get("supersedes") and change["operation"] != "SUPERSEDE":
        return "SUPERSESSION_FIELD_REQUIRES_SUPERSEDE_OPERATION"
    if change["operation"] == "SUPERSEDE" and not change.get("supersedes"):
        return "SUPERSEDE_REQUIRES_TARGET"
    if change.get("resolves_conflict_id") and change["operation"] != "RESOLVE":
        return "RESOLUTION_FIELD_REQUIRES_RESOLVE_OPERATION"
    if change["operation"] == "RESOLVE" and not change.get("resolves_conflict_id"):
        return "RESOLVE_REQUIRES_CONFLICT_TARGET"
    matching_open_conflict = next(
        (
            conflict
            for conflict in conflicts
            if conflict.get("status") == "DISPUTED"
            and conflict.get("type") == change["content_type"]
            and conflict.get("subject") == change["subject"]
        ),
        None,
    )
    if matching_open_conflict is not None and change["operation"] in {
        "DEACTIVATE",
        "INVALIDATE",
        "SUPERSEDE",
    }:
        return "DISPUTED_CONFLICT_REQUIRES_RESOLVE"
    active_target = next(
        (
            lamp
            for lamp in active_lamps
            if lamp.get("type") == change["content_type"]
            and lamp.get("subject") == change["subject"]
        ),
        None,
    )
    if (
        active_target is not None
        and change["operation"] in {"DEACTIVATE", "INVALIDATE"}
        and not _same_value(active_target.get("value"), change["value"])
    ):
        return "DEACTIVATION_MEANING_MISMATCH"
    if change["content_type"] == "GOAL" and not change["material"]:
        return "GOAL_MUST_BE_MATERIAL"
    if change["content_type"] == "CONSTRAINT" and not _constraint_value_is_valid(change["value"]):
        return "UNSUPPORTED_CONSTRAINT_POLICY"
    referenced_receipt = receipts.get(change.get("validation_receipt_id", ""))
    if change.get("validation_receipt_id") and referenced_receipt is None:
        return "UNKNOWN_VALIDATION_RECEIPT"
    if change.get("validation_receipt_id") and change["content_type"] != "FACT":
        return "NON_FACT_RECEIPT_NOT_ALLOWED"
    if referenced_receipt is not None and referenced_receipt["subject"] != change["subject"]:
        return "RECEIPT_SUBJECT_MISMATCH"
    if referenced_receipt is not None and parse_instant(
        referenced_receipt["checked_at"], "RECEIPT-TIME", "receipt.checked_at"
    ) > observed_at:
        return "RECEIPT_POSTDATES_CHANGE"
    if change["content_type"] in {"GOAL", "DECISION", "CONSTRAINT"} or change["operation"] == "RESOLVE":
        if change["authority"] != "AUTHORIZED":
            return "UNAUTHORIZED_OVERRIDE"
        if any(sources[source_id]["authority"] != "AUTHORIZED" for source_id in change["source_ids"]):
            return "AUTHORITY_SOURCE_MISMATCH"
        if any(sources[source_id]["kind"] not in TRUSTED_AUTHORITY_SOURCE_KINDS for source_id in change["source_ids"]):
            return "AUTHORITY_SOURCE_KIND_NOT_TRUSTED"
    if change["content_type"] in {"RISK", "UNKNOWN"} and any(
        sources[source_id]["authority"] == "UNAUTHORIZED" for source_id in change["source_ids"]
    ):
        return "UNTRUSTED_EVIDENCE_SOURCE"
    if change["operation"] in {"DEACTIVATE", "INVALIDATE"} and change["content_type"] != "FACT":
        if change["authority"] != "AUTHORIZED":
            return "UNAUTHORIZED_OVERRIDE"
        if any(
            sources[source_id]["authority"] != "AUTHORIZED"
            or sources[source_id]["kind"] not in TRUSTED_AUTHORITY_SOURCE_KINDS
            for source_id in change["source_ids"]
        ):
            return "AUTHORITY_SOURCE_MISMATCH"
    if change["epistemic"] == "DISPUTED":
        return "DISPUTED_CANNOT_ACTIVATE"
    if change["content_type"] == "FACT":
        if change["epistemic"] != "VERIFIED":
            return "UNSUPPORTED_FACT"
        receipt = referenced_receipt
        if receipt is None:
            return "MISSING_VALIDATION_RECEIPT"
        if receipt["validator_id"] not in TRUSTED_VALIDATOR_IDS:
            return "UNTRUSTED_VALIDATOR_RECEIPT"
        receipt_selection = _receipt_resolution_selection(receipt, conflicts, active_lamps)
        if receipt_selection == "OPEN":
            return "RECEIPT_CONFLICT_BLOCKS_FACT"
        if receipt_selection == "NOT_SELECTED":
            return "RECEIPT_RESOLUTION_DOES_NOT_SELECT_PROOF"
        if change["operation"] in {"DEACTIVATE", "INVALIDATE"}:
            if receipt["status"] != "FAIL" or not receipt.get("assertion_sha256"):
                return "RECEIPT_NOT_FAIL"
        else:
            if not _receipt_is_trusted_pass(receipt):
                return "RECEIPT_NOT_PASS"
            if receipt["assertion_sha256"] != _assertion_hash(change["subject"], change["value"]):
                return "RECEIPT_ASSERTION_MISMATCH"
    if change["content_type"] == "UNKNOWN" and change["epistemic"] != "UNKNOWN":
        return "UNKNOWN_EPISTEMIC_MISMATCH"
    return None


def _open_conflict(
    existing: dict[str, Any],
    change: dict[str, Any],
    receipts: dict[str, dict[str, Any]],
    prior_conflict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conflict_id = f"conflict:{change['content_type'].lower()}:{change['subject']}"
    new_claim = {
        "claim_id": change["change_id"],
        "value": copy.deepcopy(change["value"]),
        "epistemic": "DISPUTED",
        "asserted_epistemic": change["epistemic"],
        "authority": change["authority"],
        "source_ids": _evidence_source_ids(change, receipts),
        "observed_at": change["observed_at"],
    }
    if prior_conflict is not None:
        reopened = copy.deepcopy(prior_conflict)
        reopened["material"] = bool(reopened["material"] or existing.get("material") or change["material"])
        reopened["status"] = "DISPUTED"
        reopened["classification"] = "CONTRADICTION_REOPENED"
        reopened["reason"] = "A new competing claim reopened a previously resolved conflict; resolution history is retained."
        reopened["claims"].append(new_claim)
        return reopened
    return {
        "conflict_id": conflict_id,
        "type": change["content_type"],
        "subject": change["subject"],
        "material": bool(existing.get("material") or change["material"]),
        "status": "DISPUTED",
        "classification": "CONTRADICTION_UNRESOLVED",
        "reason": "Competing source-backed claims exist and neither explicitly supersedes the other.",
        "claims": [
            {
                "claim_id": existing["lamp_id"],
                "value": copy.deepcopy(existing["value"]),
                "epistemic": "DISPUTED",
                "asserted_epistemic": existing["epistemic"],
                "authority": existing["authority"],
                "source_ids": list(existing["source_ids"]),
                "observed_at": existing["updated_at"],
            },
            new_claim,
        ],
    }


def _latest_conflict_instant(conflict: dict[str, Any]) -> Any:
    instants = [
        parse_instant(claim["observed_at"], "CONFLICT-TIME", "claim.observed_at")
        for claim in conflict["claims"]
    ]
    instants.extend(
        parse_instant(item["observed_at"], "CONFLICT-TIME", "resolution.observed_at")
        for item in conflict.get("resolution_history", [])
    )
    return max(instants)


def _critical_unknowns(
    receipts: Iterable[dict[str, Any]],
    existing: list[dict[str, Any]],
    active_lamps: Iterable[dict[str, Any]],
    conflicts: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    unknowns = {item["unknown_id"]: copy.deepcopy(item) for item in existing}
    conflict_by_id = {item["conflict_id"]: item for item in conflicts}
    lamps = list(active_lamps)
    for unknown_id in [item for item in unknowns if item.startswith("unknown:lamp:")]:
        unknowns.pop(unknown_id)
    receipt_groups: dict[str, list[dict[str, Any]]] = {}
    for receipt in receipts:
        receipt_groups.setdefault(receipt["subject"], []).append(receipt)
    for subject, group in sorted(receipt_groups.items()):
        unknowns.pop(f"unknown:failure-cause:{subject}", None)
        unknowns.pop(f"unknown:validation:{subject}", None)
        unknowns.pop(f"unknown:receipt-conflict:{subject}", None)
        claim_identities = {_receipt_claim_identity(receipt) for receipt in group}
        statuses = {receipt["status"] for receipt in group}
        source_ids = sorted({source_id for receipt in group for source_id in receipt["source_ids"]})
        material = any(receipt["material"] for receipt in group)
        receipt_conflict = conflict_by_id.get(f"conflict:fact:validation.{subject}")
        if receipt_conflict is not None:
            source_ids = sorted(
                {
                    source_id
                    for claim in receipt_conflict["claims"]
                    for source_id in claim["source_ids"]
                }
            )
            material = bool(receipt_conflict["material"])
        if receipt_conflict is not None or len(claim_identities) > 1:
            if receipt_conflict and receipt_conflict["status"] == "RESOLVED":
                resolved_lamp = next(
                    (
                        lamp
                        for lamp in lamps
                        if lamp["type"] == "FACT" and lamp["subject"] == f"validation.{subject}"
                    ),
                    None,
                )
                selected_status = (
                    resolved_lamp["value"].get("status")
                    if resolved_lamp and isinstance(resolved_lamp.get("value"), dict)
                    else None
                )
                if selected_status == "FAIL" and material:
                    unknown_id = f"unknown:failure-cause:{subject}"
                    unknowns[unknown_id] = {
                        "unknown_id": unknown_id,
                        "subject": f"{subject}.failure_cause",
                        "statement": f"Root cause and corrective proof for {subject} remain UNKNOWN after failed validation.",
                        "critical": True,
                        "epistemic": "UNKNOWN",
                        "source_ids": source_ids,
                    }
                elif selected_status == "UNKNOWN" and material:
                    unknown_id = f"unknown:validation:{subject}"
                    unknowns[unknown_id] = {
                        "unknown_id": unknown_id,
                        "subject": subject,
                        "statement": f"Validation status for {subject} remains UNKNOWN.",
                        "critical": True,
                        "epistemic": "UNKNOWN",
                        "source_ids": source_ids,
                    }
                continue
            unknown_id = f"unknown:receipt-conflict:{subject}"
            unknowns[unknown_id] = {
                "unknown_id": unknown_id,
                "subject": f"validation.{subject}",
                "statement": f"Trusted validation receipts for {subject} disagree; the supported status remains UNKNOWN.",
                "critical": material,
                "epistemic": "UNKNOWN",
                "source_ids": source_ids,
            }
            continue
        status = next(iter(statuses))
        if status == "FAIL" and material:
            unknown_id = f"unknown:failure-cause:{subject}"
            unknowns[unknown_id] = {
                "unknown_id": unknown_id,
                "subject": f"{subject}.failure_cause",
                "statement": f"Root cause and corrective proof for {subject} remain UNKNOWN after failed validation.",
                "critical": True,
                "epistemic": "UNKNOWN",
                "source_ids": source_ids,
            }
        elif status == "UNKNOWN" and material:
            unknown_id = f"unknown:validation:{subject}"
            unknowns[unknown_id] = {
                "unknown_id": unknown_id,
                "subject": subject,
                "statement": f"Validation status for {subject} remains UNKNOWN.",
                "critical": True,
                "epistemic": "UNKNOWN",
                "source_ids": source_ids,
            }
    for lamp in lamps:
        if lamp["type"] != "UNKNOWN":
            continue
        value = lamp["value"] if isinstance(lamp["value"], str) else canonical_json_bytes(lamp["value"]).decode("utf-8")
        unknown_id = f"unknown:lamp:{lamp['subject']}"
        unknowns[unknown_id] = {
            "unknown_id": unknown_id,
            "subject": lamp["subject"],
            "statement": value,
            "critical": bool(lamp["material"]),
            "epistemic": "UNKNOWN",
            "source_ids": list(lamp["source_ids"]),
        }
    return sorted(unknowns.values(), key=lambda item: item["unknown_id"])


def _receipt_conflicts(receipts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for receipt in receipts:
        groups.setdefault(receipt["subject"], []).append(receipt)
    conflicts: list[dict[str, Any]] = []
    for subject, group in sorted(groups.items()):
        if len({_receipt_claim_identity(receipt) for receipt in group}) <= 1:
            continue
        conflict_subject = f"validation.{subject}"
        conflicts.append(
            {
                "conflict_id": f"conflict:fact:{conflict_subject}",
                "type": "FACT",
                "subject": conflict_subject,
                "material": any(receipt["material"] for receipt in group),
                "status": "DISPUTED",
                "classification": "CONTRADICTORY_VALIDATION_RECEIPTS",
                "reason": f"Trusted validation receipts for {subject} report incompatible claims.",
                "claims": [
                    _receipt_conflict_claim(receipt)
                    for receipt in sorted(group, key=lambda item: item["receipt_id"])
                ],
            }
        )
    return conflicts


def _single_receipt_conflict_update(receipt: dict[str, Any]) -> dict[str, Any]:
    conflict_subject = f"validation.{receipt['subject']}"
    return {
        "conflict_id": f"conflict:fact:{conflict_subject}",
        "type": "FACT",
        "subject": conflict_subject,
        "material": receipt["material"],
        "status": "DISPUTED",
        "classification": "CONTRADICTORY_VALIDATION_RECEIPTS",
        "reason": f"Trusted validation receipts for {receipt['subject']} report incompatible claims.",
        "claims": [_receipt_conflict_claim(receipt)],
    }


def _merge_receipt_conflict(
    existing: dict[str, Any] | None,
    expected: dict[str, Any],
) -> dict[str, Any]:
    if existing is None:
        return copy.deepcopy(expected)
    if (
        existing.get("conflict_id") != expected["conflict_id"]
        or existing.get("classification") != "CONTRADICTORY_VALIDATION_RECEIPTS"
    ):
        raise OrientationError(
            f"[RECEIPT-CONFLICT-ID] {expected['conflict_id']} collides with a non-receipt conflict"
        )
    merged = copy.deepcopy(existing)
    claims_by_id = {claim["claim_id"]: claim for claim in merged["claims"]}
    known_value_hashes = {sha256_hex(claim["value"]) for claim in merged["claims"]}
    added_novel_value = False
    novel_claims: list[dict[str, Any]] = []
    for claim in expected["claims"]:
        prior = claims_by_id.get(claim["claim_id"])
        if prior is not None and sha256_hex(prior) != sha256_hex(claim):
            raise OrientationError(
                f"[RECEIPT-ID-REUSE] receipt {claim['claim_id']} changed after checkpointing"
            )
        if prior is None:
            claims_by_id[claim["claim_id"]] = copy.deepcopy(claim)
            claim_value_hash = sha256_hex(claim["value"])
            if claim_value_hash not in known_value_hashes:
                added_novel_value = True
                known_value_hashes.add(claim_value_hash)
                novel_claims.append(claim)
    merged["claims"] = sorted(claims_by_id.values(), key=lambda item: item["claim_id"])
    merged["material"] = bool(merged["material"] or expected["material"])
    merged["classification"] = expected["classification"]
    merged["reason"] = expected["reason"]
    if added_novel_value and merged["status"] == "RESOLVED":
        latest_resolution = merged.get("resolution_history", [])[-1]
        resolution_time = parse_instant(
            latest_resolution["observed_at"], "CONFLICT-TIME", "resolution.observed_at"
        )
        if any(
            parse_instant(claim["observed_at"], "CONFLICT-TIME", "claim.observed_at")
            <= resolution_time
            for claim in novel_claims
        ):
            raise OrientationError(
                "[STALE-RECEIPT-CLAIM] a newly supplied competing receipt predates the retained resolution"
            )
        merged["status"] = "DISPUTED"
    return merged


def _receipt_conflict_matches(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    if any(
        actual.get(field) != expected[field]
        for field in ("conflict_id", "type", "subject", "classification", "reason")
    ):
        return False
    if expected["material"] and not actual.get("material"):
        return False
    actual_claims = {claim["claim_id"]: sha256_hex(claim) for claim in actual.get("claims", [])}
    return all(actual_claims.get(claim["claim_id"]) == sha256_hex(claim) for claim in expected["claims"])


def _receipt_dispute_position(
    conflicts: Iterable[dict[str, Any]],
) -> tuple[str, list[str]] | None:
    candidates = sorted(
        (
            conflict
            for conflict in conflicts
            if conflict.get("status") == "DISPUTED"
            and conflict.get("classification") == "CONTRADICTORY_VALIDATION_RECEIPTS"
            and conflict.get("material")
        ),
        key=lambda item: item["conflict_id"],
    )
    if not candidates:
        return None
    conflict = candidates[0]
    subject = (
        conflict["subject"][len("validation.") :]
        if conflict["subject"].startswith("validation.")
        else conflict["subject"]
    )
    source_ids = sorted(
        {source_id for claim in conflict["claims"] for source_id in claim["source_ids"]}
    )
    return (
        f"Current position is UNKNOWN because trusted validation receipts for {subject} disagree.",
        source_ids,
    )


def _receipt_conflict_root_subject(conflict: dict[str, Any]) -> str | None:
    subject = conflict.get("subject")
    if (
        conflict.get("classification") != "CONTRADICTORY_VALIDATION_RECEIPTS"
        or not isinstance(subject, str)
        or not subject.startswith("validation.")
    ):
        return None
    return subject[len("validation.") :]


def _action_driving_receipts(
    receipts: Iterable[dict[str, Any]],
    conflicts: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Exclude historical sides of a receipt conflict from policy selection.

    The claims stay retained in the conflict. While it is open, the conflict
    itself drives the corrective step; after an AUTHORIZED resolution, the
    selected FACT lamp drives state. Raw opposing receipts never become active
    again merely because they remain in the evidence package.
    """

    conflict_roots = {
        root
        for conflict in conflicts
        if (root := _receipt_conflict_root_subject(conflict)) is not None
    }
    return [receipt for receipt in receipts if receipt["subject"] not in conflict_roots]


def _resolved_receipt_positions(
    conflicts: Iterable[dict[str, Any]],
    active_lamps: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[str]]:
    state = {(lamp["type"], lamp["subject"]): lamp for lamp in active_lamps}
    positions: list[dict[str, Any]] = []
    proof_receipt_ids: set[str] = set()
    for conflict in conflicts:
        if (
            conflict.get("status") != "RESOLVED"
            or conflict.get("classification") != "CONTRADICTORY_VALIDATION_RECEIPTS"
            or not conflict.get("material")
        ):
            continue
        resolved_lamp = state.get(("FACT", conflict["subject"]))
        if resolved_lamp is None or not isinstance(resolved_lamp.get("value"), dict):
            continue
        status = resolved_lamp["value"].get("status")
        summary = resolved_lamp["value"].get("summary")
        if status not in {"PASS", "FAIL"} or not _text(summary):
            continue
        receipt_id = resolved_lamp.get("validation_receipt_id")
        if _text(receipt_id):
            proof_receipt_ids.add(receipt_id)
        positions.append(
            {
                "receipt_id": f"resolution:{conflict['conflict_id']}",
                "status": status,
                "summary": summary,
                "source_ids": list(resolved_lamp["source_ids"]),
            }
        )
    return sorted(positions, key=lambda item: item["receipt_id"]), proof_receipt_ids


def _select_evidenced_city_position(
    receipts: Iterable[dict[str, Any]],
    conflicts: Iterable[dict[str, Any]],
    active_lamps: Iterable[dict[str, Any]],
) -> tuple[str, list[str]] | None:
    retained_conflicts = list(conflicts)
    resolved_positions, proof_receipt_ids = _resolved_receipt_positions(
        retained_conflicts, active_lamps
    )
    position_receipts = [
        receipt
        for receipt in _action_driving_receipts(receipts, retained_conflicts)
        if receipt["receipt_id"] not in proof_receipt_ids
    ]
    raw_failed = sorted(
        (
            receipt
            for receipt in position_receipts
            if receipt["status"] == "FAIL" and receipt["material"]
        ),
        key=lambda item: item["receipt_id"],
    )
    resolved_failed = [item for item in resolved_positions if item["status"] == "FAIL"]
    if resolved_failed:
        item = resolved_failed[0]
        return item["summary"], list(item["source_ids"])
    if raw_failed:
        item = raw_failed[0]
        return item["summary"], list(item["source_ids"])
    dispute_position = _receipt_dispute_position(retained_conflicts)
    if dispute_position:
        return dispute_position
    resolved_passed = [item for item in resolved_positions if item["status"] == "PASS"]
    if resolved_passed:
        item = resolved_passed[0]
        return item["summary"], list(item["source_ids"])
    raw_passed = sorted(
        (
            receipt
            for receipt in position_receipts
            if receipt["status"] == "PASS" and receipt["material"]
        ),
        key=lambda item: item["receipt_id"],
    )
    if raw_passed:
        item = raw_passed[0]
        return item["summary"], list(item["source_ids"])
    return None


def _respect_constraints(
    voltage: str,
    step: dict[str, Any],
    active_lamps: Iterable[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    blockers = sorted(
        (
            lamp
            for lamp in active_lamps
            if lamp["type"] == "CONSTRAINT" and _constraint_forbids(lamp["value"], step["policy_class"])
        ),
        key=lambda item: item["subject"],
    )
    if not blockers:
        return voltage, step
    constraint = blockers[0]
    blocked_class = step["policy_class"]
    corrective_step = {
        "action_id": f"constraint:{constraint['subject']}:{blocked_class.lower()}",
        "instruction": (
            f"Record an AUTHORIZED revision of {constraint['subject']} or select an action "
            f"that permits {blocked_class}."
        ),
        "reason": f"The active constraint explicitly forbids policy class {blocked_class}.",
        "policy_class": "CORRECTIVE_CONSTRAINT_RESOLUTION",
        "source_ids": list(constraint["source_ids"]),
        "success_condition": {
            "type": "constraint_policy_allows",
            "subject": constraint["subject"],
            "policy_class": blocked_class,
        },
    }
    if step.get("goal"):
        corrective_step["goal"] = copy.deepcopy(step["goal"])
    return "BROKEN", corrective_step


def _choose_next_step(
    conflicts: list[dict[str, Any]],
    unknowns: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    active_lamps: Iterable[dict[str, Any]],
    as_of: str,
) -> tuple[str, dict[str, Any]]:
    del sources
    lamps = list(active_lamps)
    material_conflicts = [item for item in conflicts if item["status"] == "DISPUTED" and item["material"]]
    if material_conflicts:
        conflict = sorted(material_conflicts, key=lambda item: item["conflict_id"])[0]
        source_ids = sorted({source_id for claim in conflict["claims"] for source_id in claim["source_ids"]})
        step = {
            "action_id": f"resolve:{conflict['subject']}",
            "instruction": f"Record one AUTHORIZED resolution for {conflict['subject']} that explicitly supersedes the competing claims.",
            "reason": "The conflict is material; disputed claims cannot drive execution.",
            "policy_class": "CORRECTIVE_CONFLICT_RESOLUTION",
            "source_ids": source_ids,
            "success_condition": {
                "type": "conflict_resolved",
                "subject": conflict["subject"],
                "content_type": conflict["type"],
                "required_authority": "AUTHORIZED",
            },
        }
        if conflict["type"] == "GOAL":
            step["goal"] = {"subject": conflict["subject"], "source_ids": source_ids}
        return _respect_constraints("BLOCKED", step, lamps)
    critical_unknowns = [item for item in unknowns if item.get("critical")]
    if critical_unknowns:
        unknown = sorted(critical_unknowns, key=lambda item: item["unknown_id"])[0]
        return _respect_constraints("UNKNOWN", {
            "action_id": f"evidence:{unknown['subject']}",
            "instruction": f"Collect and validate source evidence that resolves {unknown['subject']}.",
            "reason": "A critical unknown prevents a supported action.",
            "policy_class": "CORRECTIVE_EVIDENCE_COLLECTION",
            "source_ids": list(unknown["source_ids"]),
            "success_condition": {"type": "unknown_resolved", "subject": unknown["subject"]},
        }, lamps)
    material_risks = sorted(
        (lamp for lamp in lamps if lamp["type"] == "RISK" and lamp["material"]),
        key=lambda item: item["subject"],
    )
    if material_risks:
        risk = material_risks[0]
        return _respect_constraints("WEAK", {
            "action_id": f"mitigate:{risk['subject']}",
            "instruction": f"Record and validate one mitigation for {risk['subject']} before goal execution.",
            "reason": "An active material risk makes direct execution unsafe.",
            "policy_class": "CORRECTIVE_RISK_MITIGATION",
            "source_ids": list(risk["source_ids"]),
            "success_condition": {"type": "risk_mitigated", "subject": risk["subject"]},
        }, lamps)
    failed = [receipt for receipt in receipts if receipt["status"] == "FAIL" and receipt["material"]]
    if failed:
        receipt = sorted(failed, key=lambda item: item["receipt_id"])[0]
        return _respect_constraints("BLOCKED", {
            "action_id": f"validate:{receipt['subject']}",
            "instruction": f"Fix the evidenced failure and rerun validation for {receipt['subject']}.",
            "reason": receipt["summary"],
            "policy_class": "CORRECTIVE_VALIDATION",
            "source_ids": list(receipt["source_ids"]),
            "success_condition": {
                "type": "validation_pass",
                "status": "PASS",
                "subject": receipt["subject"],
                "checked_after": receipt["checked_at"],
                "assertion_sha256": receipt["assertion_sha256"],
            },
        }, lamps)
    goal_lamps = [lamp for lamp in lamps if lamp["type"] == "GOAL"]
    if len(goal_lamps) != 1:
        raise OrientationError("[GOAL-001] orientation requires exactly one active goal")
    goal = goal_lamps[0]
    return _respect_constraints("FLOWING", {
        "action_id": "validate:current-goal",
        "instruction": "Execute the next goal-aligned validation and retain its receipt.",
        "reason": "No material conflict or critical unknown currently blocks the goal.",
        "policy_class": "GOAL_VALIDATION",
        "source_ids": list(goal["source_ids"]),
        "success_condition": {
            "type": "validation_receipt_retained",
            "status": "PASS",
            "subject": goal["subject"],
            "checked_after": as_of,
            "assertion_sha256": _assertion_hash(goal["subject"], goal["value"]),
        },
    }, lamps)


def _attach_orientation_context(next_step: dict[str, Any], active_lamps: Iterable[dict[str, Any]]) -> dict[str, Any]:
    contextualized = copy.deepcopy(next_step)
    lamps = list(active_lamps)
    goals = sorted((lamp for lamp in lamps if lamp["type"] == "GOAL"), key=lambda item: item["subject"])
    constraints = sorted((lamp for lamp in lamps if lamp["type"] == "CONSTRAINT"), key=lambda item: item["subject"])
    if goals:
        contextualized["goal"] = {
            "subject": goals[0]["subject"],
            "source_ids": list(goals[0]["source_ids"]),
        }
    contextualized["constraints"] = [
        {
            "subject": item["subject"],
            "value": copy.deepcopy(item["value"]),
            "source_ids": list(item["source_ids"]),
        }
        for item in constraints
    ]
    return contextualized


def _source_pointers(source_ids: Iterable[str], sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": source_id,
            "kind": sources[source_id]["kind"],
            "locator": sources[source_id]["locator"],
            "captured_at": sources[source_id]["captured_at"],
            "authority": sources[source_id]["authority"],
            "content_sha256": sources[source_id]["content_sha256"],
        }
        for source_id in sorted(set(source_ids))
        if source_id in sources
    ]


def _validation_receipt_pointer(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "receipt_id": receipt["receipt_id"],
        "receipt_sha256": sha256_hex(receipt),
        "subject": receipt["subject"],
        "checked_at": receipt["checked_at"],
        "source_ids": list(receipt["source_ids"]),
    }


def _derive_recovery_card(checkpoint: dict[str, Any]) -> dict[str, Any]:
    goal_lamps = [lamp for lamp in checkpoint["active_lamps"] if lamp["type"] == "GOAL"]
    decisions = [lamp for lamp in checkpoint["active_lamps"] if lamp["type"] == "DECISION"]
    constraints = [lamp for lamp in checkpoint["active_lamps"] if lamp["type"] == "CONSTRAINT"]
    risks = [lamp for lamp in checkpoint["active_lamps"] if lamp["type"] == "RISK"]
    return copy.deepcopy({
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
    })


def orient(raw_package: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic checkpoint, Recovery Card, and scoped run receipt."""

    try:
        package = require_mapping(copy.deepcopy(raw_package), "PKG-001", "package")
        package_fields = {
            "schema_version",
            "package_id",
            "as_of",
            "sources",
            "validation_receipts",
            "checkpoints",
            "changes",
        }
        require_closed_keys(package, package_fields, package_fields, "PKG-001", "package")
        require(package.get("schema_version") == SCHEMA_VERSION, "PKG-002", "package schema must be 0.3C")
        package_id = require_text(package.get("package_id"), "PKG-003", "package_id")
        as_of = require_text(package.get("as_of"), "PKG-004", "package.as_of")
        as_of_instant = parse_instant(as_of, "PKG-004", "package.as_of")

        source_list = [validate_source(item) for item in require_list(package.get("sources"), "PKG-005", "package.sources")]
        sources = {item["source_id"]: item for item in source_list}
        require(len(sources) == len(source_list), "PKG-006", "source_ids must be unique")
        for source in source_list:
            require(
                parse_instant(source["captured_at"], "PKG-012", f"source {source['source_id']} captured_at") <= as_of_instant,
                "PKG-012",
                f"source {source['source_id']} is from the future",
            )
        receipt_list = [validate_receipt(item) for item in require_list(package.get("validation_receipts", []), "PKG-007", "package.validation_receipts")]
        receipts = {item["receipt_id"]: item for item in receipt_list}
        require(len(receipts) == len(receipt_list), "PKG-008", "receipt_ids must be unique")
        for receipt in receipt_list:
            require(all(source_id in sources for source_id in receipt["source_ids"]), "PKG-009", f"receipt {receipt['receipt_id']} has an unknown source")
            checked_at = parse_instant(receipt["checked_at"], "PKG-013", f"receipt {receipt['receipt_id']} checked_at")
            require(checked_at <= as_of_instant, "PKG-013", f"receipt {receipt['receipt_id']} is from the future")
            require(
                all(parse_instant(sources[source_id]["captured_at"], "PKG-014", "source.captured_at") <= checked_at for source_id in receipt["source_ids"]),
                "PKG-014",
                f"receipt {receipt['receipt_id']} predates its evidence source",
            )
        effective_receipts = [item for item in receipt_list if item["validator_id"] in TRUSTED_VALIDATOR_IDS]

        base, recovery_status, checkpoint_errors, legacy_migration = _select_checkpoint(
            package, as_of, sources, receipts
        )
        base_checkpoint_id = base["checkpoint_id"]
        migrated_recent_changes = (
            copy.deepcopy(base["recent_changes"]) if legacy_migration else []
        )
        receipt_pointer_by_id = {
            pointer["receipt_id"]: copy.deepcopy(pointer)
            for pointer in base.get("validation_receipt_pointers", [])
        }
        for receipt in receipt_list:
            pointer = _validation_receipt_pointer(receipt)
            prior = receipt_pointer_by_id.get(receipt["receipt_id"])
            if prior is not None and prior != pointer:
                raise OrientationError(
                    f"[RECEIPT-ID-REUSE] {receipt['receipt_id']} changed after checkpointing"
                )
            receipt_pointer_by_id[receipt["receipt_id"]] = pointer
        validation_receipt_pointers = sorted(
            receipt_pointer_by_id.values(), key=lambda item: item["receipt_id"]
        )
        state = {(lamp["type"], lamp["subject"]): copy.deepcopy(lamp) for lamp in base["active_lamps"]}
        conflicts = {item["conflict_id"]: copy.deepcopy(item) for item in base["conflicts"]}
        historical_event_ids = {item["change_id"] for item in base["recent_changes"]}
        # An active lamp becomes the first preserved claim if a later update opens
        # a conflict. Reserve its deterministic identity so an incoming event
        # cannot create two claims with the same ID.
        historical_event_ids.update(lamp["lamp_id"] for lamp in base["active_lamps"])
        for conflict in base["conflicts"]:
            historical_event_ids.update(claim["claim_id"] for claim in conflict["claims"])
            historical_event_ids.update(
                resolution["change_id"] for resolution in conflict.get("resolution_history", [])
            )
        touched_receipt_conflict_ids: set[str] = set()
        for receipt_conflict in _receipt_conflicts(effective_receipts):
            conflict_id = receipt_conflict["conflict_id"]
            conflicts[conflict_id] = _merge_receipt_conflict(
                conflicts.get(conflict_id), receipt_conflict
            )
            touched_receipt_conflict_ids.add(conflict_id)
        # A compact checkpoint may preserve the earlier sides without requiring
        # the raw receipts to be loaded again. Merge each trusted tail receipt
        # directly into that retained conflict so new meaning cannot disappear.
        for receipt in effective_receipts:
            conflict_id = f"conflict:fact:validation.{receipt['subject']}"
            if conflict_id not in conflicts:
                continue
            conflicts[conflict_id] = _merge_receipt_conflict(
                conflicts[conflict_id], _single_receipt_conflict_update(receipt)
            )
            touched_receipt_conflict_ids.add(conflict_id)
        for conflict_id in sorted(touched_receipt_conflict_ids):
            projected_conflict = conflicts[conflict_id]
            if projected_conflict["status"] == "DISPUTED":
                # A later receipt reopens the validation dispute and suspends
                # the prior resolution lamp until a new explicit resolution.
                state.pop(("FACT", projected_conflict["subject"]), None)
                fact_subject = projected_conflict["subject"][len("validation.") :]
                suspended_fact = state.pop(("FACT", fact_subject), None)
                if suspended_fact is not None:
                    suspended_claim = {
                        "claim_id": suspended_fact["lamp_id"],
                        "value": {
                            "fact_subject": suspended_fact["subject"],
                            "fact_value": copy.deepcopy(suspended_fact["value"]),
                            "validation_receipt_id": suspended_fact.get("validation_receipt_id", ""),
                        },
                        "epistemic": "DISPUTED",
                        "asserted_epistemic": suspended_fact["epistemic"],
                        "authority": suspended_fact["authority"],
                        "source_ids": list(suspended_fact["source_ids"]),
                        "observed_at": suspended_fact["updated_at"],
                    }
                    prior_claim = next(
                        (
                            claim
                            for claim in projected_conflict["claims"]
                            if claim["claim_id"] == suspended_claim["claim_id"]
                        ),
                        None,
                    )
                    if prior_claim is not None and sha256_hex(prior_claim) != sha256_hex(suspended_claim):
                        raise OrientationError(
                            f"[FACT-LINEAGE-ID] {suspended_fact['lamp_id']} changed after checkpointing"
                        )
                    if prior_claim is None:
                        projected_conflict["claims"].append(suspended_claim)
                        projected_conflict["claims"].sort(key=lambda item: item["claim_id"])
                    projected_conflict["material"] = bool(
                        projected_conflict["material"] or suspended_fact["material"]
                    )
        dispositions: list[dict[str, Any]] = []
        meaningful: list[dict[str, Any]] = []
        seen_semantics: set[str] = set()
        normalized_changes = [normalize_change(item) for item in require_list(package.get("changes"), "PKG-011", "package.changes")]
        id_payloads: dict[str, set[str]] = {}
        for change in normalized_changes:
            if (
                change["object_type"] == "STATE_CHANGE"
                and _policy_rejection(
                    change,
                    sources,
                    receipts,
                    conflicts.values(),
                    state.values(),
                    base_checkpoint_id,
                    as_of,
                )
                is None
            ):
                id_payloads.setdefault(change["change_id"], set()).add(sha256_hex(change))
        reused_ids = {change_id for change_id, payloads in id_payloads.items() if len(payloads) > 1}
        ordered_changes = sorted(
            normalized_changes,
            key=lambda item: (item["sequence"], item["change_id"], sha256_hex(item)),
        )

        for change in ordered_changes:
            if change["sequence"] <= base["last_sequence"]:
                dispositions.append(_disposition(change, "IGNORED", "COVERED_BY_VALID_CHECKPOINT"))
                continue
            if change["change_id"] in historical_event_ids:
                dispositions.append(_disposition(change, "REJECTED", "HISTORICAL_ID_REUSE"))
                continue
            if change["change_id"] in reused_ids:
                dispositions.append(_disposition(change, "REJECTED", "ID_REUSE_CONFLICT"))
                continue
            if change["object_type"] == "TRACE":
                instruction_markers = ("ignore previous", "system:", "mark complete", "override authority")
                reason = "IMPORTED_TEXT_IS_DATA_NOT_INSTRUCTION" if any(marker in change["text"].lower() for marker in instruction_markers) else "TRACE_EXPIRED_NO_MEANINGFUL_CHANGE"
                dispositions.append(_disposition(change, "IGNORED", reason))
                continue
            if change["object_type"] == "RECOVERY_CARD":
                dispositions.append(_disposition(change, "REJECTED", "RECOVERY_CARD_CONTAMINATION"))
                continue

            policy_reason = _policy_rejection(
                change,
                sources,
                receipts,
                conflicts.values(),
                state.values(),
                base_checkpoint_id,
                as_of,
            )
            if policy_reason:
                dispositions.append(_disposition(change, "REJECTED", policy_reason))
                continue
            fingerprint = semantic_fingerprint(change)
            if fingerprint in seen_semantics:
                dispositions.append(_disposition(change, "REJECTED", "DUPLICATE"))
                continue
            seen_semantics.add(fingerprint)

            key = (change["content_type"], change["subject"])
            conflict_id = f"conflict:{change['content_type'].lower()}:{change['subject']}"
            if (
                change["content_type"] == "FACT"
                and conflicts.get(f"conflict:fact:validation.{change['subject']}", {}).get("status")
                == "DISPUTED"
            ):
                dispositions.append(
                    _disposition(change, "REJECTED", "RECEIPT_CONFLICT_BLOCKS_FACT")
                )
                continue
            if change["operation"] == "RESOLVE":
                requested_conflict_id = change.get("resolves_conflict_id")
                conflict = conflicts.get(requested_conflict_id)
                if (
                    requested_conflict_id != conflict_id
                    or conflict is None
                    or conflict["type"] != change["content_type"]
                    or conflict["subject"] != change["subject"]
                    or conflict["status"] != "DISPUTED"
                    or sha256_hex(change["value"])
                    not in {sha256_hex(claim["value"]) for claim in conflict["claims"]}
                ):
                    dispositions.append(_disposition(change, "REJECTED", "INVALID_CONFLICT_RESOLUTION"))
                    continue
                if parse_instant(
                    change["observed_at"], "CHG-TIME", "change.observed_at"
                ) < _latest_conflict_instant(conflict):
                    dispositions.append(_disposition(change, "REJECTED", "STALE_CONFLICT_EVENT"))
                    continue
                before_conflict = copy.deepcopy(conflict)
                resolved_lamp = _lamp_from_change(change, receipts)
                state[key] = resolved_lamp
                conflict["status"] = "RESOLVED"
                conflict["resolution_change_id"] = change["change_id"]
                conflict.setdefault("resolution_history", []).append(
                    {
                        "change_id": change["change_id"],
                        "value": copy.deepcopy(change["value"]),
                        "source_ids": list(change["source_ids"]),
                        "observed_at": change["observed_at"],
                    }
                )
                conflicts[conflict["conflict_id"]] = conflict
                disposition = _meaningful_state_change(
                    change,
                    "APPLIED",
                    "AUTHORIZED_CONFLICT_RESOLUTION",
                    "CONFLICT_RESOLVED",
                    before_conflict,
                    resolved_lamp,
                )
                dispositions.append(disposition)
                meaningful.append(disposition)
                continue

            existing_conflict = conflicts.get(conflict_id)
            if existing_conflict and existing_conflict["status"] == "DISPUTED":
                if change["operation"] not in {"CREATE", "UPDATE", "ACTIVATE"}:
                    dispositions.append(
                        _disposition(change, "REJECTED", "DISPUTED_CONFLICT_REQUIRES_RESOLVE")
                    )
                    continue
                if change["change_id"] in {claim["claim_id"] for claim in existing_conflict["claims"]}:
                    dispositions.append(_disposition(change, "REJECTED", "HISTORICAL_ID_REUSE"))
                    continue
                if parse_instant(
                    change["observed_at"], "CHG-TIME", "change.observed_at"
                ) < _latest_conflict_instant(existing_conflict):
                    dispositions.append(_disposition(change, "REJECTED", "STALE_CONFLICT_EVENT"))
                    continue
                before_conflict = copy.deepcopy(existing_conflict)
                existing_conflict["claims"].append(
                    {
                        "claim_id": change["change_id"],
                        "value": copy.deepcopy(change["value"]),
                        "epistemic": "DISPUTED",
                        "asserted_epistemic": change["epistemic"],
                        "authority": change["authority"],
                        "source_ids": _evidence_source_ids(change, receipts),
                        "observed_at": change["observed_at"],
                    }
                )
                existing_conflict["material"] = bool(existing_conflict["material"] or change["material"])
                disposition = _meaningful_state_change(
                    change,
                    "DISPUTED",
                    "CONFLICT_PRESERVED",
                    "CONFLICT_EXTENDED",
                    before_conflict,
                    existing_conflict,
                )
                dispositions.append(disposition)
                meaningful.append(disposition)
                continue

            existing = state.get(key)
            if change["content_type"] == "GOAL" and existing is None and change["operation"] in {"CREATE", "ACTIVATE"}:
                if any(lamp["type"] == "GOAL" for lamp in state.values()):
                    dispositions.append(_disposition(change, "REJECTED", "MULTIPLE_ACTIVE_GOALS_NOT_ALLOWED"))
                    continue
                if any(
                    conflict["type"] == "GOAL" and conflict["status"] == "DISPUTED"
                    for conflict in conflicts.values()
                ):
                    dispositions.append(
                        _disposition(change, "REJECTED", "MULTIPLE_GOAL_CONTEXTS_NOT_ALLOWED")
                    )
                    continue
            if change["operation"] in {"UPDATE", "SUPERSEDE", "MOVE"} and existing is None:
                dispositions.append(_disposition(change, "REJECTED", "TARGET_NOT_ACTIVE"))
                continue
            if change["operation"] == "SUPERSEDE" and change.get("supersedes") != existing["lamp_id"]:
                dispositions.append(_disposition(change, "REJECTED", "INVALID_SUPERSESSION_TARGET"))
                continue
            if existing is not None and parse_instant(change["observed_at"], "CHG-TIME", "change.observed_at") < parse_instant(existing["updated_at"], "LAMP-TIME", "lamp.updated_at"):
                dispositions.append(_disposition(change, "REJECTED", "STALE_STATE"))
                continue
            if (
                existing is not None
                and existing["material"]
                and not change["material"]
                and change["content_type"] in {"RISK", "UNKNOWN"}
                and (
                    change["authority"] != "AUTHORIZED"
                    or any(
                        sources[source_id]["authority"] != "AUTHORIZED"
                        or sources[source_id]["kind"] not in TRUSTED_AUTHORITY_SOURCE_KINDS
                        for source_id in change["source_ids"]
                    )
                )
            ):
                dispositions.append(
                    _disposition(change, "REJECTED", "UNAUTHORIZED_MATERIALITY_DOWNGRADE")
                )
                continue
            if existing_conflict and existing_conflict["status"] == "RESOLVED":
                if change["operation"] in {"DEACTIVATE", "INVALIDATE"} or change.get("supersedes") == existing["lamp_id"]:
                    dispositions.append(
                        _disposition(change, "REJECTED", "RESOLVED_STATE_REQUIRES_CONFLICT_REOPEN")
                    )
                    continue
                if sha256_hex(existing["value"]) == sha256_hex(change["value"]):
                    dispositions.append(_disposition(change, "IGNORED", "NO_NEW_MEANING"))
                    continue
            if change["operation"] == "SUPERSEDE":
                updated_lamp = _lamp_from_change(change, receipts)
                state[key] = updated_lamp
                disposition = _meaningful_state_change(
                    change,
                    "APPLIED",
                    "EXPLICIT_SUPERSESSION",
                    "STATE_REPLACED",
                    existing,
                    updated_lamp,
                )
                dispositions.append(disposition)
                meaningful.append(disposition)
                continue
            if change["operation"] in {"INVALIDATE", "DEACTIVATE"}:
                if existing is None:
                    dispositions.append(_disposition(change, "REJECTED", "TARGET_NOT_ACTIVE"))
                    continue
                if change["content_type"] == "GOAL" and sum(
                    1 for lamp in state.values() if lamp["type"] == "GOAL"
                ) == 1:
                    dispositions.append(_disposition(change, "REJECTED", "LAST_ACTIVE_GOAL_CANNOT_BE_REMOVED"))
                    continue
                if change["content_type"] == "FACT":
                    receipt = receipts[change["validation_receipt_id"]]
                    if receipt["assertion_sha256"] != _assertion_hash(existing["subject"], existing["value"]):
                        dispositions.append(_disposition(change, "REJECTED", "RECEIPT_ASSERTION_MISMATCH"))
                        continue
                state.pop(key)
                disposition = _meaningful_state_change(
                    change,
                    "APPLIED",
                    "STATE_DEACTIVATED",
                    "STATE_DEACTIVATED",
                    existing,
                    None,
                )
                dispositions.append(disposition)
                meaningful.append(disposition)
                continue
            same_value = (
                existing is not None
                and sha256_hex(existing["value"]) == sha256_hex(change["value"])
            )
            if existing is not None and not same_value:
                opened_conflict = _open_conflict(
                    existing,
                    change,
                    receipts,
                    existing_conflict if existing_conflict and existing_conflict["status"] == "RESOLVED" else None,
                )
                conflicts[conflict_id] = opened_conflict
                state.pop(key)
                disposition = _meaningful_state_change(
                    change,
                    "DISPUTED",
                    "CONFLICT_PRESERVED",
                    "CONFLICT_OPENED",
                    existing,
                    opened_conflict,
                )
                dispositions.append(disposition)
                meaningful.append(disposition)
                continue
            if existing is not None and same_value:
                merged = copy.deepcopy(existing)
                merged["source_ids"] = sorted(set(merged["source_ids"] + _evidence_source_ids(change, receipts)))
                metadata_changed = any(
                    existing[field] != change[field]
                    for field in ("epistemic", "authority", "material")
                ) or (
                    change["content_type"] == "FACT"
                    and existing.get("validation_receipt_id") != change.get("validation_receipt_id")
                )
                sources_changed = merged["source_ids"] != existing["source_ids"]
                if not metadata_changed and not sources_changed:
                    dispositions.append(_disposition(change, "IGNORED", "NO_NEW_MEANING"))
                    continue
                merged["epistemic"] = change["epistemic"]
                merged["authority"] = change["authority"]
                merged["material"] = change["material"]
                merged["updated_at"] = change["observed_at"]
                if change["content_type"] == "FACT":
                    merged["validation_receipt_id"] = change["validation_receipt_id"]
                state[key] = merged
                reason = "STATE_METADATA_UPDATED" if metadata_changed else "CORROBORATING_SOURCE_MERGED"
                impact = "STATE_METADATA_UPDATED" if metadata_changed else "EVIDENCE_EXTENDED"
                disposition = _meaningful_state_change(
                    change,
                    "APPLIED",
                    reason,
                    impact,
                    existing,
                    merged,
                )
                dispositions.append(disposition)
                meaningful.append(disposition)
                continue
            created_lamp = _lamp_from_change(change, receipts)
            state[key] = created_lamp
            disposition = _meaningful_state_change(
                change,
                "APPLIED",
                "AUTHORIZED_MEANINGFUL_CHANGE",
                "STATE_ACTIVATED",
                None,
                created_lamp,
            )
            dispositions.append(disposition)
            meaningful.append(disposition)

        active_lamps = list(state.values())
        retained_recent_changes = migrated_recent_changes + meaningful
        last_meaningful_sequence = max(
            (item["sequence"] for item in meaningful),
            default=base["last_sequence"],
        )
        unknowns = _critical_unknowns(
            effective_receipts,
            base["unknowns"],
            active_lamps,
            conflicts.values(),
        )
        open_conflicts = sorted((item for item in conflicts.values() if item["status"] == "DISPUTED"), key=lambda item: item["conflict_id"])
        retained_conflicts = sorted(conflicts.values(), key=lambda item: item["conflict_id"])
        new_effective_receipts = [
            receipt
            for receipt in effective_receipts
            if parse_instant(receipt["checked_at"], "RECEIPT-TIME", "receipt.checked_at")
            > parse_instant(base["created_at"], "CP-TIME", "checkpoint.created_at")
        ]
        semantic_input_changed = (
            legacy_migration
            or bool(meaningful)
            or bool(new_effective_receipts)
            or validation_receipt_pointers != base.get("validation_receipt_pointers", [])
            or retained_conflicts != base["conflicts"]
            or unknowns != base["unknowns"]
        )
        if semantic_input_changed:
            voltage, selected_step = _choose_next_step(
                open_conflicts,
                unknowns,
                _action_driving_receipts(effective_receipts, retained_conflicts),
                sources,
                active_lamps,
                as_of,
            )
            next_step = _attach_orientation_context(selected_step, active_lamps)
        else:
            voltage, next_step = base["voltage"], copy.deepcopy(base["primary_next_step"])
        evidenced_position = _select_evidenced_city_position(
            effective_receipts, retained_conflicts, active_lamps
        )
        if evidenced_position is None:
            city_position = base["city_position"]
            position_sources = list(base["city_position_source_ids"])
        else:
            city_position, position_sources = evidenced_position

        referenced_sources = set(position_sources + next_step["source_ids"])
        if next_step.get("goal"):
            referenced_sources.update(next_step["goal"]["source_ids"])
        for constraint in next_step.get("constraints", []):
            referenced_sources.update(constraint["source_ids"])
        for lamp in state.values():
            referenced_sources.update(lamp["source_ids"])
        for conflict in retained_conflicts:
            for claim in conflict["claims"]:
                referenced_sources.update(claim["source_ids"])
            for resolution in conflict.get("resolution_history", []):
                referenced_sources.update(resolution["source_ids"])
        for unknown in unknowns:
            referenced_sources.update(unknown["source_ids"])
        for change in retained_recent_changes:
            referenced_sources.update(change["source_ids"])
        for pointer in validation_receipt_pointers:
            referenced_sources.update(pointer["source_ids"])

        checkpoint_payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "checkpoint_id": "pending",
            "created_at": as_of,
            "last_sequence": last_meaningful_sequence,
            "city_position": city_position,
            "city_position_source_ids": sorted(set(position_sources)),
            "active_lamps": sorted(state.values(), key=lambda item: (item["type"], item["subject"])),
            "recent_changes": retained_recent_changes,
            "conflicts": retained_conflicts,
            "unknowns": unknowns,
            "voltage": voltage,
            "primary_next_step": next_step,
            "source_pointers": _source_pointers(referenced_sources, sources),
            "validation_receipt_pointers": validation_receipt_pointers,
        }
        checkpoint_required = (
            legacy_migration
            or bool(meaningful)
            or city_position != base["city_position"]
            or retained_conflicts != base["conflicts"]
            or unknowns != base["unknowns"]
            or voltage != base["voltage"]
            or next_step != base["primary_next_step"]
            or validation_receipt_pointers != base.get("validation_receipt_pointers", [])
        )
        if checkpoint_required:
            checkpoint_payload["checkpoint_id"] = f"cp:{sha256_hex({key: value for key, value in checkpoint_payload.items() if key != 'checkpoint_id'})[:16]}"
            checkpoint = seal_checkpoint(checkpoint_payload)
        else:
            checkpoint = copy.deepcopy(base)
        recovery_card = _derive_recovery_card(checkpoint)
        executed_untrusted = any(item["reason"] == "IMPORTED_TEXT_IS_DATA_NOT_INSTRUCTION" and item["status"] != "IGNORED" for item in dispositions)
        checkpoint_valid, checkpoint_reason = _checkpoint_is_semantically_valid(checkpoint, as_of, sources, receipts)
        if not checkpoint_valid:
            raise OrientationError(f"[CP-INTERNAL] generated checkpoint failed semantic validation: {checkpoint_reason}")
        checks = {
            "checkpoint_integrity_and_structure": checkpoint_valid,
            "exactly_one_next_step": _next_step_is_valid(checkpoint["primary_next_step"], set(sources)),
            "recovery_card_non_authoritative": (
                recovery_card["source_of_truth"] is False
                and recovery_card["write_back_allowed"] is False
                and recovery_card["derived_from_integrity"] == checkpoint["integrity"]["value"]
            ),
            "untrusted_instruction_not_executed": not executed_untrusted,
            "material_outputs_have_sources": checkpoint_valid,
            "disputed_claims_not_action_driving": not any(
                lamp.get("epistemic") == "DISPUTED" for lamp in checkpoint["active_lamps"]
            )
            and not any(
                lamp.get("type") == "FACT"
                and any(
                    conflict.get("status") == "DISPUTED"
                    and conflict.get("classification") == "CONTRADICTORY_VALIDATION_RECEIPTS"
                    and conflict.get("subject") == f"validation.{lamp.get('subject')}"
                    for conflict in checkpoint["conflicts"]
                )
                for lamp in checkpoint["active_lamps"]
            ),
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
    except (ContractError, KeyError, TypeError) as exc:
        raise OrientationError(str(exc)) from exc


def evaluate_success_condition(result: dict[str, Any], condition: dict[str, Any]) -> bool:
    """Evaluate the closed, machine-verifiable success-condition vocabulary."""

    if not _success_condition_is_valid(condition):
        return False
    condition_type = condition.get("type")
    checkpoint = result.get("checkpoint", {})
    open_conflicts = [
        item for item in checkpoint.get("conflicts", []) if item.get("status") == "DISPUTED"
    ]

    def has_open_conflict(content_type: str, subject: str) -> bool:
        return any(
            item.get("type") == content_type and item.get("subject") == subject
            for item in open_conflicts
        )

    def receipt_claim_is_disputed(subject: str) -> bool:
        trusted = [
            item
            for item in result.get("validation_receipts", [])
            if item.get("subject") == subject and item.get("validator_id") in TRUSTED_VALIDATOR_IDS
        ]
        matching_conflicts = [
            item
            for item in checkpoint.get("conflicts", [])
            if item.get("type") == "FACT"
            and item.get("subject") == f"validation.{subject}"
            and item.get("classification") == "CONTRADICTORY_VALIDATION_RECEIPTS"
        ]
        if matching_conflicts:
            return len(matching_conflicts) != 1 or matching_conflicts[0].get("status") != "RESOLVED"
        return len({_receipt_claim_identity(item) for item in trusted}) > 1

    def selected_receipt_resolution(subject: str) -> dict[str, Any] | None:
        matching = [
            item
            for item in checkpoint.get("conflicts", [])
            if item.get("type") == "FACT"
            and item.get("subject") == f"validation.{subject}"
            and item.get("classification") == "CONTRADICTORY_VALIDATION_RECEIPTS"
        ]
        if len(matching) != 1 or matching[0].get("status") != "RESOLVED":
            return None
        lamps = [
            item
            for item in checkpoint.get("active_lamps", [])
            if item.get("type") == "FACT" and item.get("subject") == f"validation.{subject}"
        ]
        if len(lamps) != 1 or not isinstance(lamps[0].get("value"), dict):
            return None
        return lamps[0]["value"]

    def matching_pass_after(
        subject: str,
        assertion_sha256: str,
        checked_after: Any,
    ) -> bool:
        has_receipt_conflict = any(
            item.get("type") == "FACT"
            and item.get("subject") == f"validation.{subject}"
            and item.get("classification") == "CONTRADICTORY_VALIDATION_RECEIPTS"
            for item in checkpoint.get("conflicts", [])
        )
        selected = selected_receipt_resolution(subject)
        if has_receipt_conflict and selected is None:
            return False
        if selected is not None and (
                selected.get("status") != "PASS"
                or selected.get("assertion_sha256") != assertion_sha256
                or not _text(selected.get("summary"))
            ):
            return False
        return any(
            item.get("subject") == subject
            and item.get("assertion_sha256") == assertion_sha256
            and _receipt_is_trusted_pass(item)
            and (selected is None or item.get("summary") == selected.get("summary"))
            and parse_instant(item.get("checked_at"), "RECEIPT-TIME", "receipt.checked_at")
            > checked_after
            for item in result.get("validation_receipts", [])
        )

    if condition_type == "conflict_resolved":
        subject = condition.get("subject")
        content_type = condition.get("content_type")
        authority = condition.get("required_authority")
        active = any(
            item.get("type") == content_type
            and item.get("subject") == subject
            and item.get("authority") == authority
            for item in checkpoint.get("active_lamps", [])
        )
        return not has_open_conflict(content_type, subject) and active
    if condition_type == "constraint_policy_allows":
        subject = condition.get("subject")
        policy_class = condition.get("policy_class")
        if has_open_conflict("CONSTRAINT", subject):
            return False
        constraint = next(
            (
                item
                for item in checkpoint.get("active_lamps", [])
                if item.get("type") == "CONSTRAINT" and item.get("subject") == subject
            ),
            None,
        )
        return constraint is None or not _constraint_forbids(constraint.get("value"), policy_class)
    if condition_type == "unknown_resolved":
        subject = condition.get("subject")
        root_subject = (
            subject[: -len(".failure_cause")]
            if isinstance(subject, str) and subject.endswith(".failure_cause")
            else subject
        )
        lineage = {subject, root_subject, f"validation.{root_subject}"}
        return not any(item.get("subject") in lineage for item in checkpoint.get("unknowns", [])) and not any(
            item.get("subject") in lineage for item in open_conflicts
        )
    if condition_type == "risk_mitigated":
        subject = condition.get("subject")
        return not has_open_conflict("RISK", subject) and not any(
            item.get("type") == "RISK" and item.get("subject") == subject and item.get("material")
            for item in checkpoint.get("active_lamps", [])
        )
    if condition_type == "validation_pass":
        subject = condition.get("subject")
        if receipt_claim_is_disputed(subject):
            return False
        assertion_sha256 = condition.get("assertion_sha256")
        try:
            checked_after = parse_instant(
                condition.get("checked_after"), "STEP-TIME", "success_condition.checked_after"
            )
        except ContractError:
            return False
        return condition.get("status") == "PASS" and matching_pass_after(
            subject, assertion_sha256, checked_after
        )
    if condition_type == "validation_receipt_retained":
        subject = condition.get("subject")
        if receipt_claim_is_disputed(subject):
            return False
        assertion_sha256 = condition.get("assertion_sha256")
        try:
            checked_after = parse_instant(
                condition.get("checked_after"),
                "STEP-TIME",
                "success_condition.checked_after",
            )
        except ContractError:
            return False
        return condition.get("status") == "PASS" and matching_pass_after(
            subject, assertion_sha256, checked_after
        )
    return False
