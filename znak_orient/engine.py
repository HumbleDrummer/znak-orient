"""Deterministic X30 memory-orientation reducer."""

from __future__ import annotations

import copy
from typing import Any, Iterable

from .canonical import canonical_json_bytes, seal_checkpoint, sha256_hex, verify_checkpoint_integrity
from .contracts import (
    AUTHORITIES,
    CONTENT_TYPES,
    EPISTEMIC_STATES,
    SCHEMA_VERSION,
    TRUSTED_AUTHORITY_SOURCE_KINDS,
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


VOLTAGES = {"FLOWING", "WEAK", "BLOCKED", "BROKEN", "UNKNOWN"}
SUCCESS_CONDITION_TYPES = {
    "conflict_resolved",
    "risk_mitigated",
    "unknown_resolved",
    "validation_pass",
    "validation_receipt_retained",
}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


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


def _receipt_claim_identity(receipt: dict[str, Any]) -> tuple[str, str]:
    return receipt["status"], receipt.get("assertion_sha256", "")


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
            set(value) == {"type", "subject", "required_authority"}
            and _text(value.get("subject"))
            and value.get("required_authority") == "AUTHORIZED"
        )
    if condition_type in {"risk_mitigated", "unknown_resolved", "validation_pass"}:
        return set(value) == {"type", "subject"} and _text(value.get("subject"))
    return set(value) == {"type", "status"} and value.get("status") == "PASS"


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
    if "policy_class" in value and not _text(value["policy_class"]):
        return False
    if not _source_id_list(value.get("source_ids"), known_sources):
        return False
    if not _success_condition_is_valid(value.get("success_condition")):
        return False
    goal = value.get("goal")
    if goal is not None and (
        not isinstance(goal, dict)
        or not _text(goal.get("subject"))
        or not _source_id_list(goal.get("source_ids"), known_sources)
    ):
        return False
    constraints = value.get("constraints", [])
    if not isinstance(constraints, list):
        return False
    return all(
        isinstance(item, dict)
        and _text(item.get("subject"))
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
    if checkpoint.get("voltage") not in VOLTAGES:
        return False, "checkpoint.voltage is invalid"
    if not _next_step_is_valid(checkpoint.get("primary_next_step"), known_source_ids):
        return False, "checkpoint.primary_next_step is invalid"

    lamps = checkpoint["active_lamps"]
    lamp_ids: set[str] = set()
    lamp_keys: set[tuple[str, str]] = set()
    for lamp in lamps:
        if not isinstance(lamp, dict):
            return False, "checkpoint lamp is not an object"
        lamp_id, lamp_type, subject = lamp.get("lamp_id"), lamp.get("type"), lamp.get("subject")
        if not _text(lamp_id) or lamp_type not in CONTENT_TYPES or not _text(subject) or "value" not in lamp:
            return False, "checkpoint lamp identity is invalid"
        if lamp_id != f"lamp:{lamp_type.lower()}:{subject}":
            return False, "checkpoint lamp ID does not match its type and subject"
        if lamp_id in lamp_ids or (lamp_type, subject) in lamp_keys:
            return False, "checkpoint contains duplicate lamps"
        lamp_ids.add(lamp_id)
        lamp_keys.add((lamp_type, subject))
        if lamp.get("epistemic") not in EPISTEMIC_STATES or lamp.get("epistemic") == "DISPUTED":
            return False, "checkpoint contains an action-driving disputed lamp"
        if lamp.get("authority") not in AUTHORITIES or not isinstance(lamp.get("material"), bool):
            return False, "checkpoint lamp policy fields are invalid"
        if not _source_id_list(lamp.get("source_ids"), known_source_ids):
            return False, "checkpoint lamp sources are unresolved"
        lamp_sources = [sources[source_id] for source_id in lamp["source_ids"]]
        receipt = None
        if "validation_receipt_id" in lamp:
            receipt_id = lamp.get("validation_receipt_id")
            if not _text(receipt_id) or receipt_id not in receipts:
                return False, "checkpoint lamp validation receipt is unresolved"
            receipt = receipts[receipt_id]
            if receipt["subject"] != subject or not set(receipt["source_ids"]).issubset(lamp["source_ids"]):
                return False, "checkpoint lamp validation receipt provenance is inconsistent"
        if lamp_type in {"GOAL", "DECISION", "CONSTRAINT"}:
            if lamp["authority"] != "AUTHORIZED":
                return False, "checkpoint authority-driving lamp is not authorized"
            if any(
                source["authority"] != "AUTHORIZED" or source["kind"] not in TRUSTED_AUTHORITY_SOURCE_KINDS
                for source in lamp_sources
            ):
                return False, "checkpoint authority-driving lamp has an untrusted source"
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
        try:
            if parse_instant(lamp.get("updated_at"), "CP-LAMP-TIME", "lamp.updated_at") > as_of_instant:
                return False, "checkpoint lamp is from the future"
        except ContractError as exc:
            return False, str(exc)
    goal_lamps = sorted((lamp for lamp in lamps if lamp["type"] == "GOAL"), key=lambda item: item["subject"])
    if not goal_lamps and not any(
        isinstance(item, dict) and item.get("type") == "GOAL" and item.get("status") == "DISPUTED"
        for item in checkpoint["conflicts"]
    ):
        return False, "checkpoint has no active goal"

    conflict_ids: set[str] = set()
    for conflict in checkpoint["conflicts"]:
        if not isinstance(conflict, dict) or not _text(conflict.get("conflict_id")):
            return False, "checkpoint conflict is invalid"
        if conflict["conflict_id"] in conflict_ids:
            return False, "checkpoint contains duplicate conflicts"
        conflict_ids.add(conflict["conflict_id"])
        if conflict.get("type") not in CONTENT_TYPES or not _text(conflict.get("subject")):
            return False, "checkpoint conflict identity is invalid"
        if conflict["conflict_id"] != f"conflict:{conflict['type'].lower()}:{conflict['subject']}":
            return False, "checkpoint conflict ID does not match its type and subject"
        if conflict.get("status") not in {"DISPUTED", "RESOLVED"} or not isinstance(conflict.get("material"), bool):
            return False, "checkpoint conflict policy fields are invalid"
        if not _text(conflict.get("reason")):
            return False, "checkpoint conflict reason is invalid"
        claims = conflict.get("claims")
        if not isinstance(claims, list) or len(claims) < 2:
            return False, "checkpoint conflict must preserve at least two claims"
        claim_ids: set[str] = set()
        for claim in claims:
            if (
                not isinstance(claim, dict)
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
                if parse_instant(claim.get("observed_at"), "CP-CLAIM-TIME", "claim.observed_at") > as_of_instant:
                    return False, "checkpoint conflict claim is from the future"
            except ContractError as exc:
                return False, str(exc)

    unknown_ids: set[str] = set()
    for unknown in checkpoint["unknowns"]:
        if (
            not isinstance(unknown, dict)
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

    for change in checkpoint["recent_changes"]:
        if (
            not isinstance(change, dict)
            or not _text(change.get("change_id"))
            or not isinstance(change.get("sequence"), int)
            or isinstance(change.get("sequence"), bool)
            or change.get("status") not in {"APPLIED", "DISPUTED"}
            or not _text(change.get("reason"))
            or not _source_id_list(change.get("source_ids"), known_source_ids)
            or "before" not in change
            or "after" not in change
        ):
            return False, "checkpoint recent change is invalid"

    pointers: dict[str, dict[str, Any]] = {}
    for pointer in checkpoint["source_pointers"]:
        if not isinstance(pointer, dict) or not _text(pointer.get("source_id")):
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
    if not referenced.issubset(pointers):
        return False, "checkpoint source pointers do not cover material references"
    expected_goal = (
        {
            "subject": goal_lamps[0]["subject"],
            "source_ids": list(goal_lamps[0]["source_ids"]),
        }
        if goal_lamps
        else None
    )
    if checkpoint["primary_next_step"].get("goal") != expected_goal:
        return False, "checkpoint next step is not linked to the active goal"
    expected_constraints = [
        {"subject": lamp["subject"], "source_ids": list(lamp["source_ids"])}
        for lamp in sorted((item for item in lamps if item["type"] == "CONSTRAINT"), key=lambda item: item["subject"])
    ]
    if checkpoint["primary_next_step"].get("constraints") != expected_constraints:
        return False, "checkpoint next step does not carry the active constraint context"

    checkpoint_sources = {source_id: sources[source_id] for source_id in pointers}
    checkpoint_receipts = [
        receipt
        for receipt in receipts.values()
        if receipt["validator_id"] in TRUSTED_VALIDATOR_IDS
        and parse_instant(receipt["checked_at"], "CP-RECEIPT-TIME", "receipt.checked_at") <= created_at
    ]
    checkpoint_conflicts = {item["conflict_id"]: item for item in checkpoint["conflicts"]}
    for expected_receipt_conflict in _receipt_conflicts(checkpoint_receipts):
        if checkpoint_conflicts.get(expected_receipt_conflict["conflict_id"]) != expected_receipt_conflict:
            return False, "checkpoint does not preserve contradictory trusted receipts"
    expected_voltage, expected_step = _choose_next_step(
        [item for item in checkpoint["conflicts"] if item["status"] == "DISPUTED"],
        checkpoint["unknowns"],
        checkpoint_receipts,
        checkpoint_sources,
        lamps,
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
) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    checkpoints = require_mapping(package.get("checkpoints"), "PKG-010", "package.checkpoints")
    candidates: list[tuple[str, Any]] = [("PRIMARY", checkpoints.get("primary"))]
    candidates.extend((f"FALLBACK_{index + 1}", value) for index, value in enumerate(checkpoints.get("fallbacks", [])))
    errors: list[dict[str, str]] = []
    for label, checkpoint in candidates:
        valid, reason = _checkpoint_is_semantically_valid(checkpoint, as_of, sources, receipts)
        if valid:
            status = "PRIMARY_VALID" if label == "PRIMARY" else "FALLBACK_VALID_AFTER_CORRUPTION"
            return copy.deepcopy(checkpoint), status, errors
        errors.append({"candidate": label, "reason": reason})
    raise OrientationError("[CP-RECOVERY] no valid checkpoint or fallback is available")


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
    base_checkpoint_id: str,
    as_of: str,
) -> str | None:
    if not change["source_ids"] or any(source_id not in sources for source_id in change["source_ids"]):
        return "SOURCE_UNKNOWN"
    if parse_instant(change["observed_at"], "CHG-TIME", "change.observed_at") > parse_instant(as_of, "PKG-TIME", "package.as_of"):
        return "FUTURE_EVIDENCE_REJECTED"
    expected = change.get("expected_checkpoint_id")
    if not expected:
        return "MISSING_EXPECTED_CHECKPOINT"
    if expected != base_checkpoint_id:
        return "STALE_STATE"
    if change["operation"] == "MOVE":
        return "MOVE_NOT_IMPLEMENTED_IN_MVP"
    referenced_receipt = receipts.get(change.get("validation_receipt_id", ""))
    if change.get("validation_receipt_id") and referenced_receipt is None:
        return "UNKNOWN_VALIDATION_RECEIPT"
    if referenced_receipt is not None and referenced_receipt["subject"] != change["subject"]:
        return "RECEIPT_SUBJECT_MISMATCH"
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
) -> dict[str, Any]:
    conflict_id = f"conflict:{change['content_type'].lower()}:{change['subject']}"
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
            {
                "claim_id": change["change_id"],
                "value": copy.deepcopy(change["value"]),
                "epistemic": "DISPUTED",
                "asserted_epistemic": change["epistemic"],
                "authority": change["authority"],
                "source_ids": _evidence_source_ids(change, receipts),
                "observed_at": change["observed_at"],
            },
        ],
    }


