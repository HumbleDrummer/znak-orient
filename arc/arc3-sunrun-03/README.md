# ZNAK ARC3 Sunrun 03 Sprint4h

ARC-AGI-3 Kaggle competition candidate derived from the Sunrun 01 harness.

## Purpose

The ordinary Kaggle commit uses a FastGate path that writes the required placeholder output and exits quickly. The Kaggle competition rerun executes the full offline Qwen-backed ARC-AGI-3 agent path with internet disabled.

The competition path is capped to **3h35m from notebook start** to fit the remaining weekly RTX Pro 6000 budget and leave time for teardown.

## Provenance

- Base harness: public Tufa Labs Duck harness lineage, retained in notebook attribution.
- Model/runtime: Qwen3.8 Flash Next NVFP4 vLLM bundle attached through Kaggle model/dataset sources.
- Candidate notebook SHA-256: `b8031cd41616c95cdb81653651b45a2722bbcc63a3cb729f68b41c11c6ee5c34`.
- Kaggle kernel: `znakhumbledrummer/znak-arc3-sunrun-03-sprint4h`, version 1.
- Internet: OFF.

## Result boundary

No official Kaggle score is claimed here until the code-competition rerun reaches a terminal submission state and Kaggle reports a score.

A separate interactive Sunrun 01 benchmark on 2026-09-23 completed 25 games in 7h59m with a local mean score of 15.30. That run had `TRUE_SUBMISSION=False` and is therefore **not** represented as an official Kaggle competition result.
