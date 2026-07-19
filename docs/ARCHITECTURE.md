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
| `STATE_CHANGE` | Normalized input operation plus epistemic/authority/source/time; a retained meaningful change also carries the reducer-derived closed `impact` and bound before/after snapshots | Input after policy checks; `impact` is output-only evidence of the applied transition |
| `PIN` | Authorized `USER_PIN` source feeding durable goal/constraint lamps | Source, not an executable instruction |
| `LAMP` | Active typed item keyed by `(content_type, subject)` | Canonical checkpoint state |
| `CHECKPOINT` | Compact sealed position with lamps, recent meaningful changes, conflicts, unknowns, voltage, one step, source pointers, and immutable receipt pointers | Source of truth for recovery |
| `RECOVERY_CARD` | One-way projection from a verified checkpoint | Explicitly non-authoritative and non-writeable |
| `SOURCE_POINTER` | ID, locator, kind, source time, authority assertion, and computed content hash | Provenance pointer |
| `VALIDATION_RECEIPT_POINTER` | Receipt ID, canonical receipt hash, subject, check time, and source IDs | Compact append-only identity ledger across checkpoints |
| `VALIDATION_RECEIPT` | Subject-scoped PASS/FAIL/UNKNOWN evidence plus validator ID and checks | Can block; promotion requires local trusted-validator policy |

## Four independent axes

Content, operation, epistemic status, and authority are validated separately. `material` is a required JSON boolean, never a truthy/falsy coercion. A user decision can authorize a goal or constraint but cannot make a fact true. A newer claim does not win by timestamp. A different value opens a conflict unless it explicitly and validly supersedes the active lamp. `DISPUTED` material claims are removed from action-driving state and retained under the conflict object. There must be exactly one active material `GOAL`, or exactly one open material `GOAL` conflict carrying the contested goal context.

`impact` is not a fifth input axis and an imported `STATE_CHANGE` cannot declare it. The reducer derives exactly one of eight closed effects only after policy and state checks, binds it to the operation, reason, status, meaning, source/time metadata, and complete before/after snapshots, and then validates that the latest retained change for every `(content_type, subject)` key agrees with the final lamp or conflict projection, including `FACT`.

| Input operation | Allowed derived impacts |
| --- | --- |
| `CREATE` | `STATE_ACTIVATED`, `STATE_METADATA_UPDATED`, `EVIDENCE_EXTENDED`, `CONFLICT_OPENED`, `CONFLICT_EXTENDED` |
| `UPDATE` | `STATE_METADATA_UPDATED`, `EVIDENCE_EXTENDED`, `CONFLICT_OPENED`, `CONFLICT_EXTENDED` |
| `ACTIVATE` | `STATE_ACTIVATED`, `STATE_METADATA_UPDATED`, `EVIDENCE_EXTENDED`, `CONFLICT_OPENED`, `CONFLICT_EXTENDED` |
| `DEACTIVATE` | `STATE_DEACTIVATED` |
| `SUPERSEDE` | `STATE_REPLACED` |
| `INVALIDATE` | `STATE_DEACTIVATED` |
| `RESOLVE` | `CONFLICT_RESOLVED` |
| `MOVE` | none; the operation fails closed as not implemented |

The eight impacts mean, respectively: activate a lamp, replace a lamp while retaining its identity, remove a lamp, update non-source metadata, strictly extend evidence sources, open a conflict, append one claim while preserving the complete previous conflict, or resolve a conflict into an active lamp. A structurally plausible impact with the wrong operation or a before/after snapshot that disagrees with canonical state invalidates the checkpoint. The sole projection exception is an explicit FACT receipt suspension: the FACT lamp may be absent only when its original receipt is still a supplied, trusted, value-bound PASS retained in the pointer ledger; a later incompatible trusted receipt exists in the causal interval; and the exact lamp identity, value, receipt ID, epistemic/authority, sources, and time are preserved as the suspended claim in the corresponding `CONTRADICTORY_VALIDATION_RECEIPTS` conflict. This exception records why the FACT stopped driving state; it does not validate a missing or altered FACT silently.

