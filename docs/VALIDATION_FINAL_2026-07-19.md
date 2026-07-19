# Final candidate D clean-checkout receipt — 2026-07-19

## Scope and identity

- status: `PASS_WITH_PRE_FIX_BUG_DISCLOSURE`
- scope: local deterministic engine, rejected-HTTP-response stabilization on Windows, CLI/HTTP/browser replay, retained UI media, and local handoff readiness
- validated candidate: `D`
- validated candidate commit: `3fe426b90029fcd65eb5572b1724e78ee564a089`
- validated candidate tree: `bed0a5702bc9a76e71681b17ead818d48974c20d`
- validation working directory: `work/windows-clean-3fe426b`
- validation started: `2026-07-19T19:59:40.7489484+02:00`
- clone boundary: fresh clean clone of the exact candidate above
- tracked files: `45`

This receipt validates candidate D at the exact commit and tree above. The commit and tree identity, including the 45-file tracked inventory, were also resolved from the local repository. This document does **not** validate the later commit that adds this receipt, its links, or any subsequent documentation change. A receipt cannot serve as evidence for the commit that first contains the receipt itself; that later receipt-bearing HEAD requires a separate scoped verification.

## Executed clean-clone gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Fresh clone identity | `PASS` | Exact candidate D commit/tree above; 45 tracked files |
| Isolated rejected-request regression | `PASS` | `tests.test_server.ServerTests.test_wrong_media_type_and_unknown_path_fail_closed` passed in 0.532 s |
| Full automated suite | `PASS` | 121/121 tests passed in 7.686 s |
| Additional wrong-media stress | `PASS` | 25/25 additional wrong-media attempts returned the expected rejection without a connection abort |
| Bytecode compilation | `PASS` | `compileall` completed successfully |
| JavaScript syntax | `PASS` | Browser application and recorder scripts passed syntax validation |
| Deterministic CLI | `PASS` | checkpoint `cp:a58ca1e52c138e54`; generated JSON SHA-256 `61f8983bc39421f17f1f599df58c4f3629659c8bc60c25138156d29b9aba0027` |
| Clone worktree after unit/CLI gates | `PASS` | Clean after the unit and CLI execution phase |

The clean-worktree claim is intentionally limited to the unit/CLI boundary. The later browser recorder creates or refreshes media outputs; this receipt does not transfer the earlier clean status across that mutation.

## Windows rejected-response bug disclosure

Before candidate D, fresh Windows validation encountered `ConnectionAbortedError` / `WinError 10053` twice. The failing path rejected a POST with HTTP 415 while leaving the request body unread; Windows could abort the connection before the client received and consumed the response. These two failures are not rewritten as passes and are not included in candidate D's successful run counts.

Candidate D adds a bounded request-body drain before rejected POST responses on the affected HTTP 403, 404, and 415 paths. The drain is limited by the existing request-size boundary; it is not an unbounded read. The fix is evidenced here by the isolated regression test, 25/25 additional wrong-media attempts, and the full 121-test suite. These local results support the named Windows failure mode and candidate only; they are not a general proof about every client, network stack, or production server.

## Browser replay from the same clone

| Gate | Result | Evidence |
| --- | --- | --- |
| Named browser workflow | `PASS` | Exactly 39/39 checks true |
| Expected console event | `PASS_SCOPED` | Exactly one deliberate HTTP 400 event from the invalid-input test |
| Unexpected console errors | `PASS` | 0 |
| Page errors | `PASS` | 0 |
| Browser QA receipt | `PASS_BYTE_EXACT` | SHA-256 `b296d590c4c03ea732c7004adbd97a792420b939b6a3fe2149ff418e426472ed` |
| Desktop render | `PASS_BYTE_EXACT` | SHA-256 `46ea419f55fba07e0b6cb753504934b01631db81896809217fd0eb9903f04de0`; byte-identical to the candidate source artifact |
| Mobile render | `PASS_VISUAL_EQUIVALENCE` | Clone SHA-256 `b71becf4b30f278e9cf19ea11c0ce6000fb2ac95102737853e679f9c603d8f4c`; versus the candidate source artifact, only 8 pixels / 11 channel samples differ, maximum delta 1, within `x=369..373`, `y=115..117` |
| Local WebM replay | `PASS_SCOPED` | VP8, 1440×900, 25 fps, 47.00 s, 4,165,801 bytes, SHA-256 `0ceead67a24e30a71a35adefe32742c274af02444b8b2bdb1c7127d8ed1f62b3` |

The mobile difference is limited to the measured one-level channel changes in the stated five-by-three-pixel bounding box and is visually negligible in this replay. This supports scoped rendering equivalence, not byte identity or universal cross-platform pixel determinism. The WebM is a local replay artifact; byte identity with another encoding is not claimed.

## External gates — unchanged

| External action or claim | Status |
| --- | --- |
| GitHub judging repository | `BLOCKED / NOT_PUBLISHED / USER_GATED` |
| Public deployment | `BLOCKED / NOT_DEPLOYED / USER_GATED` |
| Devpost submission | `NOT_EXECUTED / DRAFT_ONLY / USER_GATED` |
| Video publication | `NOT_EXECUTED / NOT_PUBLISHED / USER_GATED` |
| `/feedback` submission | `NOT_EXECUTED / USER_GATED` |
| Paid API or real-model execution | `NOT_EXECUTED / NOT_REQUIRED / USER_GATED` |
| Production readiness or authenticated authorization | `UNKNOWN / NOT_CLAIMED` |

No local test, browser replay, screenshot, or video file changes these external statuses. Each action remains behind its existing explicit user-confirmation and external-evidence gate.

## Claim boundary

`PASS_WITH_PRE_FIX_BUG_DISCLOSURE` means candidate D at commit `3fe426b90029fcd65eb5572b1724e78ee564a089` and tree `bed0a5702bc9a76e71681b17ead818d48974c20d` passed the listed local clean-clone and browser gates after the disclosed rejected-body fix. It does not prove external source truth, authenticated identities, production readiness, canonical X30 conformance, superiority over raw notes, GitHub publication, public deployment, Devpost submission, video publication, `/feedback` submission, paid API execution, or real-model execution. It also does not validate the later commit that contains this receipt.
