"""Canonical serialization and integrity helpers."""

from __future__ import annotations

import copy
import hashlib
import json
import unicodedata
from typing import Any


def normalize_text(value: str) -> str:
    """Normalize Unicode and insignificant whitespace without changing meaning."""

    return " ".join(unicodedata.normalize("NFC", value).split())


def normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    if isinstance(value, dict):
        normalized_keys: list[str] = []
        seen_keys: set[str] = set()
        for key in value:
            normalized_key = normalize_text(str(key))
            if normalized_key in seen_keys:
                raise TypeError("dictionary keys collide after canonical normalization")
            seen_keys.add(normalized_key)
            normalized_keys.append(normalized_key)
        return {
            normalized_key: normalize_value(item)
            for normalized_key, item in zip(normalized_keys, value.values(), strict=True)
        }
    if value is None or isinstance(value, (bool, int)):
        return value
    raise TypeError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    normalized = normalize_value(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def checkpoint_integrity_value(checkpoint: dict[str, Any]) -> str:
    payload = copy.deepcopy(checkpoint)
    payload.pop("integrity", None)
    return sha256_hex(payload)


def seal_checkpoint(checkpoint: dict[str, Any]) -> dict[str, Any]:
    sealed = copy.deepcopy(checkpoint)
    sealed["integrity"] = {
        "algorithm": "sha256",
        "value": checkpoint_integrity_value(sealed),
    }
    return sealed


def verify_checkpoint_integrity(checkpoint: dict[str, Any]) -> bool:
    integrity = checkpoint.get("integrity")
    if not isinstance(integrity, dict) or integrity.get("algorithm") != "sha256":
        return False
    expected = integrity.get("value")
    return isinstance(expected, str) and expected == checkpoint_integrity_value(checkpoint)
