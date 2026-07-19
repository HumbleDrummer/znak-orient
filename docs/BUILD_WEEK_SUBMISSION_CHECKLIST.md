# OpenAI Build Week submission checklist

Official source checked on 2026-07-19: [OpenAI Build Week Official Rules](https://openai.devpost.com/rules).

Submission deadline: **July 21, 2026 at 5:00 pm PDT**. This checklist is an evidence ledger, not a substitute for the official rules or Devpost form.

## Project identity

- project: **ZNAK ORIENT**
- category: **Developer Tools**
- GitHub owner: `HumbleDrummer`
- intended public repository: `https://github.com/HumbleDrummer/znak-orient`
- license: MIT
- principal Codex Session ID: `READY_FOR_FORM / retained outside public repository`

## Requirement status

| Requirement | Status | Evidence or next action |
| --- | --- | --- |
| Built with Codex and GPT-5.6 | `READY / DOCUMENTED` | README and `CODEX_COLLABORATION.md` describe the `gpt-5.6-sol` implementation workflow and human decisions. |
| Developer Tools category | `READY` | Category is named in the README and Devpost draft. |
| Working, consistently runnable project | `LOCAL_PASS / REMOTE_PASS` | 121-test local suite and deterministic CLI pass; the current-main workflow runs on Windows, Ubuntu, and macOS. |
| Repository URL for judging | `PUBLIC / VERIFIED` | `https://github.com/HumbleDrummer/znak-orient`; remote clone and visibility were checked after publication. |
| Relevant license | `READY` | MIT `LICENSE` is tracked. |
| README collaboration narrative | `READY` | README summarizes acceleration, human decisions, and Codex/GPT-5.6 contribution; detailed record is linked. |
| Installation and supported platform | `READY / CI_VERIFIED` | Python 3.11+, no runtime dependencies or build step; Windows launcher plus exact cross-platform commands. Windows was locally executed; Windows, Ubuntu, and macOS passed GitHub CI. |
| Judge test path without rebuilding | `READY_LOCAL` | Clone, run `unittest`, run deterministic demo, start loopback UI. No package build, credential, account, paid API, or model call is required. |
| Text description | `READY_DRAFT` | `DEVPOST_DRAFT.md` contains the English submission copy. |
| Demonstration video under 3 minutes with audio | `BLOCKED / NOT_COMPLIANT_YET` | Retained WebM is a silent local evidence capture. Record narration, upload publicly to YouTube, and add its URL. |
| Public YouTube URL | `BLOCKED / NOT_PUBLISHED` | Requires account-side upload after the compliant narrated video exists. |
| `/feedback` Codex Session ID | `READY_FOR_FORM` | Principal ID is retained in the private submission handoff; `/feedback` itself is not claimed as submitted. |
| Devpost registration and final submission | `UNKNOWN / NOT_EXECUTED` | Operator must confirm `Join Hackathon`, complete the account fields, accept the rules, and submit before the deadline. |
| Public hosted demo | `OPTIONAL / NOT_DEPLOYED` | Official rules require working access; this developer tool is directly runnable from the public repository without rebuilding. No hosted deployment is claimed. |

## Final operator sequence

1. Confirm the public GitHub repository and green CI run.
2. Record an English narrated demo shorter than three minutes using the tested build.
3. Upload the video publicly to YouTube and record the exact URL.
4. Open the Devpost submission, choose **Developer Tools**, and paste the reviewed text from `DEVPOST_DRAFT.md`.
5. Add the GitHub URL, YouTube URL, and principal Codex Session ID.
6. Review ownership, eligibility, team representation, and all form fields personally.
7. Submit before the official deadline and retain the Devpost confirmation URL/time.