def _critical_unknowns(
    receipts: Iterable[dict[str, Any]],
    existing: list[dict[str, Any]],
    active_lamps: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    unknowns = {item["unknown_id"]: copy.deepcopy(item) for item in existing}
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
        if len(claim_identities) > 1:
            unknown_id = f"unknown:receipt-conflict:{subject}"
            unknowns[unknown_id] = {
                "unknown_id": unknown_id,
                "subject": f"validation.{subject}",
                "statement": f"Trusted validation receipts for {subject} disagree; the supported status remains UNKNOWN.",
                "critical": True,
                "epistemic": "UNKNOWN",
                "source_ids": source_ids,
            }
            continue
        status = next(iter(statuses))
        material = any(receipt["material"] for receipt in group)
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
    for lamp in active_lamps:
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
                "reason": f"Trusted validation receipts for {subject} report incompatible statuses.",
                "claims": [
                    {
                        "claim_id": receipt["receipt_id"],
                        "value": {
                            "status": receipt["status"],
                            "summary": receipt["summary"],
                            "assertion_sha256": receipt["assertion_sha256"],
                        },
                        "epistemic": "DISPUTED",
                        "asserted_epistemic": "VERIFIED",
                        "authority": "NOT_APPLICABLE",
                        "source_ids": list(receipt["source_ids"]),
                        "observed_at": receipt["checked_at"],
                    }
                    for receipt in sorted(group, key=lambda item: item["receipt_id"])
                ],
            }
        )
    return conflicts


