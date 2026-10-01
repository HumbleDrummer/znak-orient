# ZNAK Game Runtime v0.2 — Slice 1

Implements the first vertical slice of the runtime contract:

- C01 \`ObservationEventAdapter\`
- C02 \`ActionContract\`
- C07 \`RunTrace\`

Covered contract tests:

- T17 multi-subframe preservation
- T18 delayed-effect attribution
- T19 missing required action parameter
- T20 unavailable action
- T30 deterministic derived replay

This slice intentionally does **not** dispatch to the real ARC environment yet.
It ends at a typed, validated \`dispatch_payload\`. Integration with the actual
TAAF/GameAPI boundary is a separate gate because that source layer was not
inspected as part of this implementation.

Run locally:

\`\`\`bash
python test_znak_game_runtime_slice1.py
\`\`\`
