# Local interface design specification

This code-native specification replaces image-generation concepting because the build authorization explicitly blocks paid or real API/model calls without separate confirmation.

## Product surface

A single responsive orientation console, not a marketing page. The desktop opening viewport must show the project position, voltage, one next step, and the evidence intake disposition without decorative metrics. On a phone, direction takes precedence: position, voltage, and the complete next step remain in the opening viewport, while intake follows in the same semantic reading flow.

Required regions, in reading order:

1. header with product name, loaded package, checkpoint hash, and rerun control
2. Current Position with a voltage-reactive ZNAK assistant and exactly one primary next step
3. Noise Intake evidence rail
4. Conflict and Unknowns
5. non-authoritative Recovery Card
6. Source Evidence table
7. Validation Receipt

## Visual direction

- character: evidence desk / editorial control room
- background: exact `#f3f1eb` warm paper; surfaces `#ffffff`
- ink: `#17211d`; muted ink `#62706a`; rules `#d7d9d2`
- signal green: `#0f6d52`; caution amber: `#9a5d00`; conflict red: `#a9362a`; direction blue: `#2056a8`
- typography: Segoe UI/Aptos for interface text; Cascadia Mono/Consolas for identifiers and hashes
- geometry: square editorial panels with 8px corners; no nested card grid, glow, gradient, map, marketplace, or decorative percentage
- motion: one short, finite state-specific cue after each result (`BLOCKED` anchors, `FLOWING` steps, `WEAK` leans, `BROKEN` corrects, `UNKNOWN` considers), plus a pointing arm and one matching state marker; all animation is disabled under `prefers-reduced-motion`

## Layout and responsive behavior

At 1280×800 or wider, use a three-rail opening layout: 28% intake, 44% current position, 28% recovery. The visual rail may place Intake left of Current Position, but DOM and assistive-technology order remain Current Position then Intake. Conflicts span the center and recovery rails. Evidence and receipts form full-width ruled sections below. At tablet widths the recovery rail moves below current position. Under 720px all regions become one column, tables become horizontally scrollable, primary controls remain at least 44px high, dynamic identifiers wrap, and the layout does not overflow at 320px.

## Component families

- ruled section header with explicit item count
- evidence row with disposition bar and source identifier
- semantic status label used only for real state (`APPLIED`, `REJECTED`, `DISPUTED`, `UNKNOWN`)
- one integrated orientation module: code-native SVG ZNAK figure, finite voltage-specific motion, and the single canonical next-step text node with reason, sources, and machine-readable success-condition code
- source table and validation check rows
- code-native SVG direction/copy/reload icons with consistent 1.75px strokes
- native JSON chooser button, concise atomic live status, persistent inline import error, pressed-state filters, and a named scrollable evidence region

## Allowed opening copy

- `ZNAK ORIENT`
- `Current Position`
- `Noise Intake`
- `Conflict and Unknowns`
- `Recovery Card`
- `Choose JSON`
- `Re-run orientation`
- `Orientation guide`
- `One justified next action`
- functional labels for filters, `Goal`, `Base`, `Mode`, `Sources`, `success`, and the derived Recovery Card fields
- loaded package name, checkpoint hash, voltage, exact project goal, exact current position, and exact selected next step derived from the package

The guide's short state line is selected from a closed presentation map over the deterministic voltage. The integrated module contains exactly one visible full action, and it must equal the deterministic next-step instruction. All other dynamic text must come from the deterministic result, not invented UI claims.
