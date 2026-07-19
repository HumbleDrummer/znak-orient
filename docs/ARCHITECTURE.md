# Architecture summary

## Runtime flow

```text
untrusted JSON package
  -> strict structural validation
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
| `TRACE` | Intake item with no state effect; expires unless meaningful | Never canonical state |
| `STATE_CHANGE` | Normalized operation plus epistemic/authority/source/time and retained before/after projection | Reducer input after policy checks |
| `PIN` | Authorized `USER_PIN` source feeding durable goal/constraint lamps | Source, not an executable instruction |
| `LAMP` | Active typed item keyed by `(content_type, subject)` | Canonical checkpoint state |
| `CHECKPOINT` | Compact sealed position with lamps, recent meaningful changes, conflicts, unknowns, voltage, one step, and source pointers | Source of truth for recovery |
| `RECOVERY_CARD` | One-way projection from a verified checkpoint | Explicitly non-authoritative and non-writeable |
| `SOURCE_POINTER` | ID, locator, kind, source time, authority assertion, and computed content hash | Provenance pointer |
| `VALIDATION_RECEIPT` | Subject-scoped PASS/FAIL/UNKNOWN evidence plus validator ID and checks | Can block; promotion requires local trusted-validator policy |

## Four independent axes

Content, operation, epistemic status, and authority are validated separately. A user decision can authorize a goal or constraint but cannot make a fact true. A newer claim does not win by timestamp. A different value opens a conflict unless it explicitly and validly supersedes the active lamp. `DISPUTED` material claims are removed from action-driving state and retained under the conflict object.

## Checkpoint and recovery

A checkpoint is valid only when its sealed canonical content and semantic invariants validate. The checks include non-future timestamps, one authorized active goal (unless a goal conflict is open), resolvable source pointers with content hashes bound to the supplied source records, authorized source kinds for authority-driving lamps, value-bound trusted PASS receipts for FACT lamps, resolved provenance for any other receipt reference, closed conflict/unknown shapes, and a recomputed goal/constraint-aligned next step. Recovery tries the primary checkpoint and then fallbacks in supplied order. It replays only meaningful changes beyond the selected cursor. If no checkpoint is valid, processing stops with `OrientationError`; it never fabricates state.

A new checkpoint is produced only when a meaningful state change, material receipt effect, conflict, unknown, voltage, position, or primary-step change exists. Noise-only traces and duplicates remain visible in intake but do not create a checkpoint.

## Next-step policy

The result stores `primary_next_step` as one object, never a list. Selection order is fixed:

1. material open conflict;
2. critical unknown;
3. failed validation;
4. a goal-aligned validation step.

Ties use stable identifiers, not recency. Each step carries a reason, source IDs, goal linkage, and a closed success-condition type evaluated by `evaluate_success_condition`.

`MOVE` remains in the closed X30 operation vocabulary but is deliberately rejected as `MOVE_NOT_IMPLEMENTED_IN_MVP` until a non-ambiguous state-transition contract exists.

## Prompt-injection boundary

The safe claim is “imported instruction text is inert by construction,” not “prompt injection is solved.” The runtime has no model call and never concatenates input into a prompt, query, template, path, or process invocation. Dynamic UI values use DOM `textContent`. The server applies CSP, `nosniff`, frame denial, no-referrer, no-store, a 1 MB request limit, exact route matching, loopback binding by default, and loopback Host/Origin validation unless the explicit non-loopback override is used.

## Orientation guide

The animated figure is a presentation-only projection. Its label is selected from a closed voltage-to-copy map; its cue is the exact `primary_next_step.instruction`, never a second recommendation. Color follows the semantic voltage token. CSS motion is disabled under `prefers-reduced-motion`, and the guide has no write path, model call, persistence, or authority.

## Persistence boundary

This vertical slice intentionally uses JSON checkpoints and CLI artifacts, not SQLite or a production event store. It proves deterministic reduction, scoped atomic artifact replacement, and fallback-checkpoint recovery. It does not prove multi-process concurrency, power-loss behavior, database recovery, remote identity, production IAM, or canonical X30 substrate equivalence.
