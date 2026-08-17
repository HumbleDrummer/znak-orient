# Monetization playbook — znak-orient

This is an operator playbook, not a claim that any of this has been executed. Every account signup, payment connection, and identity verification below has to be done by a human who owns the project — none of it can be done on your behalf. What follows is ready-to-paste copy and an exact sequence so that part takes minutes, not days.

Context: the OpenAI Build Week deadline (2026-07-21) has passed, so `BUILD_WEEK_SUBMISSION_CHECKLIST.md` is no longer a revenue path. This playbook replaces it with three tracks that can run in parallel. They are ordered by time-to-first-dollar, not by ceiling.

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

Contents to build (not yet built — this is the spec):
- Ready-made evidence-package JSON templates pre-wired for Claude Code, Codex, and Cursor session logs (the `demo/evidence-package.json` schema already in this repo is the base to extend).
- A short PDF/Markdown playbook: "how to keep an AI agent honest across sessions" — 5–8 pages, written from the design decisions already documented in `docs/ARCHITECTURE.md` and `docs/DESIGN_SYSTEM.md`.
- A CLI wrapper script that converts a raw Claude Code / Codex transcript export into a valid evidence package automatically.

Listing platform: Gumroad or Lemon Squeezy (both let an individual sign up and list a digital product same-day; Lemon Squeezy acts as merchant of record, which is simpler for tax/VAT if you're outside the US).

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

## What to do this week, in order

1. Fill in `.github/FUNDING.yml` and push (5 minutes, needs your GitHub Sponsors/Ko-fi username).
2. Tell me whether to build the Track B evidence-pack templates and playbook — I can do that in this repo now.
3. Copy the Track C blurb into an Upwork/Fiverr profile and apply to 5–10 relevant listings; that's the fastest actual dollars, and it's on you because it requires an account under your identity.
