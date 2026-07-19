# Repository and judging access

## Current verified local repository

```text
C:\path\to\znak-orient
```

- branch: `main`
- remote: none
- publication status: `BLOCKED_BY_EXPLICIT_CONFIRMATION_GATE`

Judges with filesystem access can clone the repository directly:

```powershell
git clone "C:\path\to\znak-orient" znak-orient-judge
Set-Location znak-orient-judge
python -m unittest discover -s tests -v
python -m znak_orient verify-demo --input demo/evidence-package.json --output artifacts/demo-result.json
python -m znak_orient serve --host 127.0.0.1 --port 8765
```

A source archive generated from the final Git HEAD is supplied beside the repository as `znak-orient-source.zip`.

## GitHub handoff after explicit confirmation

No GitHub repository, remote, issue, release, or deployment has been created. After the user explicitly approves publication:

1. create the intended GitHub repository under the user-selected owner and visibility;
2. add its exact URL as `origin`;
3. push `main`;
4. clone that remote into a fresh short path;
5. rerun the three judging commands above;
6. record the remote URL, commit, command outputs, and access visibility in a new validation receipt.

Do not substitute an invented URL in Devpost. Until the gated steps run, the GitHub field remains `BLOCKED / NOT_PUBLISHED`.
