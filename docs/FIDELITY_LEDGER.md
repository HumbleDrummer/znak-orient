# Interface fidelity ledger

## References

- code-native concept: `docs/design-concept.svg`
- rendered concept: `artifacts/design-concept-1440x900.png`
- desktop implementation: `artifacts/ui-desktop-1440x900.png`
- mobile implementation: `artifacts/ui-mobile-390x844.png`

Image generation was not used because the authorized PIN blocks paid or real API/model calls without separate confirmation. The deterministic vector concept is the recorded design reference for this build.

## Verification methods

The Codex in-app browser loaded the real loopback application, returned a complete accessibility snapshot, executed **Re-run orientation**, changed the intake filter to **Rejected** (8 → 5 visible items), activated **Copy Recovery Card**, and reported no warning/error console entries. Its viewport override did not change the reported CSS viewport, so local Chromium headless with all non-loopback resolution blocked was used for exact 1440×900 and 390×844 responsive screenshots, a 35.12-second workflow recording, and the retained `browser-qa.json` receipt.

## Comparison points

| Point | Concept | Render | Result |
| --- | --- | --- | --- |
| Information architecture | Intake, position, recovery, blockers, evidence | Same order and ownership | Match |
| Palette | Warm paper, white evidence surfaces, dark recovery rail, semantic signal colors | Exact CSS tokens from design spec | Match |
| Typography | Strong editorial position, compact mono identifiers, deliberate control text | Segoe UI/Aptos + Cascadia/Consolas hierarchy | Match |
| Container model | Three rails, ruled evidence, no decorative card grid | Same; conflict spans center/right below primary row | Match |
| Dynamic copy | Failed position, BLOCKED voltage, one authorized resolution | Exact deterministic demo result | Match |
| Orientation guide | Small code-native figure, red blocker signal, selected action | Voltage-reactive label and color; cue equals the exact next-step instruction | Match |
| Recovery treatment | Dark rail, explicit derived warning, copy control | Same | Match |
| Responsive behavior | Single-column current-position-first mobile flow | 390×844 screenshot shows no horizontal overflow and 44px controls | Match |
| Interaction | Rerun, filtering, Recovery Card copy | Rerun/filter/copy payload verified in the isolated headless context | Match within local browser scope |
| Motion access | Restrained assistant motion | Animation active normally and absent under `prefers-reduced-motion: reduce` | Match |

## Above-the-fold copy diff

Allowed static copy: `ZNAK ORIENT`, `Current Position`, `Noise Intake`, `Conflict and Unknowns`, `Recovery Card`, `Choose JSON`, and `Re-run orientation`. All remaining visible position, goal, status, source, and next-step text is result data. No decorative eyebrow, fake metric, marketplace, account, 3D map, or unexplained percentage was added.

## Fixes made during QA

- removed the initial success toast that covered content in screenshots;
- added the required JSON import control to the design reference;
- updated the concept hash and Recovery Card copy control;
- aligned the concept grid with the implemented conflict span and real data density;
- added the requested animated orientation figure without introducing another recommendation or model call;
- bound the figure cue to the exact deterministic next step and verified reduced-motion behavior;
- retained scroll-safe tables and current-position-first mobile ordering.

## Intentional limitations

The in-app browser's clipboard API returned an empty read after the page reported a successful copy. A separate isolated headless Chromium run with explicit local clipboard permission did read the payload and verify `source_of_truth = false` plus `write_back_allowed = false`. This proves only that tested local context, not clipboard support in other browsers. The same flags remain independently covered by automated tests.

## Retained image hashes

| Artifact | Dimensions | SHA-256 |
| --- | --- | --- |
| `design-concept-1440x900.png` | 1440×900 | `23d2ea07788e340cfe89955160bd47e8d91b4d873edaaf943593de9f235aea4e` |
| `ui-desktop-1440x900.png` | 1440×900 | `13f785f882ea09a3fba461250a3af4a7e5101753d63b2236f6e51564fec75ff2` |
| `ui-mobile-390x844.png` | 390×844 | `5159508de1199e9febf0b661128c1924eae8eda2a258fcb2de65cfba400fd162` |
