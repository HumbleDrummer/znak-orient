"""Closed vocabularies and input validation for ZNAK ORIENT 0.3C."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .canonical import normalize_text, normalize_value, sha256_hex

SCHEMA_VERSION = "0.3C"
CONTENT_TYPES = {"FACT", "DECISION", "GOAL", "CONSTRAINT", "RISK", "UNKNOWN", "CONNECTION"}
OPERATIONS = {"CREATE", "UPDATE", "ACTIVATE", "DEACTIVATE", "SUPERSEDE", "INVALIDATE", "RESOLVE", "MOVE"}
EPISTEMIC_STATES = {"VERIFIED", "SUPPORTED", "INFERRED", "UNKNOWN", "DISPUTED"}
AUTHORITIES = {"AUTHORIZED", "UNAUTHORIZED", "NOT_APPLICABLE"}
OBJECT_TYPES = {"TRACE", "STATE_CHANGE", "RECOVERY_CARD"}
RECEIPT_STATUSES = {"PASS", "FAIL", "UNKNOWN"}
TRUSTED_VALIDATOR_IDS = {
    "SYNTHETIC_CLEAN_CHECKOUT_FIXTURE",
    "ZNAK_ORIENT_LOCAL_TEST_RUNNER",
}
TRUSTED_AUTHORITY_SOURCE_KINDS = {"USER_PIN", "USER_DECISION", "DECISION_RECORD"}


class ContractError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ContractError(code, message)


def require_mapping(value: Any, code: str, name: str) -> dict[str, Any]:
    require(isinstance(value, dict), code, f"{name} must be an object")
    return value


def require_list(value: Any, code: str, name: str) -> list[Any]:
    require(isinstance(value, list), code, f"{name} must be an array")
    return value


def require_text(value: Any, code: str, name: str) -> str:
    require(isinstance(value, str) and bool(normalize_text(value)), code, f"{name} must be non-empty text")
    return normalize_text(value)


def require_closed_keys(
    value: dict[str, Any],
    required: set[str],
    allowed: set[str],
    code: str,
    name: str,
) -> None:
    keys = set(value)
    require(required.issubset(keys), code, f"{name} is missing required fields")
    require(keys.issubset(allowed), code, f"{name} contains unsupported fields")


def parse_instant(value: Any, code: str, name: str) -> datetime:
    text = require_text(value, code, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(code, f"{name} must be an ISO-8601 timestamp") from exc
    require(parsed.tzinfo is not None, code, f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate_source(source: Any) -> dict[str, Any]:
    item = require_mapping(source, "SRC-001", "source")
    source_fields = {"source_id", "kind", "locator", "captured_at", "authority", "excerpt"}
    require_closed_keys(
        item,
        source_fields - {"excerpt"},
        source_fields,
        "SRC-001",
        "source",
    )
    source_id = require_text(item.get("source_id"), "SRC-002", "source_id")
    authority = require_text(item.get("authority"), "SRC-003", "source.authority")
    require(authority in AUTHORITIES, "SRC-003", f"unsupported source authority {authority!r}")
    captured_at = require_text(item.get("captured_at"), "SRC-004", "source.captured_at")
    parse_instant(captured_at, "SRC-004", "source.captured_at")
    excerpt = item.get("excerpt", "")
    require(isinstance(excerpt, str), "SRC-007", "source.excerpt must be text")
    normalized = {
        "source_id": source_id,
        "kind": require_text(item.get("kind"), "SRC-005", "source.kind"),
        "locator": require_text(item.get("locator"), "SRC-006", "source.locator"),
        "captured_at": captured_at,
        "authority": authority,
        "excerpt": normalize_text(excerpt),
    }
    normalized["content_sha256"] = sha256_hex(normalized)
    return normalized


def validate_receipt(receipt: Any) -> dict[str, Any]:
    item = require_mapping(receipt, "RCP-001", "validation receipt")
    receipt_fields = {
        "receipt_id",
        "validator_id",
        "subject",
        "status",
        "checked_at",
        "material",
        "summary",
        "source_ids",
        "checks",
        "assertion_sha256",
    }
    require_closed_keys(
        item,
        receipt_fields - {"assertion_sha256"},
        receipt_fields,
        "RCP-001",
        "validation receipt",
    )
    status = require_text(item.get("status"), "RCP-002", "receipt.status")
    require(status in RECEIPT_STATUSES, "RCP-002", f"unsupported receipt status {status!r}")
    checked_at = require_text(item.get("checked_at"), "RCP-003", "receipt.checked_at")
    parse_instant(checked_at, "RCP-003", "receipt.checked_at")
    source_ids = [require_text(value, "RCP-004", "receipt.source_id") for value in require_list(item.get("source_ids"), "RCP-004", "receipt.source_ids")]
    require(bool(source_ids), "RCP-004", "receipt.source_ids cannot be empty")
    raw_checks = require_list(item.get("checks"), "RCP-009", "receipt.checks")
    require(bool(raw_checks), "RCP-009", "receipt.checks cannot be empty")
    checks: list[dict[str, str]] = []
    check_ids: set[str] = set()
    for raw_check in raw_checks:
        check = require_mapping(raw_check, "RCP-009", "receipt.check")
        require_closed_keys(check, {"id", "status"}, {"id", "status"}, "RCP-009", "receipt.check")
        check_id = require_text(check.get("id"), "RCP-009", "receipt.check.id")
        check_status = require_text(check.get("status"), "RCP-009", "receipt.check.status")
        require(check_status in RECEIPT_STATUSES, "RCP-009", "receipt check has unsupported status")
        require(check_id not in check_ids, "RCP-009", "receipt check IDs must be unique")
        check_ids.add(check_id)
        checks.append({"id": check_id, "status": check_status})
    require(status != "PASS" or all(check["status"] == "PASS" for check in checks), "RCP-010", "PASS receipt contains a non-PASS check")
    require(status != "FAIL" or any(check["status"] == "FAIL" for check in checks), "RCP-010", "FAIL receipt has no failed check")
    require(status != "UNKNOWN" or any(check["status"] == "UNKNOWN" for check in checks), "RCP-010", "UNKNOWN receipt has no unknown check")
    material = item.get("material")
    require(isinstance(material, bool), "RCP-012", "receipt.material must be a JSON boolean")
    assertion_sha256 = require_text(item.get("assertion_sha256"), "RCP-011", "receipt.assertion_sha256") if item.get("assertion_sha256") is not None else ""
    require(
        not assertion_sha256 or (len(assertion_sha256) == 64 and all(character in "0123456789abcdef" for character in assertion_sha256)),
        "RCP-011",
        "receipt.assertion_sha256 must be a lowercase SHA-256 digest",
    )
    require(status != "PASS" or bool(assertion_sha256), "RCP-011", "PASS receipt must bind an assertion hash")
    return {
        "receipt_id": require_text(item.get("receipt_id"), "RCP-005", "receipt_id"),
        "validator_id": require_text(item.get("validator_id"), "RCP-008", "receipt.validator_id"),
        "subject": require_text(item.get("subject"), "RCP-006", "receipt.subject"),
        "status": status,
        "checked_at": checked_at,
        "material": material,
        "summary": require_text(item.get("summary"), "RCP-007", "receipt.summary"),
        "source_ids": sorted(set(source_ids)),
        "checks": checks,
        "assertion_sha256": assertion_sha256,
    }


def normalize_change(change: Any) -> dict[str, Any]:
    item = require_mapping(change, "CHG-001", "change")
    object_type = require_text(item.get("object_type"), "CHG-002", "change.object_type")
    require(object_type in OBJECT_TYPES, "CHG-002", f"unsupported object type {object_type!r}")
    common_fields = {"change_id", "object_type", "sequence", "observed_at", "source_ids"}
    if object_type == "STATE_CHANGE":
        state_fields = common_fields | {
            "content_type",
            "operation",
            "subject",
            "value",
            "epistemic",
            "authority",
            "material",
            "expected_checkpoint_id",
            "validation_receipt_id",
            "supersedes",
            "resolves_conflict_id",
        }
        require_closed_keys(
            item,
            common_fields | {"content_type", "operation", "subject", "value", "epistemic", "authority", "material"},
            state_fields,
            "CHG-001",
            "STATE_CHANGE",
        )
    elif object_type == "TRACE":
        trace_fields = common_fields | {"text"}
        require_closed_keys(item, trace_fields, trace_fields, "CHG-001", "TRACE")
    else:
        card_fields = common_fields | {"value"}
        require_closed_keys(item, card_fields, card_fields, "CHG-001", "RECOVERY_CARD")
    sequence = item.get("sequence")
    require(isinstance(sequence, int) and not isinstance(sequence, bool) and sequence > 0, "CHG-003", "change.sequence must be a positive integer")
    observed_at = require_text(item.get("observed_at"), "CHG-004", "change.observed_at")
    parse_instant(observed_at, "CHG-004", "change.observed_at")
    source_ids = [require_text(value, "CHG-005", "change.source_id") for value in require_list(item.get("source_ids", []), "CHG-005", "change.source_ids")]
    normalized: dict[str, Any] = {
        "change_id": require_text(item.get("change_id"), "CHG-006", "change_id"),
        "object_type": object_type,
        "sequence": sequence,
        "observed_at": observed_at,
        "source_ids": sorted(set(source_ids)),
        "text": "",
    }
    if object_type == "STATE_CHANGE":
        content_type = require_text(item.get("content_type"), "CHG-007", "change.content_type")
        operation = require_text(item.get("operation"), "CHG-008", "change.operation")
        epistemic = require_text(item.get("epistemic"), "CHG-009", "change.epistemic")
        authority = require_text(item.get("authority"), "CHG-010", "change.authority")
        require(content_type in CONTENT_TYPES, "CHG-007", f"unsupported content type {content_type!r}")
        require(operation in OPERATIONS, "CHG-008", f"unsupported operation {operation!r}")
        require(epistemic in EPISTEMIC_STATES, "CHG-009", f"unsupported epistemic state {epistemic!r}")
        require(authority in AUTHORITIES, "CHG-010", f"unsupported authority {authority!r}")
        material = item.get("material")
        require(isinstance(material, bool), "CHG-012", "change.material must be a JSON boolean")
        for optional_field in (
            "expected_checkpoint_id",
            "validation_receipt_id",
            "supersedes",
            "resolves_conflict_id",
        ):
            require(
                optional_field not in item or isinstance(item[optional_field], str),
                "CHG-013",
                f"change.{optional_field} must be text when present",
            )
        normalized.update(
            {
                "content_type": content_type,
                "operation": operation,
                "subject": require_text(item.get("subject"), "CHG-011", "change.subject"),
                "value": normalize_value(item.get("value")),
                "epistemic": epistemic,
                "authority": authority,
                "material": material,
                "expected_checkpoint_id": normalize_text(item.get("expected_checkpoint_id", "")) if isinstance(item.get("expected_checkpoint_id", ""), str) else "",
                "validation_receipt_id": normalize_text(item.get("validation_receipt_id", "")) if isinstance(item.get("validation_receipt_id", ""), str) else "",
                "supersedes": normalize_text(item.get("supersedes", "")) if isinstance(item.get("supersedes", ""), str) else "",
                "resolves_conflict_id": normalize_text(item.get("resolves_conflict_id", "")) if isinstance(item.get("resolves_conflict_id", ""), str) else "",
            }
        )
    elif object_type == "TRACE":
        normalized["text"] = normalize_text(require_text(item.get("text"), "CHG-014", "change.text"))
    elif object_type == "RECOVERY_CARD":
        normalized["value"] = normalize_value(item.get("value", {}))
    return normalized


def semantic_fingerprint(change: dict[str, Any]) -> str:
    ignored = {"change_id", "sequence", "observed_at"}
    return sha256_hex({key: value for key, value in change.items() if key not in ignored})
