# ZNAK ARC-AGI-3 public evidence receipt

- Archive ID: `ZNAK-20260903-ARC-AGI-3-RESULTS-v1.0`
- Evidence date: `2026-09-03`
- Public scorecards: `25`
- Locally retained complete recordings: `25`
- Verified wins: `25/25`
- Levels: `183/183`
- Counted actions: `6,992`
- Counted retry resets: `0`
- Validation errors: `0`

Every physical NDJSON record in all 25 locally retained recordings was parsed and checked. Validation covered exact game and recording identifiers, one initial `RESET` with `full_reset=true`, no later retry reset, action count, monotonic level progress, and terminal `WIN`.

Three independent read-only audits covered all 25 tasks and found no mismatches. A scan of the 51 downloaded files found no API keys, private keys, tokens, cookies, passwords, email addresses, or local user paths.

For DC22, the retained recording is the completed 434-action `WIN` run with GUID `08d7d5d9-2f11-4c41-afb9-1fc6648716ca`, not the empty `NOT_FINISHED` initialization run retained on the public scorecard.

Raw ARC Prize payloads remain in the local archive and are not redistributed here. This receipt records validation of platform-reported public-game outcomes; it is not ARC Prize certification or endorsement.
