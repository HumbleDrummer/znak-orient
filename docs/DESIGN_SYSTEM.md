# Local interface design specification

This code-native specification replaces image-generation concepting because the build authorization explicitly blocks paid or real API/model calls without separate confirmation.

## Product surface

A single responsive orientation console, not a marketing page. The opening viewport must show the project position, voltage, one next step, and the evidence intake disposition without decorative metrics.

Required regions, in reading order:

1. header with product name, loaded package, checkpoint hash, and rerun control
2. Noise Intake evidence rail
3. Current Position and exactly one primary next step
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
- motion: one restrained result refresh transition; disabled under `prefers-reduced-motion`

## Layout and responsive behavior

At 1280×800 or wider, use a three-rail opening layout: 28% intake, 44% current position, 28% recovery. Conflicts span the center and recovery rails. Evidence and receipts form full-width ruled sections below. At tablet widths the recovery rail moves below current position. Under 720px all regions become one column, tables become horizontally scrollable, and primary controls remain at least 44px high.

## Component families

- ruled section header with explicit item count
- evidence row with disposition bar and source identifier
- semantic status label used only for real state (`APPLIED`, `REJECTED`, `DISPUTED`, `UNKNOWN`)
- next-step block with reason, sources, and success-condition code
- source table and validation check rows
- code-native SVG direction/copy/reload icons with consistent 1.75px strokes

## Allowed opening copy

- `ZNAK ORIENT`
- `Current Position`
- `Noise Intake`
- `Conflict and Unknowns`
- `Recovery Card`
- `Re-run orientation`
- loaded package name, checkpoint hash, voltage, exact project goal, exact current position, and exact selected next step derived from the package

All other dynamic text must come from the deterministic result, not invented UI claims.

