# MEMORIA lifecycle

MEMORIA is an optional, local cache layer for orientation evidence. It is
derived state: the canonical package, checkpoint, and receipt ledger remain the
source of truth.

## Key and entry integrity

Each entry uses a deterministic SHA-256 key over the source identity and the
source `content_sha256`. Checkpoints use `checkpoint:<checkpoint_id>` as the
source identity and their canonical integrity digest as `content_sha256`.
The cached value also retains its own canonical digest.
A changed value therefore reports `CORRUPT` instead of being silently reused.

## Lifecycle states

| State | Meaning | Action |
| --- | --- | --- |
| `HIT` | Key exists, value digest matches, and TTL has not elapsed. | Reuse the value. |
| `MISS` | No entry exists for the requested key. | Recompute and insert. |
| `STALE` | Entry exists but its TTL has elapsed. | Recompute; stale data is not returned. |
| `CORRUPT` | Stored value no longer matches its sealed digest. | Do not return it; recompute. |
| `PURGE` | Entries backed by a `FAIL` receipt source were removed. | Recompute affected evidence. |

`DISPUTED` is a separate cache disposition, not part of the five closed
`MEMORIA_STATES` counters. A `CONFLICT_OPENED` event marks related source-backed
entries disputed; disputed values are never returned until they are explicitly
recomputed or purged.

`purge_for_receipt` only acts on receipts whose status is `FAIL` and only on
entries sharing one of that receipt's `source_ids`. PASS and UNKNOWN receipts
do not purge cache entries.

An accepted material `STATE_CHANGE` purges entries backed by the change's
evidence sources. Non-material changes and entries backed by unrelated sources
remain cached.

## Metrics and Recovery Card

The cache exposes a defensive snapshot of counters for `hit`, `miss`, `stale`,
`corrupt`, and `purge`. When a cache is explicitly supplied to `orient`, this
snapshot is copied into the Recovery Card as `memoria_metrics`. It is read-only,
non-authoritative, and does not change the default output shape when no cache is
supplied.

Metrics are observability only. They do not turn a successful orientation run
into proof that the project is complete, and they do not repair a failed
validation receipt.
