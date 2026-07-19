# Local video and browser QA receipt

## Recorded artifact

| Field | Value |
| --- | --- |
| File | `artifacts/znak-orient-demo.webm` |
| Status | `EXECUTED_LOCAL / LOCAL_CANDIDATE / NOT_PUBLISHED` |
| Duration | 47.04 seconds |
| Frame | 1440x900, 25 fps |
| Codec | VP8 in WebM |
| Bytes | 4,311,676 |
| SHA-256 | `4263a18281eb8a53347b0cfa9422f48c862c1ced2149812ec27e0b11a3a57694` |

The capture was produced from the real loopback application by `tools/record_demo.cjs`. Browser routing rejected every non-loopback host. The recording walks through rerun, Rejected/All filtering, conflict and unknowns, Recovery Card copy, source evidence, receipts, and return to Current Position. It contains no narration and is distinct from the proposed 2:35 narrated script in `DEMO_SCRIPT.md`.

These files are current worktree evidence for the `LOCAL_CANDIDATE`; they are not yet a commit-scoped clean-checkout receipt.

## Machine-readable browser receipt

`artifacts/browser-qa.json` reports `LOCAL_BROWSER_WORKFLOW_ONLY / PASS` and has SHA-256 `b296d590c4c03ea732c7004adbd97a792420b939b6a3fe2149ff418e426472ed`. It contains 39 named checks; all 39 are true. It records zero unexpected console errors and zero page errors. One expected browser resource error from the deliberate invalid-JSON HTTP 400 is isolated in `expected_console_events` and is not represented as an unexpected clean-console failure.

The retained checks cover:

- the six required product sections, source-backed failed position, exactly one visible next step, and matching `/api/demo` success condition;
- the animated assistant's `BLOCKED`, `FLOWING`, `WEAK`, `BROKEN`, and `UNKNOWN` runtime states, one matching marker, finite motion, and all-five-state reduced-motion behavior;
- Rejected/All filtering, pressed-state semantics, and restoration to all eight intake records;
- native JSON chooser keyboard focus, persistent single import error, recovery after a valid import, and local rejection of an oversized import;
- the scoped transform receipt, non-authoritative Recovery Card clipboard payload, and semantic mobile reading order;
- desktop, mobile, 320px minimum, long-token, and breakpoint-sweep overflow checks;
- opening-viewport visibility for the mobile guide and complete next action;
- forced-colors focus, table focus, assistant strokes, and overflow behavior;
- zero unexpected console warnings/errors and zero page errors.

The hashes above identify only these retained local artifacts. They are not inherited by any later recorder or UI change.

## Reproduce locally

Prerequisites:

- Python 3.11 or newer for the application;
- Node.js with the `playwright` package available to `require("playwright")`;
- a Playwright-compatible Chromium installation whose executable path is returned by `chromium.executablePath()`;
- a writable repository checkout and free loopback port 8765;
- two PowerShell terminals opened at the repository root.

In the first terminal, start the application:

```powershell
python -m znak_orient serve --host 127.0.0.1 --port 8765
```

In the second terminal, resolve the installed Chromium path without embedding a machine-specific location, then run the recorder:

```powershell
$env:ZNAK_ORIENT_URL = "http://127.0.0.1:8765"
$env:ZNAK_ORIENT_CHROMIUM = node -e "process.stdout.write(require('playwright').chromium.executablePath())"
node tools/record_demo.cjs
```

The recorder writes the WebM, desktop/mobile screenshots, and `artifacts/browser-qa.json`. It aborts if the configured URL is not loopback. Stop the server with `Ctrl+C` after the recorder finishes.

## Claim boundary

This proves only the retained local headless-Chromium workflow over the synthetic package. It does not prove public availability, narration quality, clipboard behavior in other browsers, external source truth, production readiness, Devpost submission, or video publication. See `CLAIM_EVIDENCE_MATRIX.md` for the claim-by-claim status and evidence boundary.
