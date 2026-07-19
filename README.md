# ZNAK ORIENT

[![CI](https://github.com/HumbleDrummer/znak-orient/actions/workflows/ci.yml/badge.svg)](https://github.com/HumbleDrummer/znak-orient/actions/workflows/ci.yml)

ZNAK ORIENT is a local, deterministic developer tool for recovering project direction from partial, stale, duplicated, contradictory, and untrusted evidence. It returns a source-backed current position, explicit conflicts and unknowns, exactly one corrective next step, a machine-verifiable success condition, a canonical checkpoint, and a compact non-authoritative Recovery Card.

Current scope: `IMPLEMENTED_AND_LOCALLY_EXECUTED` competition MVP. This is not a claim of production readiness, canonical X30 ratification, external source authenticity, GitHub publication, public deployment, Devpost submission, or published video.

![ZNAK ORIENT desktop interface](artifacts/ui-desktop-1440x900.png)

## OpenAI Build Week

- category: **Developer Tools**
- public-repository target: [github.com/HumbleDrummer/znak-orient](https://github.com/HumbleDrummer/znak-orient)
- primary supported and executed platform: Windows 11 with Python 3.11
- runtime: Python standard library plus code-native HTML, CSS, and JavaScript
- build step: none; judges can clone, run the test command, and start the local UI directly

Codex for Windows with `gpt-5.6-sol` accelerated repository discovery, contract and reducer implementation, test generation, browser verification, accessibility refinement, Windows HTTP failure diagnosis, and evidence-ledger preparation. The human product decisions were to keep the engine deterministic, separate fact confidence from decision authority, preserve disputes instead of overwriting them, make the Recovery Card non-authoritative, and keep publishing and external calls behind explicit gates. The complete collaboration record and principal `/feedback` Session ID are in [docs/CODEX_COLLABORATION.md](docs/CODEX_COLLABORATION.md).

The [Build Week submission checklist](docs/BUILD_WEEK_SUBMISSION_CHECKLIST.md) separates repository-ready evidence from the still-required public YouTube video and Devpost submission.

## Why it exists

Project notes often preserve volume but lose direction. A newer claim can be unsupported, an authorized decision can conflict with another authorized decision, a failed receipt can leave a critical cause unknown, and imported text can contain instructions that must remain inert. ZNAK ORIENT builds a compact orientation checkpoint without silently overwriting history. The tested fixture verifies recovery equivalence after pre-checkpoint history is removed; it does not claim global minimality or superiority over raw notes.

## What the demo proves

The bundled synthetic package contains an old valid checkpoint, an unsupported completion claim, a failed validation receipt, a material unresolved conflict, an embedded prompt-injection attempt, one authorized state change, a duplicate, a stale update, an unauthorized goal override, and a forged Recovery Card write-back.

The deterministic result:

- rejects the completion claim because its cited receipt is `FAIL`;
- treats the embedded instruction as untrusted data;
- preserves both entrypoint claims as `DISPUTED`;
- exposes the critical failure-cause unknown;
- applies the authorized publication gate;
- recovers the current position as “not yet judge-ready”;
- returns one safe conflict-resolution step with sources and a closed success-condition type;
- shows a code-native animated ZNAK assistant whose finite state-specific cue points to the one canonical selected step without duplicating it;
- derives a Recovery Card that cannot write back into canonical state.

`run_receipt.status = PASS` verifies only the orientation transform and its stated invariants. It explicitly does not claim project completion or repair the imported failed validation.

## Requirements

- Windows, macOS, or Linux
- Python 3.11 or newer
- Git for history or clean-clone verification
- a local browser for the interface

Runtime and tests use only the Python standard library. No package install, credential, network service, model, Docker, WSL, Node.js, or Ollama is required.

## Run from a clean checkout

```powershell
git clone https://github.com/HumbleDrummer/znak-orient.git
Set-Location znak-orient
python -m unittest discover -s tests -v
python -m znak_orient verify-demo --input demo/evidence-package.json --output artifacts/demo-result.json
python -m znak_orient serve --host 127.0.0.1 --port 8765
```

On Windows, judges may instead double-click `start-znak-orient.bat`; it starts the same loopback-only server and opens the local interface. Keep its terminal window open and press `Ctrl+C` there to stop the server.

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). Use **Re-run orientation** for the bundled fixture or **Choose JSON** for another local package no larger than 1 MB.

Expected command markers:

```text
Ran 121 tests ... OK
ORIENTATION_PASS checkpoint=<deterministic-id> output=artifacts\demo-result.json
ZNAK_ORIENT_LOCAL http://127.0.0.1:8765
```

Candidate commit `3fe426b90029fcd65eb5572b1724e78ee564a089` passed 121/121 tests in a fresh no-hardlink clone, the deterministic CLI/HTTP gates, 25/25 additional rejected-request stress probes, and the 39/39 browser workflow. The exact evidence, including two pre-fix Windows connection-abort observations and their bounded-body-drain fix, is recorded in `docs/VALIDATION_FINAL_2026-07-19.md`. The retained 47.04-second local capture remains unpublished; a separate 47.00-second fresh-clone replay is commit-scoped evidence, not a byte-identical media reproduction. Earlier validation receipts remain historical evidence for their named commits only.

## Commands

```powershell
# Full automated suite
python -m unittest discover -s tests -v

# Deterministic CLI transform with atomic result replacement
python -m znak_orient verify-demo --input demo/evidence-package.json --output artifacts/demo-result.json

# Loopback web UI
python -m znak_orient serve --host 127.0.0.1 --port 8765

# Version
python -m znak_orient --version
```

Non-loopback binding fails closed unless the operator adds `--allow-non-loopback`. Public deployment remains a separate user-confirmation gate.

## Repository map

```text
demo/evidence-package.json       synthetic judge-safe package
znak_orient/canonical.py         Unicode normalization, canonical JSON, SHA-256 sealing
znak_orient/contracts.py         closed vocabularies and strict package validation
znak_orient/strict_json.py       duplicate-key-rejecting JSON boundary
znak_orient/engine.py            policy gates, reducer, conflict/unknown logic, checkpoint and card
znak_orient/cli.py               atomic CLI artifact write and local commands
znak_orient/server.py            loopback HTTP/API surface with security headers and size limits
znak_orient/web/                 code-native responsive interface
tests/                           deterministic, policy, recovery, CLI, and HTTP tests
.github/workflows/ci.yml         public GitHub Actions test and demo-verification gate
start-znak-orient.bat            Windows one-click local launcher
docs/                            architecture, demo, submission, access, audits, and validation
```

## Core boundaries

- `FACT` confidence and `DECISION` authority are independent axes.
- “Authorized” in this MVP is a deterministic local fixture policy over recognized source kinds; it is not identity authentication or production IAM.
- A trusted-validator ID is a local policy simulation, not a cryptographic attestation.
- SHA-256 binds canonicalized checkpoint/source content inside the package; it does not preserve raw-input byte identity or prove truth in the outside world.
- Deduplication covers structured equality after Unicode and whitespace normalization; it does not claim semantic paraphrase detection.
- JSON parsing rejects exact duplicate keys, unsupported fields, and non-boolean materiality instead of silently coercing them.
- Sources and receipts must exist before the changes/checkpoint members they support; a later record cannot be used as earlier evidence.
- Every checkpoint retains immutable receipt ID/hash pointers. Reusing an ID with changed meaning, deleting the ledger, or rolling back past a newer unverifiable receipt lineage fails closed.
- Success conditions remain false while the same subject or validation lineage is disputed.
- Corrupt-checkpoint recovery means fallback to an older valid checkpoint and causally safe tail replay; it stops when a newer invalid checkpoint makes receipt lineage unknowable. It does not claim recovery from a corrupt disk or database.
- The HTTP server processes uploads in memory and does not persist them. The CLI writes only the explicit output path.
- Imported strings are rendered with `textContent`, never executed as prompts, code, SQL, HTML, paths, or commands.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Evidence package contract](docs/EVIDENCE_PACKAGE.md)
- [Under-three-minute demo script](docs/DEMO_SCRIPT.md)
- [Codex collaboration record](docs/CODEX_COLLABORATION.md)
- [Repository and judging access](docs/REPOSITORY_ACCESS.md)
- [Devpost draft](docs/DEVPOST_DRAFT.md)
- [OpenAI Build Week submission checklist](docs/BUILD_WEEK_SUBMISSION_CHECKLIST.md)
- [Claim-to-evidence matrix](docs/CLAIM_EVIDENCE_MATRIX.md)
- [Privacy, security, licensing, and claims audit](docs/AUDIT_2026-07-19.md)
- [Visual fidelity ledger](docs/FIDELITY_LEDGER.md)
- [Local video and browser QA receipt](docs/VIDEO_RECORDING.md)
- [Final candidate clean-checkout receipt](docs/VALIDATION_FINAL_2026-07-19.md)
- [Historical assistant edge-state clean-checkout receipt](docs/VALIDATION_EDGE_2026-07-19.md)
- [Historical assistant-refinement clean-checkout receipt](docs/VALIDATION_REFINEMENT_2026-07-19.md)
- [Repository discovery preflight](docs/PREFLIGHT_2026-07-19.md)

## License

MIT. See [LICENSE](LICENSE).
