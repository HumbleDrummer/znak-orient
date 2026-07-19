# Repository and judging access

## Public judging repository

- URL: `https://github.com/HumbleDrummer/znak-orient`
- owner: `HumbleDrummer`
- visibility: `PUBLIC`
- branch: `main`
- remote: `origin = https://github.com/HumbleDrummer/znak-orient.git`

Judges can clone and execute the project directly:

```powershell
git clone https://github.com/HumbleDrummer/znak-orient.git znak-orient-judge
Set-Location znak-orient-judge
python -m unittest discover -s tests -v
python -m znak_orient verify-demo --input demo/evidence-package.json --output artifacts/demo-result.json
python -m znak_orient serve --host 127.0.0.1 --port 8765
```

On Windows, `start-znak-orient.bat` provides the same loopback-only start path without a build step.

## Verified publication baseline

- branch under test: current `main`
- GitHub Actions: [CI workflow](https://github.com/HumbleDrummer/znak-orient/actions), executing on Windows, Ubuntu, and macOS with Python 3.11
- privacy gate: no reachable `main` commit contains the removed local Windows user path or the private submission Session ID after the pre-publication history rewrite
- exact final commit, tree, workflow-run URL, remote-clone output, and archive hash: retained in the local publication handoff generated after the final CI run

The receipt-bearing documentation commit is verified by its own GitHub Actions run and the separate final handoff receipt. A public hosted deployment is not claimed or required to run this developer tool; the application remains loopback-only.
