# ZNAK ORIENT

ZNAK ORIENT is a local, deterministic developer tool for recovering project direction from partial, stale, duplicated, contradictory, or untrusted evidence. It keeps facts, decisions, authority, and epistemic status separate; preserves material conflicts; and returns one source-backed corrective next step.

Project status while this build is in progress: `DESIGN_CANDIDATE`.

The runtime uses Python 3.11+ and the standard library. It makes no model, paid API, telemetry, publishing, or deployment calls.

## Planned local commands

```powershell
python -m unittest discover -s tests -v
python -m znak_orient verify-demo --input demo/evidence-package.json --output artifacts/demo-result.json
python -m znak_orient serve --host 127.0.0.1 --port 8765
```

The commands above become claims only after they are executed and retained in the final validation receipt.

