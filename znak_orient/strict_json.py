"""Fail-closed JSON parsing for evidence-package boundaries."""

from __future__ import annotations

import json
from typing import Any


class StrictJsonError(ValueError):
    """Raised when JSON syntax or object identity is ambiguous."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise StrictJsonError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def strict_json_loads(text: str) -> Any:
    """Parse JSON while rejecting exact duplicate object keys at every depth."""

    try:
        return json.loads(text, object_pairs_hook=_unique_object)
    except json.JSONDecodeError as exc:
        raise StrictJsonError(str(exc)) from exc
