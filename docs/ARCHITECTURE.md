# Architecture summary

## Runtime flow

```text
untrusted JSON package
  -> duplicate-key rejection + closed structural validation
  -> canonical Unicode/whitespace normalization
  -> deterministic ID and semantic deduplication
  -> source, time, epistemic, authority, and receipt policy gates
  -> ordered state-change reduction
  -> conflict and critical-unknown projection
  -> voltage + exactly one corrective next step
  -> SHA-256-sealed canonical checkpoint
  -> one-way Recovery Card derivation
  -> scoped orientation-transform receipt
```

The CLI atomically replaces the requested result file with a flushed temporary file and `os.replace`. The HTTP server processes a package in memory and returns JSON without storing the upload.

## X30 object mapping

| Object | MVP representation | Authority |
| --- | --- | --- |
| `TRACE` | Intake item with no state effect; always expires in this MVP | Never canonical state; meaningful input must arrive as a `STATE_CHANGE` |
| `STATE_CHANGE` | Normalized operation plus epistemic/authority/source/time and retained before/after projection | Reducer input after policy checks |
| `PIN` | Authorized `USER_PIN` source feeding durable goal/constraint lamps | Source, not an executable instruction |
| `LAMP` | Active typed item keyed by `(content_type, subject)` | Canonical checkpoint state |
| `CHECKPOINT` | Compact sealed position with lamps, recent meaningful changes, conflicts, unknowns, voltage, one step, source pointers, and immutable receipt pointers | Source of truth for recovery |
| `RECOVERY_CARD` | One-way projection from a verified checkpoint | Explicitly non-authoritative and non-writeable |
| `SOURCE_POINTER` | ID, locator, kind, source time, authority assertion, and computed content hash | Provenance pointer |
| `VALIDATION_RECEIPT_POINTER` | Receipt ID, canonical receipt hash, subject, check time, and source IDs | Compact append-only identity ledger across checkpoints |
| `VALIDATION_RECEIPT` | Subject-scoped PASS/FAIL/UNKNOWN evidence plus validator ID and checks | Can block; promotion requires local trusted-validator policy |

## Four independent axes

Content, operation, epistemic status, and authority are validated separately. `material` is a required JSON boolean, never a truthy/falsy coercion. A user decision can authorize a goal or constraint but cannot make a fact true. A newer claim does not win by timestamp. A different value opens a conflict unless it explicitly and validly supersedes the active lamp. `DISPUTED` material claims are removed from action-driving state and retained under the conflict object. There must be exactly one active material `GOAL`, or exactly one open material `GOAL` conflict carrying the contested goal context.

## Checkpoint and recovery

A checkpoint is valid only when its sealed canonical content and semantic invariants validate. The checks include a closed top-level and nested shape, positive bounded history cursors, exactly one goal context, source/receipt/claim times that do not postdate the object they support, source pointers with hashes bound to the supplied records, required receipt ID/hash pointers, authorized source kinds for authority-driving lamps and resolutions, value-bound trusted PASS receipts for FACT lamps, and a recomputed goal/constraint-aligned next step. A resolved conflict must select one preserved claim, retain chronological resolution history, and correspond to the active lamp. Receipt references are permitted only on FACT lamps, and a disputed proof receipt cannot support another FACT unless its own conflict is resolved to that exact claim.

Recovery validates every primary/fallback candidate, then selects the newest valid checkpoint by `created_at`, semantic cursor, and a deterministic tie-break. Receipt IDs found in any retained candidate remain reserved even when a newer checkpoint is otherwise invalid. If fallback would cross an interval whose receipt lineage is missing, replay stops instead of silently accepting a reused identity. A single trusted tail receipt is compared with claims already compacted into the checkpoint, so older raw receipts need not be reloaded. If no checkpoint is valid, processing stops with `OrientationError`; it never fabricates state. `checkpoint_id` is a cooperative stale-state token for this fixture, while `integrity.value` is the canonical-content digest; the ID alone is not a cryptographic concurrency token.

A new checkpoint is produced only when a meaningful state change, new receipt pointer, material receipt effect, conflict, unknown, voltage, position, or primary-step change exists. Noise-only traces and semantic duplicates remain visible in intake but do not create a checkpoint.

## Next-step policy

The result stores `primary_next_step` as one object, never a list. Selection order is fixed:

1. material open conflict;
2. critical unknown;
3. active material risk;
4. failed validation;
5. a goal-aligned validation step.

Ties use stable identifiers, not recency. Each step carries a reason, source IDs, goal linkage, the full active constraint context, and a closed success-condition type evaluated by `evaluate_success_condition`. Conditions bind the exact subject, content type where applicable, assertion hash, and time boundary; an open dispute in the same lineage keeps an older condition false. After an authorized receipt-conflict resolution, only the selected claim can drive position, validation success, or a dependent FACT; retained losing receipts remain history.

Constraint values use a closed machine vocabulary: `LOCAL_ONLY`, `LOCAL_ONLY_NO_EXTERNAL_APIS`, `REQUIRES_SEPARATE_USER_CONFIRMATION`, or `{ "forbidden_policy_classes": [...] }`. If an active constraint forbids the selected policy class, voltage becomes `BROKEN` and the sole step becomes `CORRECTIVE_CONSTRAINT_RESOLUTION`. That meta-correction class cannot forbid itself.

`MOVE` remains in the closed X30 operation vocabulary but is deliberately rejected as `MOVE_NOT_IMPLEMENTED_IN_MVP` until a non-ambiguous state-transition contract exists.

## Prompt-injection boundary

Exact duplicate JSON keys and unsupported object fields are rejected before reduction; imported text is never allowed to redefine the package contract.

The safe claim is “imported instruction text is inert by construction,” not “prompt injection is solved.” The runtime has no model call and never concatenates input into a prompt, query, template, path, or process invocation. Dynamic UI values use DOM `textContent`. The server applies CSP, `nosniff`, frame denial, no-referrer, no-store, a 1 MB request limit, exact route matching, loopback binding by default, and loopback Host/Origin validation unless the explicit non-loopback override is used.

## Orientation guide

The animated figure is a presentation-only projection inside the canonical next-step module. Its label is selected from a closed voltage-to-copy map, while the module's only full action node is the exact `primary_next_step.instruction`, never a second recommendation. Color and the single visible marker follow the semantic voltage token. Each voltage has one short finite motion cue, replayed only after a new result; all CSS motion is disabled under `prefers-reduced-motion`. The guide has no write path, model call, persistence, or authority.

## Persistence boundary

This vertical slice intentionally uses JSON checkpoints and CLI artifacts, not SQLite or a production event store. It proves deterministic reduction, scoped atomic artifact replacement, fallback-checkpoint recovery, and equivalence for the tested package whose older history is already covered by its checkpoint. It does not prove that the compression is globally minimal or better than raw notes, nor multi-process concurrency, power-loss behavior, database recovery, remote identity, production IAM, or canonical X30 substrate equivalence.
