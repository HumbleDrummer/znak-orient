# Clean-checkout validation receipt — 2026-07-19

## Scope and identity

- status: `PASS`
- scope: committed local competition candidate, synthetic fixture, clean local clone
- validated commit: `2a3b961e54c0d5fb0d2e269379cf4024a5304da9`
- validated tree: `fc86659b11eaec303b231cbbe8e7225d5a1ef4e8`
- execution time: `2026-07-19T12:57:19+02:00`
- toolchain: Python `3.11.9`; Git `2.55.0.windows.2`
- clone method: `git clone --local --no-hardlinks`
- tracked files: `42`
- public remote: none; the clone's `origin` was only the local source path

This in-repository receipt necessarily validates the candidate commit immediately before the receipt itself was added. Reproducibility of the later receipt-bearing final HEAD is recorded in the separate output-level `ZNAK_ORIENT_FINAL_VALIDATION_2026-07-19.md` so the evidence does not make a circular claim about its own commit.

## Executed gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Fresh checkout | `PASS` | New non-existing clone directory; exact commit above |
| Automated suite | `PASS` | `Ran 104 tests in 6.442s`; `OK` (6.830 s measured wall time) |
| Bytecode compilation | `PASS` | `python -m compileall -q znak_orient tests`, exit 0 |
| Deterministic CLI | `PASS` | `ORIENTATION_PASS checkpoint=cp:3676e65da2ad0981`; output SHA-256 `9a0f24f4ea20653790dae893ae50749e9c2a55b1ef61d2e9fc91587eee7f10b4` |
| Checkpoint integrity | `PASS` | `666249a080192b88ab44c8d4163554d8c1688baf2c259d2cd85dc4352caf05f5`; two retained validation-receipt pointers |
| Loopback index | `PASS` | HTTP 200, CSP and `nosniff` present, `orientation-guide` present |
| Loopback APIs | `PASS` | `GET /api/demo` and `POST /api/orient` returned HTTP 200; checkpoint and integrity matched the CLI; voltage `BLOCKED`; exactly one next step |
| Browser workflow receipt | `PASS` | 15/15 checks true; no console/page errors |
| High-confidence secret scan | `PASS` | no matching files for AWS/GitHub/OpenAI/private-key patterns |
| Worktree after execution | `PASS` | `git status --short` empty; generated JSON and bytecode remained ignored |

## Retained browser and media evidence

- `artifacts/browser-qa.json`: SHA-256 `64952fbca8f4395af4448a5cd37509265f08662f1e6bee566318d7c28b2dd733`
- `artifacts/znak-orient-demo.webm`: 34.92 s, 1440×900 VP8 WebM, SHA-256 `eb3aadb035cf6e081c6dd5b14a2a45d2fb948e4316ece04810c95cba49db3382`
- `artifacts/ui-desktop-1440x900.png`: SHA-256 `e68ed57cc633ae80f18bcdb4cf0da3e804463cec0b6e928b2e35abc170bfc59d`
- `artifacts/ui-mobile-390x844.png`: SHA-256 `a046e1f0218fecdee0b767e6136350baf295d1fcfad9c01b4b1897f0219ef573`
- `artifacts/design-concept-1440x900.png`: SHA-256 `733ddacd9510a5dad99ad47377f6f303e9826f9ca27e6cb65c4a6b0a1ad73f92`

## Claim boundary

`PASS` means the committed local synthetic vertical slice was reproducible under the executed gates. It does not mean the imported project is complete, the synthetic sources are externally true, authorization strings are authenticated identities, X30 is canonically ratified, compressed memory outperforms raw notes, the product is production-ready, or GitHub/Devpost/public deployment/video publication has occurred.
