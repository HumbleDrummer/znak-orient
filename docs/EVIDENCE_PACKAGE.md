# Evidence package contract

The top-level JSON object uses schema `0.3C` and contains:

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
  "expected_checkpoint_id": "cp-old-valid-001",
  "source_ids": ["src-entrypoint-new"]
}
```

Closed content types: `FACT`, `DECISION`, `GOAL`, `CONSTRAINT`, `RISK`, `UNKNOWN`, `CONNECTION`.

Closed operations: `CREATE`, `UPDATE`, `ACTIVATE`, `DEACTIVATE`, `SUPERSEDE`, `INVALIDATE`, `RESOLVE`, `MOVE`. `MOVE` is recognized but fails closed as `MOVE_NOT_IMPLEMENTED_IN_MVP` until its transition semantics are specified.

Closed epistemic values: `VERIFIED`, `SUPPORTED`, `INFERRED`, `UNKNOWN`, `DISPUTED`.

Closed authority values: `AUTHORIZED`, `UNAUTHORIZED`, `NOT_APPLICABLE`.

The package is untrusted data. Its authority and validator fields are evaluated against fixed local source-kind and validator-ID policies. A trusted receipt must have internally consistent check statuses; FACT promotion additionally requires a PASS receipt whose `assertion_sha256` binds the exact normalized subject/value assertion and whose evidence sources are carried into the lamp. Contradictory trusted receipts project a dispute and critical unknown instead of winning by order. Future sources, receipts, and changes fail closed against `package.as_of`.

Checkpoint source pointers carry the computed canonical content hash of the currently supplied source. Any dangling or mismatched source/receipt reference invalidates that checkpoint and triggers fallback when available. These are deterministic fixture controls, not signatures, identity authentication, or remote attestation.
