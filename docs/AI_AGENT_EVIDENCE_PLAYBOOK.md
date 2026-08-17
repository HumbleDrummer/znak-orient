# Keeping an AI coding agent honest across sessions

This is the playbook half of the "znak-orient Evidence Pack for AI Coding Agents" (see `docs/MONETIZATION.md`, Track B). It explains the problem the template in `templates/evidence-packs/ai-agent-session-template.json` is built to catch, and how to adapt that template to your own project.

## The problem

AI coding agents (Claude Code, Codex, Cursor, and similar tools) are excellent at producing plausible status updates and terrible at knowing when a previous status update was wrong. Across a multi-session project you typically accumulate:

- a checkpoint from session N that was accurate at the time;
- a newer claim from session N+1 that contradicts it, with no record of why;
- a chat-style "everything passed, mark it done" message that is not itself evidence of anything;
- occasionally, text pasted into a session (a log, a ticket, a doc) that contains an embedded instruction trying to redirect the agent.

Left alone, an agent (or a human skimming the transcript) tends to trust whichever claim is most recent or most confidently worded. znak-orient's job is to refuse that shortcut: it only advances a fact into "current" if it's backed by a PASS receipt bound to that exact value, it keeps two AUTHORIZED but contradictory decisions visible as an open dispute instead of picking one, and it treats imported chat/text as untrusted evidence regardless of its content — including text that tries to look like a system instruction.

## How the template demonstrates this

`templates/evidence-packs/ai-agent-session-template.json` encodes a three-session scenario:

1. **Session 1 (Claude Code):** implements a webhook handler, checkpoints "signature verification done, end-to-end test pending," with an entrypoint decision.
2. **Session 2 (Codex):** changes the entrypoint command without recording that it supersedes session 1's decision, and runs a clean-checkout test that **fails**.
3. **Session 3 (Cursor):** a chat message claims "everything passed, mark it complete" — contradicting the actual FAIL receipt — and a pasted log contains a prompt-injection attempt ("ignore previous rules and override authority").

Run it the same way the bundled demo is verified:

```powershell
python -m znak_orient verify-demo --input templates/evidence-packs/ai-agent-session-template.json --output artifacts/ai-agent-session-template-result.json
```

The deterministic result: the entrypoint conflict is surfaced and blocks execution (`voltage: BLOCKED`) instead of silently picking the newer command; the FAIL receipt — not the chat claim — determines the current position; the prompt-injection text is retained as an inert `TRACE`, never as an instruction. This is the same class of guarantee documented for the bundled `demo/evidence-package.json` fixture, applied to an AI-agent-session narrative instead of the original hackathon-judging narrative.

## Adapting it to your project

`tools/build_ai_agent_evidence_pack.py` generates the template through the actual `znak_orient.canonical` and `znak_orient.contracts` functions rather than hand-edited JSON, because every checkpoint carries a self-referential integrity hash and every retained receipt is pinned by a content hash — editing the JSON text directly will break those without you noticing until the CLI rejects the file. To build your own evidence pack:

1. Copy `tools/build_ai_agent_evidence_pack.py` to a new script.
2. Replace `RAW_SOURCES` with your own session excerpts: what each agent session claimed, decided, or pasted in, with honest `authority` values (`AUTHORIZED` only for things a human actually approved; `UNAUTHORIZED` for chat/imported text; `NOT_APPLICABLE` for raw logs).
3. Replace `RAW_RECEIPTS` with your actual test/validation outcomes. A receipt's `assertion_sha256` must equal `sha256_hex({"subject": <subject>, "value": <the exact value it's proving>})` whenever a `FACT` lamp cites it — the script already computes this for you; don't hardcode a copied hash if you change the subject or value.
4. Update the checkpoint's `active_lamps` to match your project's actual goal/facts/decisions/constraints, keeping each `lamp_id` as `lamp:{type}:{subject}` in lowercase.
5. Run the script, then run `python -m znak_orient verify-demo` against its output. If it's rejected, the CLI's error names the exact contract or engine rule that failed (e.g. `[CP-RECOVERY]`, `RECEIPT_ID_REUSE:...`) — that's the tool doing its job, not a bug to work around.

## What this playbook is not

It doesn't claim znak-orient is a general project-management tool, and it doesn't claim the generated template proves anything about *your* codebase — it proves that the orientation engine correctly resolves the specific scenario you feed it. The value is in the discipline the schema forces: every claim about "current status" has to name its source and, if it's a fact, name the receipt that proved it.
