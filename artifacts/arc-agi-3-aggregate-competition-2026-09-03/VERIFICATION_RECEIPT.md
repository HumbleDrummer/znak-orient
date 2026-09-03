# Verification receipt

Archive ID: `ZNAK-20260903-ARC-AGI-3-AGGREGATE-COMPETITION-v1.0`

Verdict: **PASS**

## Checks completed

- The unauthenticated public scorecard API matched the retained public scorecard capture.
- The public scorecard reported score `100`, `ai_agent: true`, Competition mode, 25/25 environments, 183/183 levels, 6,992 actions, and a publication timestamp.
- Exactly one public run was present for every expected environment.
- All 25 downloaded public recordings were parsed from beginning to end.
- Every action identity, payload, state, level counter, and frame fingerprint matched the frozen blueprint.
- Recomputed totals were 25 terminal `WIN` states, 183 level completions, 6,992 gameplay actions, and 0 counted retry resets.
- The 25 recording files totaled 7,017 NDJSON rows and 363,551,531 bytes.
- SHA-256 and byte counts were computed for every retained recording.
- The public package was scanned for credentials, tokens, passwords, cookies, e-mail addresses, account names, and absolute local user paths; none were detected.

Fresh recording verification completed at `2026-09-03T18:40:21.074956+00:00`.

## Publication boundary

Only authored metadata, verification results, integrity hashes, and official ARC Prize links are published in this folder. The raw third-party scorecard payload, close response, recordings, game frames, action payloads, and local runtime files remain outside the repository.
