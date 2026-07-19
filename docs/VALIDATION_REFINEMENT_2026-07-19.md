# Assistant refinement clean-checkout receipt — 2026-07-19

> Historical receipt for commit `97d104fe043b0963b19ce15aea9bd3fe2480874a`. Its test counts, timings, media identities, and conclusions remain unchanged as commit-scoped evidence. It does not validate the current `LOCAL_CANDIDATE`, which still requires a new clean-checkout receipt.

## Scope and identity

- status: `PASS`
- scope: integrated ZNAK assistant, responsive/accessibility refinement, refreshed media, and publication-path hygiene
- validated candidate commit: `97d104fe043b0963b19ce15aea9bd3fe2480874a`
- validated candidate tree: `0e91e5b2fffb19e85940f001521f23b9de59c97f`
- execution time: `2026-07-19T13:38:33+02:00`
- toolchain: Python `3.11.9`; Git `2.55.0.windows.2`
- clone method: `git clone --local --no-hardlinks` into a new non-existing directory
- tracked files: `43`
- public remote: none; the clone's `origin` was only the local source repository

This in-repository receipt validates the candidate commit immediately before this receipt was finalized. Reproducibility of the later receipt-bearing HEAD is recorded separately at output level, avoiding a circular claim about the commit that contains its own receipt.

## Executed gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Fresh checkout | `PASS` | New clone at exact commit/tree above; no hard links |
| Automated suite | `PASS` | `Ran 105 tests in 6.995s`; `OK` |
| Bytecode compilation | `PASS` | `python -m compileall -q znak_orient tests`, exit 0 |
| Deterministic CLI | `PASS` | checkpoint `cp:3676e65da2ad0981`; generated result SHA-256 `9a0f24f4ea20653790dae893ae50749e9c2a55b1ef61d2e9fc91587eee7f10b4` |
| JavaScript syntax | `PASS` | `app.js` and `record_demo.cjs` passed the bundled Node syntax check |
| Loopback HTTP | `PASS` | HTTP 200; CSP and `nosniff`; GET demo and POST orient matched checkpoint/integrity, voltage `BLOCKED`, and exactly one step |
| Browser workflow from clone | `PASS` | 23/23 checks true; checks exactly equal the retained receipt; zero console/page errors |
| Desktop render replay | `PASS` | Clean-clone 1440×900 PNG was byte-identical to the retained desktop image |
| Mobile render replay | `PASS_VISUAL_EQUIVALENCE` | Same 390×844 layout; only 11 RGB channel samples differed by one level, inside a 5×3 antialiasing boundary; no semantic/layout difference |
| Minimum-width and motion access | `PASS` | No 320px overflow; complete guide/action at 390×844; reduced motion disabled figure, arm, and markers |
| Video replay | `PASS_SCOPED` | New local VP8 run: 35.68 s, 1440×900, 25 fps, no audio stream listed; byte identity is not claimed for re-encoding |
| Local-path and high-confidence secret scan | `PASS` | Zero matching tracked files |
| Worktree after execution | `PASS` | Empty status; generated validation files remained under ignored `work/` |

## Retained media

- `artifacts/browser-qa.json`: 23/23 `PASS`, SHA-256 `80e89b005a8eb3cf2957e3d070a5f7093c42298dede6b9da79044ffb97f5918f`
- `artifacts/znak-orient-demo.webm`: 35.44 s, 1440×900 VP8 WebM, SHA-256 `9fd30795607fa29c87e4a47f46a53939e43c14b255cf2770e287271fd0130709`
- `artifacts/ui-desktop-1440x900.png`: SHA-256 `77fe7b818860aebf7b0fb9e9961937d92586709a2333eaa0c505d206a585aea3`
- `artifacts/ui-mobile-390x844.png`: SHA-256 `262ae610e7844de7d050c9bb40477cbf5ec142a499cc8819122d9a6d92be8395`
- `artifacts/design-concept-1440x900.png`: SHA-256 `2a44073a724801674a5365e96f5c59155ea6682f9607a044740b908361e0e71d`

## Claim boundary

`PASS` means the committed local synthetic refinement was reproducible under the listed gates. It does not prove external source truth, authenticated identities, production readiness, canonical X30 conformance, superiority over raw notes, GitHub publication, public deployment, Devpost submission, video publication, `/feedback` submission, paid API execution, or real-model execution.
