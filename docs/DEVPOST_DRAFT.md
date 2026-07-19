# Devpost form draft — not submitted

## Project name

ZNAK ORIENT

## Tagline

Recover project direction from partial, stale, contradictory, and untrusted evidence.

## Short description

ZNAK ORIENT is a local deterministic developer tool that turns scattered project evidence into a source-backed current position, explicit conflicts and unknowns, one justified next action, a machine-verifiable success condition, and a compact Recovery Card.

## Inspiration

Long project histories often preserve every sentence while losing the decisions, constraints, unknowns, and next step that restore direction. We wanted minimum sufficient memory: enough to resume safely without loading the whole project “city.”

## What it does

The application imports a closed JSON evidence package, rejects duplicate keys and ambiguous materiality, normalizes structured observations, rejects stale or unauthorized changes, enforces causal source/receipt times, requires subject-scoped value-bound validation for facts, preserves incompatible claims as disputes, retains immutable receipt ID/hash pointers across fallback, and produces one canonical orientation result. A responsive local UI shows Noise Intake, Current Position, Conflict and Unknowns, Recovery Card, Source Evidence, and Validation Receipt. A small animated ZNAK assistant reacts to voltage and points to the single canonical next step without inventing or duplicating another one.

## How we built it

Python 3.11 standard library provides strict contracts, canonical JSON, SHA-256 sealing, deterministic reduction, atomic CLI artifact replacement, `unittest`, and a loopback `http.server`. The interface is code-native HTML, CSS, and JavaScript. Imported values are written with `textContent`; the server uses CSP and size/route/binding limits. No model, credential, telemetry, external database, Docker, Node runtime, or hosted API is required.

## Challenges

The hardest boundary was preventing different kinds of confidence from collapsing into one status: source time is not truth, fact verification is not decision authority, and a newer claim is not automatically a correction. We also preserved receipt identity through compact checkpoints and fallback without reloading all earlier raw receipts, while keeping the Recovery Card useful and unable to become canonical input.

## Accomplishments

- deterministic replay and exact checkpoint integrity;
- explicit duplicate, stale, unauthorized, unsupported, conflict, and derived-input dispositions;
- fallback recovery from a corrupted primary checkpoint;
- immutable receipt identity and lineage-safe fallback that stops on an unverifiable rollback interval;
- tail-receipt conflict merging without loading the earlier raw receipt set;
- tested recovery equivalence when history already covered by the checkpoint is removed;
- exactly one corrective next step with a closed evaluator;
- a code-native animated guide with verified reduced-motion support and no model call;
- judge-safe prompt-injection fixture that remains inert by construction;
- local interface, automated suite, clean-checkout workflow, and auditable claims.

## What we learned

Good memory is not more recall. It is traceable selection: retain meaningful deltas, preserve disputes, label unknowns, and refuse to turn output summaries back into evidence.

## What is next

Add an authenticated authority registry, cryptographically bound validator receipts, an append-only transactional store, larger regression corpora, and—only after separate evidence—evaluate whether compressed checkpoints restore direction better than raw notes.

## Built with

Python, HTML, CSS, JavaScript, Git, Codex for Windows, local Chromium.

## Repository URL

`https://github.com/HumbleDrummer/znak-orient`

## Demo URL

`LOCAL_ONLY: http://127.0.0.1:8765 — no public deployment authorized`

## Video URL

`LOCAL_ARTIFACT: artifacts/znak-orient-demo.webm / NOT_PUBLISHED`

## Claim note for judges

The synthetic fixture and local tests prove the scoped deterministic behavior in this repository. They do not prove external truth, production security, canonical X30 conformance, or superiority over raw notes.

The exact test, receipt, artifact, and non-execution mapping is maintained in the [claim-to-evidence matrix](CLAIM_EVIDENCE_MATRIX.md).
