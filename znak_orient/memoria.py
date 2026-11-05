"""Small deterministic cache primitives for MEMORIA recovery state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from .canonical import checkpoint_content_sha256, sha256_hex
from .contracts import MEMORIA_STATES


def memoria_cache_key(source: str, content_sha256: str) -> str:
    """Return a stable key bound to the source identity and content digest."""

    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a non-empty string")
    if (
        not isinstance(content_sha256, str)
        or len(content_sha256) != 64
        or any(character not in "0123456789abcdef" for character in content_sha256)
    ):
        raise ValueError("content_sha256 must be a lowercase SHA-256 digest")
    return sha256_hex({"source": source, "content_sha256": content_sha256})


def checkpoint_cache_key(checkpoint: dict[str, Any]) -> str:
    """Return a deterministic MEMORIA key for a canonical checkpoint."""

    checkpoint_id = checkpoint.get("checkpoint_id")
    if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
        raise ValueError("checkpoint.checkpoint_id must be a non-empty string")
    return memoria_cache_key(
        f"checkpoint:{checkpoint_id}", checkpoint_content_sha256(checkpoint)
    )


@dataclass
class _Entry:
    value: Any
    source_ids: frozenset[str]
    content_sha256: str
    stored_at: datetime
    value_sha256: str


class MemoriaCache:
    """In-memory cache with explicit HIT/STALE/CORRUPT/PURGE outcomes."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        if not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be a positive integer")
        self._ttl = timedelta(seconds=ttl_seconds)
        self._entries: dict[str, _Entry] = {}
        self._disputed_keys: set[str] = set()
        self._metrics = {state.lower(): 0 for state in MEMORIA_STATES}

    def put(
        self,
        source: str,
        content_sha256: str,
        value: Any,
        *,
        source_ids: Iterable[str] = (),
        now: datetime | None = None,
    ) -> str:
        key = memoria_cache_key(source, content_sha256)
        stored_at = now or datetime.now(timezone.utc)
        if stored_at.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        self._entries[key] = _Entry(
            value=value,
            source_ids=frozenset(source_ids),
            content_sha256=content_sha256,
            stored_at=stored_at,
            value_sha256=sha256_hex(value),
        )
        return key

    def put_checkpoint(
        self,
        checkpoint: dict[str, Any],
        *,
        source_ids: Iterable[str] = (),
        now: datetime | None = None,
    ) -> str:
        """Cache a checkpoint using its id and canonical content digest."""

        checkpoint_id = checkpoint.get("checkpoint_id")
        if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
            raise ValueError("checkpoint.checkpoint_id must be a non-empty string")
        return self.put(
            f"checkpoint:{checkpoint_id}",
            checkpoint_content_sha256(checkpoint),
            checkpoint,
            source_ids=source_ids,
            now=now,
        )

    def get_checkpoint(
        self, checkpoint: dict[str, Any], *, now: datetime | None = None
    ) -> tuple[str, Any | None]:
        """Read a checkpoint by its deterministic canonical key."""

        checkpoint_id = checkpoint.get("checkpoint_id")
        if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
            raise ValueError("checkpoint.checkpoint_id must be a non-empty string")
        return self.get(
            f"checkpoint:{checkpoint_id}",
            checkpoint_content_sha256(checkpoint),
            now=now,
        )

    def get(
        self,
        source: str,
        content_sha256: str,
        *,
        now: datetime | None = None,
    ) -> tuple[str, Any | None]:
        key = memoria_cache_key(source, content_sha256)
        entry = self._entries.get(key)
        if entry is None:
            self._metrics["miss"] += 1
            return "MISS", None
        if key in self._disputed_keys:
            return "DISPUTED", None
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if current - entry.stored_at >= self._ttl:
            self._metrics["stale"] += 1
            return "STALE", None
        if sha256_hex(entry.value) != entry.value_sha256:
            self._metrics["corrupt"] += 1
            return "CORRUPT", None
        self._metrics["hit"] += 1
        return "HIT", entry.value

    def mark_conflict_opened(self, source_ids: Iterable[str]) -> int:
        """Mark source-backed entries disputed after a material conflict opens."""

        sources = set(source_ids)
        keys = [key for key, entry in self._entries.items() if entry.source_ids & sources]
        self._disputed_keys.update(keys)
        return len(keys)

    def purge_for_state_change(self, source_ids: Iterable[str], *, material: bool) -> int:
        """Purge source-backed entries after an accepted material state change."""

        if not material:
            return 0
        sources = set(source_ids)
        if not sources:
            return 0
        keys = [key for key, entry in self._entries.items() if entry.source_ids & sources]
        for key in keys:
            del self._entries[key]
            self._disputed_keys.discard(key)
        self._metrics["purge"] += len(keys)
        return len(keys)

    def purge_for_receipt(self, receipt: dict[str, Any]) -> int:
        """Purge entries backed by sources of a material FAIL receipt."""

        if receipt.get("status") != "FAIL":
            return 0
        source_ids = set(receipt.get("source_ids", []))
        if not source_ids:
            return 0
        keys = [key for key, entry in self._entries.items() if entry.source_ids & source_ids]
        for key in keys:
            del self._entries[key]
            self._disputed_keys.discard(key)
        self._metrics["purge"] += len(keys)
        return len(keys)

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def metrics(self) -> dict[str, int]:
        """Return a defensive, deterministic snapshot of lifecycle counters."""

        return {name: self._metrics[name] for name in sorted(self._metrics)}


__all__ = ["MEMORIA_STATES", "MemoriaCache", "memoria_cache_key"]
