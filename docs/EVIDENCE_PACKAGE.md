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

Closed content types: `FACT`, `DECISION`, `GOAL`, `CONSTRAINT`, `RISK`, `UNKNOWN`, `CONNECTION`.

Closed operations: `CREATE`, `UPDATE`, `ACTIVATE`, `DEACTIVATE`, `SUPERSEDE`, `INVALIDATE`, `RESOLVE`, `MOVE`. `MOVE` is recognized but fails closed as `MOVE_NOT_IMPLEMENTED_IN_MVP` until its transition semantics are specified.

Closed epistemic values: `VERIFIED`, `SUPPORTED`, `INFERRED`, `UNKNOWN`, `DISPUTED`.

Closed authority values: `AUTHORIZED`, `UNAUTHORIZED`, `NOT_APPLICABLE`.

`material` is required and must be a JSON boolean. Exact duplicate JSON object keys, unknown object fields, ambiguous normalized dictionary keys, and non-boolean materiality are rejected rather than coerced or overwritten.

Constraint values are closed to `LOCAL_ONLY`, `LOCAL_ONLY_NO_EXTERNAL_APIS`, `REQUIRES_SEPARATE_USER_CONFIRMATION`, or an object containing only a non-empty unique `forbidden_policy_classes` list drawn from the supported policy classes. `CORRECTIVE_CONSTRAINT_RESOLUTION` cannot be forbidden.

The package is untrusted data. Its authority and validator fields are evaluated against fixed local source-kind and validator-ID policies. A trusted receipt must have internally consistent check statuses; FACT promotion additionally requires a PASS receipt whose `assertion_sha256` binds the exact normalized subject/value assertion and whose evidence sources are carried into the lamp. Receipt references are rejected on non-FACT changes and lamps. Contradictory trusted receipts include differences in status, assertion hash, or position-driving summary; they project a dispute and critical unknown instead of winning by order. If proof receipts themselves conflict, a dependent FACT may use only the exact side selected by an authorized resolution.

Time is causal, not decorative: every source must exist by the change or checkpoint member it supports, a referenced receipt must be checked by the FACT change/lamp time, conflict resolutions cannot predate competing claims, and all retained checkpoint material must exist by `checkpoint.created_at`. Future sources, receipts, and changes also fail closed against `package.as_of`.

Checkpoint source pointers cover the position, step, goal, constraints, lamps, claims, unknowns, recent changes, resolution history, and receipt-pointer provenance, and carry the computed canonical content hash of the currently supplied source. The required `validation_receipt_pointers` ledger stores each retained receipt ID, canonical hash, subject, check time, and source IDs. IDs are immutable across checkpoints; a changed hash, deleted ledger, or unverifiable rollback interval stops replay. A single later receipt is merged against conflict claims preserved in the checkpoint even when earlier raw receipts are omitted. Any dangling, postdated, or mismatched source/receipt reference invalidates that checkpoint and triggers fallback only when lineage remains safe. These are deterministic fixture controls, not signatures, identity authentication, or remote attestation.
