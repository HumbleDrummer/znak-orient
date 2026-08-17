# Monetization playbook — znak-orient

This is an operator playbook, not a claim that any of this has been executed. Every account signup, payment connection, and identity verification below has to be done by a human who owns the project — none of it can be done on your behalf. What follows is ready-to-paste copy and an exact sequence so that part takes minutes, not days.

Context: the OpenAI Build Week deadline (2026-07-21) has passed, so `BUILD_WEEK_SUBMISSION_CHECKLIST.md` is no longer a revenue path. This playbook replaces it with four tracks that can run in parallel. They are ordered by time-to-first-dollar, not by ceiling.

## Positioning (use this everywhere)

znak-orient is a local, deterministic tool that recovers a trustworthy project status from messy, partial, or contradictory notes — including notes written by AI coding agents across sessions. The specific, timely pain it solves: AI agent sessions (Claude Code, Codex, Cursor, etc.) routinely lose context between runs, restate stale claims as current, or silently overwrite disputed decisions. znak-orient rejects unsupported completion claims, keeps conflicting claims visible instead of merging them, and produces one machine-verifiable next step instead of a wall of text. It runs on the Python standard library only — no model call, no credential, no network dependency — so it is auditable and safe to run against untrusted evidence.

Use that framing (not "hackathon project") in every listing below — it is the actual sellable differentiator in 2026's market.

## Track A — Passive / lowest effort (minutes to enable, income depends on traffic)

**GitHub Sponsors + Ko-fi.** `.github/FUNDING.yml` is already scaffolded in this repo with the right keys — it just has placeholder comments instead of usernames.

1. Enable GitHub Sponsors: github.com/sponsors → follow the billing-profile flow (requires your identity, GitHub does the KYC).
2. Create a Ko-fi account (or skip it and just use GitHub Sponsors + a custom link) — ko-fi.com, free tier is enough to start.
3. Edit `.github/FUNDING.yml` and replace the placeholders with your usernames/URL. Commit and push.
4. Add one line near the top of `README.md`: `> If this tool is useful to you, consider [sponsoring the project](your-link).`

This alone won't produce meaningful income without traffic. Its job is to capture the traffic Track B and C generate, so do it first because it's free and takes five minutes.

## Track B — Sell a companion product (days, requires you to price and list it)

The core tool is MIT-licensed, so selling the code itself is a bad plan — anyone can already clone it for free, and relicensing now would break the "IMPLEMENTED_TESTED_PUBLIC_JUDGING_REPOSITORY" claims already published in this repo's history. Instead, sell what the free tool doesn't include: packaged templates and setup work for a specific audience.

**Product: "znak-orient Evidence Pack for AI Coding Agents" — suggested price $19–$39, one-time.**

Built and committed in this repo:
- `templates/evidence-packs/ai-agent-session-template.json` — a working, engine-verified evidence package modeling a real multi-session AI-agent scenario (Claude Code → Codex → Cursor), covering a stale entrypoint conflict, a failed clean-checkout receipt, an unauthorized "just mark it done" chat claim, and an inert prompt-injection attempt. Verified to produce `ORIENTATION_PASS` via the actual CLI.
- `tools/build_ai_agent_evidence_pack.py` — the generator that produced it, using the real `znak_orient.canonical`/`znak_orient.contracts` functions so every integrity hash and receipt pointer is correct by construction. This is also the customization path: copy it, edit the source/receipt/lamp content, rerun.
- `docs/AI_AGENT_EVIDENCE_PLAYBOOK.md` — the explainer: what problem this catches, how the scenario plays out, and a 5-step adaptation guide for a buyer's own project.

Not yet built: a packaged PDF version of the playbook and per-tool starter variants (a Cursor-only template, a multi-repo template). Build those once the base pack has sold a few copies — no point polishing a variant before the first one is validated.

