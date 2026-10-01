# ZNAK Game Runtime v0.2 — Slice 1 implementation receipt

TARGET_REPO: HumbleDrummer/znak-orient  
BASELINE: c045d3b1649beab29297f3a602796ac1180f215a  
BRANCH: feature/znak-game-runtime-v0.2-slice1

SCOPE:
- C01 ObservationEventAdapter
- C02 ActionContract
- C07 RunTrace
- T17, T18, T19, T20, T30

WORK_STATE: IMPLEMENTED_AND_LOCALLY_TESTED  
EXTERNAL_RUNTIME_INTEGRATION: NOT_IMPLEMENTED  
REAL_ARC_DISPATCH: NOT_EXECUTED

## Local test execution

Command:

\`\`\`text
python /mnt/data/znak_game_runtime_slice1/test_znak_game_runtime_slice1.py
\`\`\`

Observed result:

\`\`\`text
test_T17_multi_subframe_preservation ... ok
test_T18_delayed_effect_attribution ... ok
test_T19_missing_parameter_rejected ... ok
test_T20_unavailable_action_rejected ... ok
test_T30_deterministic_derived_replay ... ok
test_previous_outcome_required_before_next_decision ... ok
test_terminal_state_blocks_action ... ok

Ran 7 tests in 0.001s
OK
\`\`\`

## Claim boundary

This receipt proves only local execution of the isolated Slice 1 fixtures against
the locally generated implementation. It does not prove integration with TAAF/GameAPI,
Kaggle, a real ARC-AGI-3 environment, or any performance improvement.

The repository branch contents must be fetched and compared before claiming byte-for-byte
equivalence with the local tested snapshot.