def _choose_next_step(
    conflicts: list[dict[str, Any]],
    unknowns: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    active_lamps: Iterable[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    material_conflicts = [item for item in conflicts if item["status"] == "DISPUTED" and item["material"]]
    if material_conflicts:
        conflict = sorted(material_conflicts, key=lambda item: item["conflict_id"])[0]
        source_ids = sorted({source_id for claim in conflict["claims"] for source_id in claim["source_ids"]})
        return "BLOCKED", {
            "action_id": f"resolve:{conflict['subject']}",
            "instruction": f"Record one AUTHORIZED resolution for {conflict['subject']} that explicitly supersedes the competing claims.",
            "reason": "The conflict is material; disputed claims cannot drive execution.",
            "policy_class": "CORRECTIVE_CONFLICT_RESOLUTION",
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
            "policy_class": "CORRECTIVE_EVIDENCE_COLLECTION",
            "source_ids": list(unknown["source_ids"]),
            "success_condition": {"type": "unknown_resolved", "subject": unknown["subject"]},
        }
    material_risks = sorted(
        (lamp for lamp in active_lamps if lamp["type"] == "RISK" and lamp["material"]),
        key=lambda item: item["subject"],
    )
    if material_risks:
        risk = material_risks[0]
        return "WEAK", {
            "action_id": f"mitigate:{risk['subject']}",
            "instruction": f"Record and validate one mitigation for {risk['subject']} before goal execution.",
            "reason": "An active material risk makes direct execution unsafe.",
            "policy_class": "CORRECTIVE_RISK_MITIGATION",
            "source_ids": list(risk["source_ids"]),
            "success_condition": {"type": "risk_mitigated", "subject": risk["subject"]},
        }
    failed = [receipt for receipt in receipts if receipt["status"] == "FAIL"]
    if failed:
        receipt = sorted(failed, key=lambda item: item["receipt_id"])[0]
        return "BLOCKED", {
            "action_id": f"validate:{receipt['subject']}",
            "instruction": f"Fix the evidenced failure and rerun validation for {receipt['subject']}.",
            "reason": receipt["summary"],
            "policy_class": "CORRECTIVE_VALIDATION",
            "source_ids": list(receipt["source_ids"]),
            "success_condition": {"type": "validation_pass", "subject": receipt["subject"]},
        }
    goal_lamps = sorted((lamp for lamp in active_lamps if lamp["type"] == "GOAL"), key=lambda item: item["subject"])
    goal_sources = list(goal_lamps[0]["source_ids"]) if goal_lamps else sorted(
        source_id for source_id, source in sources.items() if source["authority"] == "AUTHORIZED"
    )[:1]
    return "FLOWING", {
        "action_id": "validate:current-goal",
        "instruction": "Execute the next goal-aligned validation and retain its receipt.",
        "reason": "No material conflict or critical unknown currently blocks the goal.",
        "policy_class": "GOAL_VALIDATION",
        "source_ids": goal_sources,
        "success_condition": {"type": "validation_receipt_retained", "status": "PASS"},
    }


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
        {"subject": item["subject"], "source_ids": list(item["source_ids"])} for item in constraints
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

        base, recovery_status, checkpoint_errors = _select_checkpoint(package, as_of, sources, receipts)
        base_checkpoint_id = base["checkpoint_id"]
        state = {(lamp["type"], lamp["subject"]): copy.deepcopy(lamp) for lamp in base["active_lamps"]}
        conflicts = {item["conflict_id"]: copy.deepcopy(item) for item in base["conflicts"]}
        for receipt_conflict in _receipt_conflicts(effective_receipts):
            conflicts[receipt_conflict["conflict_id"]] = receipt_conflict
        dispositions: list[dict[str, Any]] = []
        meaningful: list[dict[str, Any]] = []
        seen_semantics: set[str] = set()
        normalized_changes = [normalize_change(item) for item in require_list(package.get("changes"), "PKG-011", "package.changes")]
        id_payloads: dict[str, set[str]] = {}
        for change in normalized_changes:
            if (
                change["object_type"] == "STATE_CHANGE"
                and _policy_rejection(change, sources, receipts, base_checkpoint_id, as_of) is None
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

            policy_reason = _policy_rejection(change, sources, receipts, base_checkpoint_id, as_of)
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
            if change["operation"] == "RESOLVE":
                requested_conflict_id = change.get("resolves_conflict_id")
                conflict = conflicts.get(requested_conflict_id)
                if (
                    requested_conflict_id != conflict_id
                    or conflict is None
                    or conflict["type"] != change["content_type"]
                    or conflict["subject"] != change["subject"]
                    or conflict["status"] != "DISPUTED"
                    or change["value"] not in [claim["value"] for claim in conflict["claims"]]
                ):
                    dispositions.append(_disposition(change, "REJECTED", "INVALID_CONFLICT_RESOLUTION"))
                    continue
                before_conflict = copy.deepcopy(conflict)
                resolved_lamp = _lamp_from_change(change, receipts)
                state[key] = resolved_lamp
                conflict["status"] = "RESOLVED"
                conflict["resolution_change_id"] = change["change_id"]
                conflicts[conflict["conflict_id"]] = conflict
                disposition = _disposition(change, "APPLIED", "AUTHORIZED_CONFLICT_RESOLUTION")
                disposition["before"] = before_conflict
                disposition["after"] = copy.deepcopy(resolved_lamp)
                dispositions.append(disposition)
                meaningful.append(disposition)
                continue

            existing_conflict = conflicts.get(conflict_id)
            if existing_conflict and existing_conflict["status"] == "DISPUTED":
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
                disposition = _disposition(change, "DISPUTED", "CONFLICT_PRESERVED")
                disposition["before"] = before_conflict
                disposition["after"] = copy.deepcopy(existing_conflict)
                dispositions.append(disposition)
                meaningful.append(disposition)
                continue

            existing = state.get(key)
            if change["operation"] in {"UPDATE", "SUPERSEDE", "MOVE"} and existing is None:
                dispositions.append(_disposition(change, "REJECTED", "TARGET_NOT_ACTIVE"))
                continue
            if change["operation"] == "SUPERSEDE" and change.get("supersedes") != existing["lamp_id"]:
                dispositions.append(_disposition(change, "REJECTED", "INVALID_SUPERSESSION_TARGET"))
                continue
            if existing is not None and parse_instant(change["observed_at"], "CHG-TIME", "change.observed_at") < parse_instant(existing["updated_at"], "LAMP-TIME", "lamp.updated_at"):
                dispositions.append(_disposition(change, "REJECTED", "STALE_STATE"))
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
                disposition = _disposition(change, "APPLIED", "STATE_DEACTIVATED")
                disposition["before"] = copy.deepcopy(existing)
                disposition["after"] = None
                dispositions.append(disposition)
                meaningful.append(disposition)
                continue
            if existing is not None and existing["value"] != change["value"]:
                if change.get("supersedes") == existing["lamp_id"]:
                    updated_lamp = _lamp_from_change(change, receipts)
                    state[key] = updated_lamp
                    disposition = _disposition(change, "APPLIED", "EXPLICIT_SUPERSESSION")
                    disposition["before"] = copy.deepcopy(existing)
                    disposition["after"] = copy.deepcopy(updated_lamp)
                else:
                    opened_conflict = _open_conflict(existing, change, receipts)
                    conflicts[conflict_id] = opened_conflict
                    state.pop(key)
                    disposition = _disposition(change, "DISPUTED", "CONFLICT_PRESERVED")
                    disposition["before"] = copy.deepcopy(existing)
                    disposition["after"] = copy.deepcopy(opened_conflict)
                dispositions.append(disposition)
                meaningful.append(disposition)
                continue
            if existing is not None and existing["value"] == change["value"]:
                merged = copy.deepcopy(existing)
                merged["source_ids"] = sorted(set(merged["source_ids"] + _evidence_source_ids(change, receipts)))
                if merged["source_ids"] == existing["source_ids"]:
                    dispositions.append(_disposition(change, "IGNORED", "NO_NEW_MEANING"))
                    continue
                merged["updated_at"] = max(existing["updated_at"], change["observed_at"])
                state[key] = merged
                disposition = _disposition(change, "APPLIED", "CORROBORATING_SOURCE_MERGED")
                disposition["before"] = copy.deepcopy(existing)
                disposition["after"] = copy.deepcopy(merged)
                dispositions.append(disposition)
                meaningful.append(disposition)
                continue
            created_lamp = _lamp_from_change(change, receipts)
            state[key] = created_lamp
            disposition = _disposition(change, "APPLIED", "AUTHORIZED_MEANINGFUL_CHANGE")
            disposition["before"] = None
            disposition["after"] = copy.deepcopy(created_lamp)
            dispositions.append(disposition)
            meaningful.append(disposition)

        active_lamps = list(state.values())
        last_meaningful_sequence = max(
            (item["sequence"] for item in meaningful),
            default=base["last_sequence"],
        )
        unknowns = _critical_unknowns(effective_receipts, base["unknowns"], active_lamps)
        open_conflicts = sorted((item for item in conflicts.values() if item["status"] == "DISPUTED"), key=lambda item: item["conflict_id"])
        retained_conflicts = sorted(conflicts.values(), key=lambda item: item["conflict_id"])
        semantic_input_changed = bool(meaningful) or bool(effective_receipts) or retained_conflicts != base["conflicts"] or unknowns != base["unknowns"]
        if semantic_input_changed:
            voltage, selected_step = _choose_next_step(open_conflicts, unknowns, effective_receipts, sources, active_lamps)
            next_step = _attach_orientation_context(selected_step, active_lamps)
        else:
            voltage, next_step = base["voltage"], copy.deepcopy(base["primary_next_step"])
        failed_material = sorted((item for item in effective_receipts if item["status"] == "FAIL" and item["material"]), key=lambda item: item["receipt_id"])
        passed_material = sorted((item for item in effective_receipts if item["status"] == "PASS" and item["material"]), key=lambda item: item["receipt_id"])
        if failed_material:
            city_position = failed_material[0]["summary"]
            position_sources = failed_material[0]["source_ids"]
        elif passed_material:
            city_position = passed_material[0]["summary"]
            position_sources = passed_material[0]["source_ids"]
        else:
            city_position = base["city_position"]
            position_sources = list(base["city_position_source_ids"])

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
        for unknown in unknowns:
            referenced_sources.update(unknown["source_ids"])

        checkpoint_payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "checkpoint_id": "pending",
            "created_at": as_of,
            "last_sequence": last_meaningful_sequence,
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
        checkpoint_required = (
            bool(meaningful)
            or city_position != base["city_position"]
            or retained_conflicts != base["conflicts"]
            or unknowns != base["unknowns"]
            or voltage != base["voltage"]
            or next_step != base["primary_next_step"]
        )
        if checkpoint_required:
            checkpoint_payload["checkpoint_id"] = f"cp:{sha256_hex({key: value for key, value in checkpoint_payload.items() if key != 'checkpoint_id'})[:16]}"
            checkpoint = seal_checkpoint(checkpoint_payload)
        else:
            checkpoint = copy.deepcopy(base)
        recovery_card = _derive_recovery_card(checkpoint)
        executed_untrusted = any(item["reason"] == "IMPORTED_TEXT_IS_DATA_NOT_INSTRUCTION" and item["status"] != "IGNORED" for item in dispositions)
        checkpoint_valid, _ = _checkpoint_is_semantically_valid(checkpoint, as_of, sources, receipts)
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
    if condition_type == "risk_mitigated":
        subject = condition.get("subject")
        return not any(
            item.get("type") == "RISK" and item.get("subject") == subject and item.get("material")
            for item in checkpoint.get("active_lamps", [])
        )
    if condition_type == "validation_pass":
        subject = condition.get("subject")
        return any(
            item.get("subject") == subject
            and _receipt_is_trusted_pass(item)
            for item in result.get("validation_receipts", [])
        )
    if condition_type == "validation_receipt_retained":
        return any(
            condition.get("status") == "PASS" and _receipt_is_trusted_pass(item)
            for item in result.get("validation_receipts", [])
        )
    return False
