# Repository discovery preflight — 2026-07-19

## Decision

`REPOSITORY_STATUS: NOT_FOUND`

No dedicated ZNAK ORIENT 0.3C product repository or implementation checkout with valid Git history was found. The authorized response is to create the smallest isolated repository at:

`<authorized-workspace>\outputs\znak-orient`

The machine-specific workspace prefix is intentionally omitted from the publication-facing record.

The original product baseline branch and commit are therefore `NOT_APPLICABLE`.

## Candidates deliberately excluded

| Candidate | Evidence | Decision |
| --- | --- | --- |
| `...\outputs\znak-orientation-lab` | Valid Git repo, branch `master`, observed HEAD `4eb38e30bae9953ff70aba545eb6f891b88d1098`; `pyproject.toml` describes a local experimental lab; working tree was already dirty. | Experiment harness, not the product repo. Do not mix. |
| `...\po\work\znak_orient_mvp` | Python contracts and tests exist, but enclosing `...\po\.git` is empty and Git discovery fails. | Historical implementation directory, not a checkout. Treat only as background evidence. |
| `...\po\work\znak-windows-city` | Contains X30-related code but belongs to ZNAK Windows City; enclosing Git marker is empty. | Separate product and ownership boundary. Do not mix. |

## Detected local toolchain

- Git: `2.55.0.windows.2`
- Python: `3.11.9`
- Node.js/npm: not available on `PATH`
- Python `pytest`: not available in the system interpreter
- Git global author identity: not configured at discovery time

The new repo therefore uses Python's standard-library `unittest` runner and a standard-library loopback web server. No external package install is required for runtime or tests.

## Missing vertical-slice components at discovery

- canonical evidence-package contract
- normalization and semantic deduplication
- authority/epistemic policy gate
- deterministic state-change reducer
- conflict and critical-unknown preservation
- checkpoint integrity, fallback, and replay
- derived non-authoritative Recovery Card
- exactly-one next-step selector with machine-verifiable success condition
- judge-safe synthetic scenario
- local web interface and browser verification
- project-scoped validation receipt
- clean-checkout and submission documentation

## Evidence boundary

Historical reports such as `99 passed` or `173 passed` were not reproduced in this new repository and are not product PASS evidence. No source code was copied from the excluded candidates during this preflight.