Listing platform: Gumroad or Lemon Squeezy (both let an individual sign up and list a digital product same-day; Lemon Squeezy acts as merchant of record, which is simpler for tax/VAT if you're outside the US). Listing needs your own account — I can't create it, but the product description below is ready to paste in once you have.

Copy-paste product description draft:

> **Stop losing project state between AI coding sessions.**
> znak-orient is an open-source, deterministic tool that turns a messy pile of AI agent notes into one trustworthy status: what's actually done, what's disputed, what's unknown, and the single next step — with sources, not vibes.
> This pack gives you the fast path: ready-made evidence templates for Claude Code / Codex / Cursor sessions, a setup playbook, and a converter script — so you're running it on your own project in under 15 minutes instead of building the evidence format yourself.
> The core engine is free and MIT-licensed on GitHub. This pack is the setup shortcut.

I can build the templates, playbook, and converter script now if you want this track — say so and I'll implement them in this repo.

## Track C — Freelance / portfolio (days to weeks, highest $/hour once it lands)

Use this project as proof-of-skill on Upwork/Fiverr/Toptal rather than trying to sell the project itself. Paste-ready case-study blurb for a freelance profile "portfolio" section:

> **znak-orient — deterministic state-recovery engine (Python, zero dependencies)**
> Designed and built a local developer tool that reconstructs a trustworthy project status from partial, stale, duplicated, and contradictory evidence, including adversarial/prompt-injection input. Enforced strict contracts (subject-scoped fact validation, causal source/receipt ordering, immutable receipt lineage through fallback), shipped with a 121-test suite green on Windows/macOS/Linux CI, and a code-native local web UI with CSP and input-sanitization hardening — no external runtime dependency. Full source: github.com/HumbleDrummer/znak-orient

Pitch this specifically into two current-demand niches where it's a strong signal: (1) "AI agent tooling / context engineering" gigs, (2) general Python backend / deterministic-systems roles. Apply with this project attached rather than a generic profile — it's a stronger signal than most portfolio pieces because it has tests, CI, and documented design tradeoffs.

## Track D — Sell a second, independent product: the Sales & Closing Agent Pack (days, requires listing it)

Built and committed at `products/sales-agent-pack/`: five specialized Claude Code subagents (lead qualifier, sales copywriter, objection handler/closer, follow-up strategist, pricing negotiator) that plug into any Claude Code project via `.claude/agents/`. Each one encodes a specific, well-established sales discipline (BANT qualification, consultative needs discovery, feature-to-benefit copywriting, acknowledge-then-resolve objection handling, value-anchored pricing) — the value being sold is the judgment built into each agent's instructions, not a generic "write me a sales email" prompt.

This is a separate audience from Track B (freelancers/small teams doing their own sales with Claude Code, not necessarily znak-orient users), so it doubles your addressable buyers rather than competing with Track B for the same ones. `products/sales-agent-pack/example-output/evidence-pack-cold-outreach.md` is a worked example — the pack's own copywriter agent used to draft outreach for the Track B product — worth linking to from the listing as proof the pack produces usable output, not just advice.

Copy-paste product description draft:

> **Five sales specialists for your Claude Code sessions — not one generalist bot.**
> Qualify a lead, write the pitch, handle the objection, follow up without being annoying, negotiate price — each stage has its own agent, built on well-established sales methodology (BANT, consultative selling, value-based pricing). Drop the files into `.claude/agents/` and Claude Code routes to the right one automatically.
> Every agent drafts only — you stay in control of what actually gets sent. That's not a limitation, it's what makes the output trustworthy enough to use.
> $[15–29] one-time. Full source and worked example included.

Suggested price: $15–$29 one-time — lower than Track B's technical audience price point, because the buyer pool (freelancers/solo founders doing their own sales) is more price-sensitive and this is a lighter-weight download.

## Track E — SiteDoctor: a service business, not a download (weeks, highest ceiling, most moving parts)

Built and committed at `products/sitedoctor/`: a working, tested (19/19 passing) technical-audit engine — SSL/security-headers/response-time/DNS checks, 0-100 scoring, Markdown report generation with an explicitly-labeled "cost of neglect" estimate and competitor comparison, and a CLI. This is real, runnable code, not a spec.

This came from a much more aggressive prompt (scrape 500 store domains, cold-email them on a fixed schedule "until commission appears," projected $392 MRR + $4,000 setup fees in 24 days). `products/sitedoctor/README.md` documents exactly what changed and why: the scrape-and-cold-email acquisition model was replaced with a **pull model** (a visitor requests their own free audit) because unsolicited commercial email carries real legal exposure under GDPR/Polish e-commerce law that an unsubscribe link doesn't resolve, and because a self-requested audit converts better anyway. The revenue mechanism itself — white-label partners (agencies) sell monitoring/fixes to their own clients, you take 40% recurring + a $200 setup fee per client, referrers get 20% — is unchanged and is in `products/sitedoctor/templates/partner-agreement.md` as a starting draft (have a lawyer review it before anyone signs).

This is the slowest track to first dollar of the four, because unlike Track B/D it isn't a finished download — it needs a landing page, hosting (Vercel/Supabase or equivalent), and real conversations with agency partners before it produces revenue. It also has the highest ceiling: recurring revenue with a partner doing the selling scales past what a one-time digital-product sale can.

What's not built, in order of what to do next: (1) the self-serve landing page where someone submits their domain for a free audit — I can build the markup/API contract on request; (2) picking and setting up hosting for it, which needs your account; (3) actual outreach to 5-10 real agencies using `products/sitedoctor/templates/partner-agreement.md` as the starting point for a real conversation, not an automated blast.

## What to do this week, in order

1. Fill in `.github/FUNDING.yml` and push (5 minutes, needs your GitHub Sponsors/Ko-fi username).
2. Sign up for Gumroad or Lemon Squeezy, create a listing using the Track B product description above, and attach `templates/evidence-packs/ai-agent-session-template.json` + `docs/AI_AGENT_EVIDENCE_PLAYBOOK.md` as the deliverable (zip them together). This is built and ready to sell now.
3. On the same account, list Track D using its product description above, attaching everything in `products/sales-agent-pack/` zipped up. Also built and ready to sell now.
4. Copy the Track C blurb into an Upwork/Fiverr profile and apply to 5–10 relevant listings; that's the fastest actual dollars, and it's on you because it requires an account under your identity.
5. If you want to pursue Track E, tell me and I'll build the landing page next — but the actual agency conversations and hosting choice are yours to make; I can't automate a real business relationship into existing.
