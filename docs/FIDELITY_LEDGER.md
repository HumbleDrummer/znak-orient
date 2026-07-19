# Interface fidelity ledger

## References

- code-native concept: `docs/design-concept.svg`
- rendered concept: `artifacts/design-concept-1440x900.png`
- desktop implementation: `artifacts/ui-desktop-1440x900.png`
- mobile implementation: `artifacts/ui-mobile-390x844.png`

Image generation was not used because the authorized PIN blocks paid or real API/model calls without separate confirmation. The deterministic vector concept is the recorded design reference for this build.

## Verification methods

The Codex in-app browser loaded the real loopback application, returned a complete accessibility snapshot, executed **Re-run orientation**, changed the intake filter to **Rejected** (8 → 5 of 8 visible items), activated **Copy Recovery Card**, and reported no warning/error console entries. Its viewport override did not change the reported CSS viewport, so local Chromium headless with all non-loopback resolution blocked was used for exact 1440×900, 390×844, and 320×640 responsive checks, a 47.04-second workflow recording, and the retained 39/39 `browser-qa.json` receipt. That receipt isolates one expected HTTP 400 resource event from the deliberate invalid-JSON probe and records zero unexpected console errors and zero page errors. Fresh-clone replay and the 8-pixel mobile antialiasing boundary are recorded in `VALIDATION_EDGE_2026-07-19.md`.

## Comparison points

| Point | Concept | Render | Result |
| --- | --- | --- | --- |
| Information architecture | Intake, position, recovery, blockers, evidence | Same visual ownership; semantic reading starts with Current Position before Intake | Match with accessibility refinement |
| Palette | Warm paper, white evidence surfaces, dark recovery rail, semantic signal colors | Exact CSS tokens from design spec | Match |
| Typography | Strong editorial position, compact mono identifiers, deliberate control text | Segoe UI/Aptos + Cascadia/Consolas hierarchy | Match |
| Container model | Three rails, ruled evidence, no decorative card grid | Same; conflict spans center/right below primary row | Match |
| Dynamic copy | Failed position, BLOCKED voltage, one authorized resolution | Exact deterministic demo result | Match |
| Orientation guide | Integrated ZNAK figure, blocker signal, and one selected action | One compact module; one full action node, matching marker, reason, sources, and machine condition | Match with responsive scale refinement |
| Recovery treatment | Dark rail, explicit derived warning, copy control | Same | Match |
| Responsive behavior | Single-column current-position-first mobile flow | Complete guide/action inside 390×844 opening view; no overflow at 390px or 320px; 44px controls | Match |
| Interaction | Rerun, filtering, Recovery Card copy | Rerun/filter/copy payload verified in the isolated headless context | Match within local browser scope |
| Motion access | Restrained assistant motion | One finite cue per result, distinct character motion per voltage, one matching marker, and no motion under `prefers-reduced-motion: reduce` | Match |

## Above-the-fold copy diff

Static functional copy includes `ZNAK ORIENT`, section names, `Choose JSON`, `Re-run orientation`, `Orientation guide`, `One justified next action`, filters, semantic field labels, and the explicit Recovery Card derivation warning. Position, goal, voltage, guide state, sources, and next-step content come from the result or the closed voltage presentation map. No decorative eyebrow, fake metric, marketplace, account, 3D map, or unexplained percentage was added.

## Fixes made during QA

- removed the initial success toast that covered content in screenshots;
- added the required JSON import control to the design reference;
- updated the concept hash and Recovery Card copy control;
- aligned the concept grid with the implemented conflict span and real data density;
- integrated the requested animated ZNAK figure with the canonical action instead of duplicating that action;
- added finite voltage-specific motion, a pointing arm, one matching state marker, and complete reduced-motion suppression;
- made Current Position first in semantic order while retaining the desktop intake rail;
- replaced the invisible file-input focus target with a native button and a dual-contrast focus ring;
- added a concise atomic live status, pressed-state filters, a persistent inline import error, scoped table headers, and a named evidence region;
- kept the complete guide/action inside the 390×844 opening view and removed horizontal overflow at 320px;
- removed the guide gradient and retained scroll-safe evidence tables.

## Intentional limitations

The in-app browser's clipboard API returned an empty read after the page reported a successful copy. A separate isolated headless Chromium run with explicit local clipboard permission did read the payload and verify `source_of_truth = false` plus `write_back_allowed = false`. This proves only that tested local context, not clipboard support in other browsers. The same flags remain independently covered by automated tests.

The implementation makes the assistant smaller than the concept to keep the full action and figure visible on a 390×844 screen. That is an intentional responsive scale change, not a change in ownership or meaning. The visible synthetic walkthrough centers on `BLOCKED`; separately, the retained machine-readable browser workflow executes and verifies `BLOCKED`, `FLOWING`, `WEAK`, `BROKEN`, and `UNKNOWN`, including the corresponding reduced-motion states. The video is not represented as a narrated visual tour of all five states.

## Retained image hashes

| Artifact | Dimensions | SHA-256 |
| --- | --- | --- |
| `design-concept-1440x900.png` | 1440×900 | `2a44073a724801674a5365e96f5c59155ea6682f9607a044740b908361e0e71d` |
| `ui-desktop-1440x900.png` | 1440×900 | `46ea419f55fba07e0b6cb753504934b01631db81896809217fd0eb9903f04de0` |
| `ui-mobile-390x844.png` | 390×844 | `a15fc5dcffaa25dc1e8f0fb720707c968c382d8e902cc2747b499739c0bff269` |
