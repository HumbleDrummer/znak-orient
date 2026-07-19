# Assistant edge-state clean-checkout receipt — 2026-07-19

> Historical commit-scoped receipt. Its figures and conclusions below remain unchanged as evidence for commit `6bd740b9c36743d3b84266da5ddf77027ca48dbc`; current validation is superseded by `VALIDATION_FINAL_2026-07-19.md` for candidate D.

## Scope and identity

- status: `PASS_WITH_RETRY_DISCLOSURE`
- scope: animated orientation assistant, responsive/accessibility edge states, closed `STATE_CHANGE` impact semantics, legacy `0.3C` migration, retained media, and local handoff readiness
- validated candidate commit: `6bd740b9c36743d3b84266da5ddf77027ca48dbc`
- validated candidate tree: `7f92c119080f25d8142c3ac48d37b59e470fc677`
- validation started: `2026-07-19T14:46:56.2012786+02:00`
- toolchain: Python `3.11.9`; Git `2.55.0.windows.2`
- clone method: `git clone --local --no-hardlinks` into a new ignored directory
- tracked files: `44`
- public remote: none; the clone's `origin` was only the local source repository

This receipt validates the exact candidate commit and tree above. It cannot validate the later commit that adds this receipt and its links; that receipt-bearing HEAD is checked separately in the output-level handoff report.

## Executed gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Fresh checkout identity | `PASS` | Exact commit/tree above; 44 tracked files; no hard links; local-only origin |
| Automated suite | `PASS` | `Ran 121 tests in 7.638s`; `OK` |
| HTTP regression isolation | `PASS` | Previously interrupted test passed alone in 0.529 s, inside the full suite, and in 10/10 additional repetitions |
| Bytecode compilation | `PASS` | `python -m compileall -q znak_orient tests`, exit 0 |
| Deterministic CLI | `PASS` | checkpoint `cp:a58ca1e52c138e54`; generated result SHA-256 `61f8983bc39421f17f1f599df58c4f3629659c8bc60c25138156d29b9aba0027` |
| JavaScript syntax | `PASS` | `app.js` and `record_demo.cjs` passed the bundled Node syntax check |
| Loopback HTTP | `PASS` | HTTP 200; CSP present; `nosniff`; checkpoint `cp:a58ca1e52c138e54`; voltage `BLOCKED`; exactly one step |
| Browser workflow from clone | `PASS` | 39/39 named checks true; one expected deliberate HTTP 400 event; zero unexpected console errors; zero page errors |
| Browser receipt replay | `PASS_BYTE_EXACT` | Clone and retained `browser-qa.json` SHA-256 both `b296d590c4c03ea732c7004adbd97a792420b939b6a3fe2149ff418e426472ed` |
| Desktop render replay | `PASS_BYTE_EXACT` | Clone and retained 1440×900 PNG SHA-256 both `46ea419f55fba07e0b6cb753504934b01631db81896809217fd0eb9903f04de0` |
| Mobile render replay | `PASS_VISUAL_EQUIVALENCE` | Clone SHA-256 `b71becf4b30f278e9cf19ea11c0ce6000fb2ac95102737853e679f9c603d8f4c`; retained SHA-256 `a15fc5dcffaa25dc1e8f0fb720707c968c382d8e902cc2747b499739c0bff269`; 8 pixels / 11 RGB channel samples differ by at most 1 level inside bounding box `(369,115)–(373,117)`; no semantic or layout difference observed |
| Video replay | `PASS_SCOPED` | Clone VP8 1440×900 25 fps capture: 47.24 s, 4,322,386 bytes, SHA-256 `4838592545ee06a07f574a0edf835ce9e21245b68acf335443a3ca15cff16d24`; byte identity with the retained 47.04 s encoding is not claimed |
| Tracked path/secret scan | `PASS` | Zero absolute user-home paths and zero high-confidence secret patterns in tracked content; zero symlinks |
| Git object check | `PASS_WITH_NOTE` | `git fsck --full` exited 0 and reported one unreachable dangling blob; an unreachable blob is not reachable-history corruption |
| Worktree boundary | `PASS` | Clone was clean after unit/CLI gates; the recorder then expectedly changed only the mobile PNG and WebM because those encodings are not byte-stable |

## Invalid preliminary attempt — excluded from evidence

Before the valid run above, one orchestration command named the clone but did not actually change its process working directory. Its tests therefore ran in the source checkout, not in the clone, and one HTTP test ended with Windows `WinError 10053`. That whole attempt is excluded from clean-checkout evidence. The correctly rooted clone then passed the test alone, the complete 121-test suite, and 10/10 repeated executions. This disclosure is retained so a transient or orchestration error is not silently rewritten as a first-attempt pass.

## Retained candidate artifacts

- `artifacts/browser-qa.json`: 39/39 `PASS`, SHA-256 `b296d590c4c03ea732c7004adbd97a792420b939b6a3fe2149ff418e426472ed`
- `artifacts/znak-orient-demo.webm`: 47.04 s, 4,311,676 bytes, VP8 1440×900 25 fps, SHA-256 `4263a18281eb8a53347b0cfa9422f48c862c1ced2149812ec27e0b11a3a57694`
- `artifacts/ui-desktop-1440x900.png`: SHA-256 `46ea419f55fba07e0b6cb753504934b01631db81896809217fd0eb9903f04de0`
- `artifacts/ui-mobile-390x844.png`: SHA-256 `a15fc5dcffaa25dc1e8f0fb720707c968c382d8e902cc2747b499739c0bff269`
- `artifacts/design-concept-1440x900.png`: SHA-256 `2a44073a724801674a5365e96f5c59155ea6682f9607a044740b908361e0e71d`

## Claim boundary

`PASS_WITH_RETRY_DISCLOSURE` proves the named local synthetic commit under the gates above. It does not prove external source truth, authenticated identities, production readiness, canonical X30 conformance, superiority over raw notes, GitHub publication, public deployment, Devpost submission, video publication, `/feedback` submission, paid API execution, or real-model execution.