## Checkpoint and recovery

A checkpoint is valid only when its sealed canonical content and semantic invariants validate. The checks include a closed top-level and nested shape, positive bounded history cursors, exactly one goal context, source/receipt/claim times that do not postdate the object they support, source pointers with hashes bound to the supplied records, required receipt ID/hash pointers, authorized source kinds for authority-driving lamps and resolutions, value-bound trusted PASS receipts for FACT lamps, and a recomputed goal/constraint-aligned next step. A resolved conflict must select one preserved claim, retain chronological resolution history, and correspond to the active lamp. Receipt references are permitted only on FACT lamps, and a disputed proof receipt cannot support another FACT unless its own conflict is resolved to that exact claim.

Recovery validates every primary/fallback candidate, then selects the newest valid checkpoint by `created_at`, semantic cursor, and a deterministic tie-break. Receipt IDs found in any retained candidate remain reserved even when a newer checkpoint is otherwise invalid. If fallback would cross an interval whose receipt lineage is missing, replay stops instead of silently accepting a reused identity. A single trusted tail receipt is compared with claims already compacted into the checkpoint, so older raw receipts need not be reloaded. If no checkpoint is valid, processing stops with `OrientationError`; it never fabricates state. `checkpoint_id` is a cooperative stale-state token for this fixture, while `integrity.value` is the canonical-content digest; the ID alone is not a cryptographic concurrency token.

Legacy schema-`0.3C` checkpoints whose retained meaningful changes predate the `impact` field use a narrow migration path. The original checkpoint seal is verified first, before any inference. Only a non-empty history in which every retained change has the exact legacy shape is eligible. Each missing impact must be uniquely derivable under the current operation/impact and snapshot rules; mixed shapes, corruption, zero or multiple candidates, and current-semantic failures are rejected and recovery proceeds to a valid fallback or fails closed. Migration operates on a copy, preserves the original bytes, adds only the derived impacts, reseals the in-memory candidate, and validates it normally. A selected migrated base reports a status ending in `_LEGACY_MIGRATED` (for example `PRIMARY_VALID_LEGACY_MIGRATED`); the emitted checkpoint is a fresh current-shape object with a new `checkpoint_id` and processing time.

A new checkpoint is produced only when a meaningful state change, new receipt pointer, material receipt effect, conflict, unknown, voltage, position, or primary-step change exists. Noise-only traces and semantic duplicates remain visible in intake but do not create a checkpoint. Within retained history, successive changes for the same `(content_type, subject)` key must form a continuous transition chain: the earlier `after` snapshot must equal the later `before` snapshot exactly. The only permitted break is the same explicit FACT receipt suspension: after a retained FACT state has been suspended into its matching receipt conflict, a later change for that FACT may correctly begin with `before: null`. This does not permit arbitrary gaps, reordered changes, or a reset without the bound suspension claim.

The tested history-compaction guarantee is semantic: processing a meaningful prefix and replaying the tail from that checkpoint yields the same position-driving projection as processing prefix and tail together, once the tail's `expected_checkpoint_id` is rebased to the selected compacted checkpoint. It does not require byte-identical checkpoints, identical checkpoint IDs, or identical retained-history prefixes; stale or unre-based CAS tokens still fail closed.

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

This vertical slice intentionally uses JSON checkpoints and CLI artifacts, not SQLite or a production event store. It proves deterministic reduction, scoped atomic artifact replacement, fallback-checkpoint recovery, integrity-first migration for the supported legacy `0.3C` shape, and semantic projection equivalence for the tested package whose older history is already covered by its checkpoint after explicit CAS rebase. It does not prove byte-for-byte replay equivalence, that compression is globally minimal or better than raw notes, nor multi-process concurrency, power-loss behavior, database recovery, remote identity, production IAM, or canonical X30 substrate equivalence.
