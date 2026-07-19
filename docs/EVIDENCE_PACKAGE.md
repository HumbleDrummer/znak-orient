# Evidence package contract

The top-level JSON object uses schema `0.3C` and contains exactly:

- `package_id`: stable local identifier;
- `as_of`: timezone-aware ISO-8601 processing boundary;
- `sources`: unique source records with locator, source time, authority assertion, kind, and excerpt;
- `validation_receipts`: subject-scoped validation evidence;
- `checkpoints.primary` and optional `checkpoints.fallbacks`;
- `changes`: ordered `TRACE`, `STATE_CHANGE`, or rejected `RECOVERY_CARD` inputs.

A `STATE_CHANGE` separates:

```json
{
  "content_type": "DECISION",
  "operation": "UPDATE",
  "subject": "demo.entrypoint",
  "value": "python app.py --demo",
  "epistemic": "VERIFIED",
  "authority": "AUTHORIZED",
  "material": true,
  "expected_checkpoint_id": "cp-old-valid-001",
  "source_ids": ["src-entrypoint-new"]
}
```

This is the untrusted input shape. It deliberately has no `impact` member: imported changes may describe an operation, but cannot assert their own canonical effect. An input-supplied `impact` is an unsupported field and the package is rejected. After reduction, a retained meaningful change adds the derived `impact` plus complete `before` and `after` snapshots; together they are transition evidence, not another instruction.

Closed content types: `FACT`, `DECISION`, `GOAL`, `CONSTRAINT`, `RISK`, `UNKNOWN`, `CONNECTION`.

Closed operations: `CREATE`, `UPDATE`, `ACTIVATE`, `DEACTIVATE`, `SUPERSEDE`, `INVALIDATE`, `RESOLVE`, `MOVE`. `MOVE` is recognized but fails closed as `MOVE_NOT_IMPLEMENTED_IN_MVP` until its transition semantics are specified.

The derived output impact is closed and operation-bound:

| Operation | Permitted output impacts |
| --- | --- |
| `CREATE` | `STATE_ACTIVATED`, `STATE_METADATA_UPDATED`, `EVIDENCE_EXTENDED`, `CONFLICT_OPENED`, `CONFLICT_EXTENDED` |
| `UPDATE` | `STATE_METADATA_UPDATED`, `EVIDENCE_EXTENDED`, `CONFLICT_OPENED`, `CONFLICT_EXTENDED` |
| `ACTIVATE` | `STATE_ACTIVATED`, `STATE_METADATA_UPDATED`, `EVIDENCE_EXTENDED`, `CONFLICT_OPENED`, `CONFLICT_EXTENDED` |
| `DEACTIVATE` | `STATE_DEACTIVATED` |
| `SUPERSEDE` | `STATE_REPLACED` |
| `INVALIDATE` | `STATE_DEACTIVATED` |
| `RESOLVE` | `CONFLICT_RESOLVED` |
| `MOVE` | none |

The complete impact vocabulary is `STATE_ACTIVATED`, `STATE_REPLACED`, `STATE_DEACTIVATED`, `STATE_METADATA_UPDATED`, `EVIDENCE_EXTENDED`, `CONFLICT_OPENED`, `CONFLICT_EXTENDED`, and `CONFLICT_RESOLVED`. The validator checks not just vocabulary membership, but also the allowed operation, fixed reason and status, value/meaning binding, source/time and lamp identity, complete conflict-claim preservation, before/after transition shape, and agreement of the latest retained change for every `(content_type, subject)` key with the final checkpoint projection, including `FACT`. A forged but well-shaped transition therefore cannot become valid merely by recomputing the SHA-256 seal.

There is one narrow projection exception for receipt-driven FACT suspension. A retained FACT `after` snapshot need not appear as an active lamp only when its `validation_receipt_id` still identifies a supplied trusted PASS receipt whose assertion hash binds that exact subject/value, whose evidence sources are present in the lamp, and whose pointer remains in `validation_receipt_pointers`. A later incompatible trusted receipt must occur after the lamp update (and no later than a subsequent same-key change when the chain exception is used). The corresponding `CONTRADICTORY_VALIDATION_RECEIPTS` conflict must also preserve an exact suspended claim for that lamp: identity, FACT subject/value, receipt ID, epistemic and authority, source IDs, and observation time must all match. The separate receipt conflict explains the removal from action-driving state; its existence does not excuse any other projection mismatch.

