# Clean-checkout validation receipt — 2026-07-19

## Scope and identity

- status: `PASS`
- scope: committed local competition candidate, synthetic fixture, clean local clone
- validated commit: `0f841242e672b444ef5b5d668f7e496459aa1d79`
- validated tree: `660cab9fe049b6b8ebf0407bc3ecc5b586a0ce0b`
- execution time: `2026-07-19T11:21:18+02:00`
- toolchain: Python `3.11.9`; Git `2.55.0.windows.2`
- clone method: `git clone --local --no-hardlinks`
- tracked files: `40`
- public remote: none; the clone's `origin` was only the local source path

This in-repository receipt necessarily validates the candidate commit immediately before the receipt itself was added. Reproducibility of the later receipt-bearing final HEAD is recorded in the separate output-level `ZNAK_ORIENT_FINAL_VALIDATION_2026-07-19.md` so the evidence does not make a circular claim about its own commit.

## Executed gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Fresh checkout | `PASS` | New non-existing clone directory; exact commit above |
| Automated suite | `PASS` | `Ran 59 tests in 4.721s`; `OK` |
| Bytecode compilation | `PASS` | `python -m compileall -q znak_orient tests`, exit 0 |
| Deterministic CLI | `PASS` | `ORIENTATION_PASS checkpoint=cp:32f9a80d529c31f3` |
| Checkpoint integrity | `PASS` | `f656f572f6e5e2cccbe8c5bc33461db5666ad8bd0baf78c3e1bf82c0239ecd20` |
| Loopback index | `PASS` | HTTP 200, CSP present, `orientation-guide` present |
| Loopback demo API | `PASS` | package `judge-safe-orientation-demo-001`; voltage `BLOCKED`; scoped run `PASS` |
| Browser workflow receipt | `PASS` | 15/15 checks true; no console/page errors |
| High-confidence secret scan | `PASS` | no matching files for AWS/GitHub/OpenAI/private-key patterns |
| Worktree after execution | `PASS` | `git status --short` empty; generated JSON and bytecode remained ignored |

## Retained browser and media evidence

- `artifacts/browser-qa.json`: SHA-256 `64952fbca8f4395af4448a5cd37509265f08662f1e6bee566318d7c28b2dd733`
- `artifacts/znak-orient-demo.webm`: 35.12 s, 1440×900 VP8 WebM, SHA-256 `eb4b080035a68fec13167e05201e7343030b99c1779f5186b5c85028a7bb433e`
- `artifacts/ui-desktop-1440x900.png`: SHA-256 `13f785f882ea09a3fba461250a3af4a7e5101753d63b2236f6e51564fec75ff2`
- `artifacts/ui-mobile-390x844.png`: SHA-256 `5159508de1199e9febf0b661128c1924eae8eda2a258fcb2de65cfba400fd162`
- `artifacts/design-concept-1440x900.png`: SHA-256 `23d2ea07788e340cfe89955160bd47e8d91b4d873edaaf943593de9f235aea4e`

## Claim boundary

`PASS` means the committed local synthetic vertical slice was reproducible under the executed gates. It does not mean the imported project is complete, the synthetic sources are externally true, authorization strings are authenticated identities, X30 is canonically ratified, compressed memory outperforms raw notes, the product is production-ready, or GitHub/Devpost/public deployment/video publication has occurred.
