# Local video and browser QA receipt

## Recorded artifact

| Field | Value |
| --- | --- |
| File | `artifacts/znak-orient-demo.webm` |
| Status | `EXECUTED_LOCAL / NOT_PUBLISHED` |
| Duration | 35.12 seconds |
| Frame | 1440×900, 25 fps |
| Codec | VP8 in WebM |
| Bytes | 2,836,670 |
| SHA-256 | `eb4b080035a68fec13167e05201e7343030b99c1779f5186b5c85028a7bb433e` |

The capture was produced from the real loopback application by `tools/record_demo.cjs`. Browser routing rejected every non-loopback host. The recording walks through rerun, Rejected/All filtering, conflict and unknowns, Recovery Card copy, source evidence, receipts, and return to Current Position. It contains no narration and is distinct from the proposed 2:35 narrated script in `DEMO_SCRIPT.md`.

## Machine-readable browser receipt

`artifacts/browser-qa.json` reports `LOCAL_BROWSER_WORKFLOW_ONLY / PASS` and has SHA-256 `64952fbca8f4395af4448a5cd37509265f08662f1e6bee566318d7c28b2dd733`.

All retained checks passed:

- six required product sections;
- source-backed failed position;
- exactly one visible next step;
- guide state bound to `BLOCKED`;
- guide cue exactly equal to the selected next-step instruction;
- guide animation active in normal motion mode;
- five rejected items and restoration to all eight;
- scoped transform receipt shown as PASS;
- no desktop or mobile horizontal overflow;
- Recovery Card clipboard payload remained non-authoritative;
- current position precedes intake on mobile;
- guide animation disabled under reduced-motion emulation;
- zero collected console warnings/errors or page errors.

## Claim boundary

This proves only the retained local headless-Chromium workflow over the synthetic package. It does not prove public availability, narration quality, clipboard behavior in other browsers, external source truth, production readiness, Devpost submission, or video publication.