Closed epistemic values: `VERIFIED`, `SUPPORTED`, `INFERRED`, `UNKNOWN`, `DISPUTED`.

Closed authority values: `AUTHORIZED`, `UNAUTHORIZED`, `NOT_APPLICABLE`.

`material` is required and must be a JSON boolean. Exact duplicate JSON object keys, unknown object fields, ambiguous normalized dictionary keys, and non-boolean materiality are rejected rather than coerced or overwritten.

Constraint values are closed to `LOCAL_ONLY`, `LOCAL_ONLY_NO_EXTERNAL_APIS`, `REQUIRES_SEPARATE_USER_CONFIRMATION`, or an object containing only a non-empty unique `forbidden_policy_classes` list drawn from the supported policy classes. `CORRECTIVE_CONSTRAINT_RESOLUTION` cannot be forbidden.

The package is untrusted data. Its authority and validator fields are evaluated against fixed local source-kind and validator-ID policies. A trusted receipt must have internally consistent check statuses; FACT promotion additionally requires a PASS receipt whose `assertion_sha256` binds the exact normalized subject/value assertion and whose evidence sources are carried into the lamp. Receipt references are rejected on changes and lamps whose content type is not `FACT`. Contradictory trusted receipts include differences in status, assertion hash, or position-driving summary; they project a dispute and critical unknown instead of winning by order. If proof receipts themselves conflict, a dependent FACT may use only the exact side selected by an authorized resolution.

Time is causal, not decorative: every source must exist by the change or checkpoint member it supports, a referenced receipt must be checked by the FACT change/lamp time, conflict resolutions cannot predate competing claims, and all retained checkpoint material must exist by `checkpoint.created_at`. Future sources, receipts, and changes also fail closed against `package.as_of`.

Checkpoint source pointers cover the position, step, goal, constraints, lamps, claims, unknowns, recent changes, resolution history, and receipt-pointer provenance, and carry the computed canonical content hash of the currently supplied source. The required `validation_receipt_pointers` ledger stores each retained receipt ID, canonical hash, subject, check time, and source IDs. IDs are immutable across checkpoints; a changed hash, deleted ledger, or unverifiable rollback interval stops replay. A single later receipt is merged against conflict claims preserved in the checkpoint even when earlier raw receipts are omitted. Any dangling, postdated, or mismatched source/receipt reference invalidates that checkpoint and triggers fallback only when lineage remains safe. These are deterministic fixture controls, not signatures, identity authentication, or remote attestation.

For legacy schema-`0.3C` checkpoints whose retained meaningful changes have the exact pre-`impact` shape, migration is integrity-first and fail-closed. The original seal must verify before inference; then every missing impact must have exactly one valid derivation under the current matrix and before/after semantics. The runtime migrates a copy, leaves the legacy bytes untouched, adds only those impacts, reseals the candidate, and runs the full current semantic validation. Mixed legacy/current histories, corrupted seals, ambiguous derivation, or invalid current semantics make that candidate unusable. If selected, its base status ends in `_LEGACY_MIGRATED`; the returned current checkpoint receives a new ID and processing time.

Retained changes are ordered and, for each repeated `(content_type, subject)` key, must form a continuous snapshot chain: each prior `after` must equal the next `before`. The only exception is receipt-driven FACT suspension described above. If the prior FACT `after` is preserved as that exact suspended claim, a subsequent change for the same FACT may have `before: null`, reflecting that the FACT is no longer active. No other missing link, reordered transition, or implicit reset is accepted.

History compaction is evidenced as semantic equivalence, not byte identity. In the covered fixture, the compact path and full-history path converge on the same position-driving checkpoint fields and the same final meaningful transition after the compact tail explicitly rebases `expected_checkpoint_id` to the checkpoint produced by its prefix. Checkpoint IDs, seals, creation times, and retained-history prefixes may legitimately differ. Omitting that CAS rebase is stale-state input and must not be treated as equivalent replay.
