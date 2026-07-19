# Local video and browser QA receipt

## Recorded artifact

| Field | Value |
| --- | --- |
| File | `artifacts/znak-orient-demo.webm` |
| Status | `EXECUTED_LOCAL / NOT_PUBLISHED` |
| Duration | 35.44 seconds |
| Frame | 1440×900, 25 fps |
| Codec | VP8 in WebM |
| Bytes | 3,448,458 |
| SHA-256 | `9fd30795607fa29c87e4a47f46a53939e43c14b255cf2770e287271fd0130709` |

The capture was produced from the real loopback application by `tools/record_demo.cjs`. Browser routing rejected every non-loopback host. The recording walks through rerun, Rejected/All filtering, conflict and unknowns, Recovery Card copy, source evidence, receipts, and return to Current Position. It contains no narration and is distinct from the proposed 2:35 narrated script in `DEMO_SCRIPT.md`.

## Machine-readable browser receipt

`artifacts/browser-qa.json` reports `LOCAL_BROWSER_WORKFLOW_ONLY / PASS` and has SHA-256 `80e89b005a8eb3cf2957e3d070a5f7093c42298dede6b9da79044ffb97f5918f`.

All retained checks passed:

- six required product sections;
- source-backed failed position;
- exactly one visible next step;
- guide state bound to `BLOCKED` and exactly one matching state marker;
- exactly one full visible action, equal to the selected next-step instruction;
- success-condition machine value equal to `/api/demo`;
- finite, state-specific guide motion active in normal motion mode;
- five-of-eight rejected count, pressed-state semantics, and restoration to all eight;
- visible keyboard focus on the native JSON chooser;
- scoped transform receipt shown as PASS;
- no desktop or mobile horizontal overflow;
- Recovery Card clipboard payload remained non-authoritative;
- current position precedes intake visually on mobile and semantically in DOM order;
- the complete guide and next action remain inside the 390×844 opening viewport;
- figure, pointing arm, and marker animation are disabled under reduced-motion emulation;
- no horizontal overflow at the 320px minimum width;
- zero collected console warnings/errors or page errors.

The machine-readable receipt contains 23 checks and all 23 are true.

## Claim boundary

This proves only the retained local headless-Chromium workflow over the synthetic package. It does not prove public availability, narration quality, clipboard behavior in other browsers, external source truth, production readiness, Devpost submission, or video publication.
