# ZNAK Grid Orientator — ARC-AGI-1 / ARC-AGI-2

General-purpose ARC grid reasoning harness built around deterministic structural orientation plus a language-model solver. The orientator extracts task structure from training input/output pairs and test inputs, keeps cross-task mechanism memory between bounded attempts, and does not use hidden/reference outputs as execution input.

## Public-evaluation results

These are **self-reported local public-evaluation results**, not ARC Prize Verified scores and not Kaggle hidden-set scores.

- ARC-AGI-1 public evaluation: **389 / 400 = 97.25%**, three-attempt protocol.
- ARC-AGI-2 public evaluation: **94 / 120 = 78.33%**, two-attempt protocol.

The results were independently recomputed from saved per-task outputs by the local audit harness. The public evaluation sets are known/public; these numbers must not be described as unseen, semi-private, private, or ARC Prize Verified.

## System

- `arc_orientation_engine.py`: deterministic structural feature extraction and compositional mechanism memory.
- `run_arc1_full_attempt.py`: resumable ARC-AGI-1 public-evaluation runner.
- `run_arc2_full_attempt.py`: resumable ARC-AGI-2 public-evaluation runner.
- `audit_arc_grid_runs.py`: recomputes exact-grid task success from saved predictions.
- Model used for the recorded runs: GPT-5.6 Sol, high reasoning effort, invoked through the Codex CLI adapter.
- ARC-AGI-1 protocol: three prediction attempts.
- ARC-AGI-2 protocol: two prediction attempts.

## Reproducibility boundary

The code is public here so the method and harness can be inspected and rerun by users with access to the named model/runtime. The benchmark datasets remain governed by their upstream licenses and are not copied into this directory. Exact repository commits, manifests, run receipts and SHA-256 values are recorded in the accompanying evidence files.

## Claim label

`LOCAL_PUBLIC_RUN_NOT_VERIFIED`

This project does not claim ARC Prize endorsement, official verification, or a Kaggle competition result.

## Public evidence links

- Kaggle ARC-AGI-1 local public audit notebook: https://www.kaggle.com/code/znakhumbledrummer/znak-arc1-public-audit-97-25
- ARC Prize Community Leaderboard submission PR: https://github.com/arcprize/ARC-AGI-Community-Leaderboard/pull/57
