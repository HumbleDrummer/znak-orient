# Sales & Closing Agent Pack for Claude Code

Five specialized Claude Code subagents that cover one stage each of a sales pipeline: qualifying a lead, writing the outreach/pitch, handling objections and closing, following up when it goes quiet, and negotiating price. Drop them into `.claude/agents/` in any project and Claude Code will route to the right one automatically based on what you're doing.

This is deliberately not a single "do everything" sales bot. A pipeline of specialists each of whom does one thing well and hands off cleanly produces better output than one prompt trying to be a lead-gen tool, a copywriter, a negotiator, and a closer at once — the same reason real sales orgs split these roles across people instead of one generalist.

## The pipeline

```
new prospect
     │
     ▼
lead-qualifier ──────► verdict: QUALIFIED / NURTURE / DISQUALIFY
     │ (QUALIFIED)
     ▼
sales-copywriter ─────► drafts the outreach/pitch/landing copy
     │
     ▼
  [human sends it]
     │
     ├── objection raised or ready to decide ──► objection-handler-closer
     │
     ├── price pushback specifically ──────────► pricing-negotiator
     │
     └── goes quiet ────────────────────────────► follow-up-strategist
```

Every agent's job ends at a draft. None of them contact anyone directly — a human reviews and sends. That boundary is intentional, not a limitation to work around: unsolicited messages sent without review risk reading as spam, and a fabricated testimonial, fake deadline, or invented statistic (which an unsupervised "close at all costs" agent would eventually reach for) destroys the credibility the whole system depends on. The value this pack sells is the quality of judgment encoded in each agent, not unsupervised autonomy — a human in the loop is what makes that judgment trustworthy enough to act on.

## What's inside

| Agent | File | Use it when |
| --- | --- | --- |
| Lead Qualifier | `agents/lead-qualifier.md` | A new prospect or inbound inquiry needs a fit/readiness verdict (BANT) before you spend time on them. |
| Sales Copywriter | `agents/sales-copywriter.md` | You need outreach copy, landing page copy, or a product description for a specific offer and audience. |
| Objection Handler & Closer | `agents/objection-handler-closer.md` | A specific objection came back, or a qualified prospect is ready to be asked for the decision. |
| Follow-Up Strategist | `agents/follow-up-strategist.md` | A prospect went quiet and you need a deliberate, non-annoying multi-touch sequence instead of one more "just checking in." |
| Pricing Negotiator | `agents/pricing-negotiator.md` | Setting a price, or responding to price pushback or a counter-offer. |

The methodology behind each agent draws on well-established, widely taught sales frameworks — BANT qualification, SPIN/consultative needs discovery, feature-to-benefit translation, the acknowledge-then-resolve objection structure, value-anchored pricing — in the tradition of classic sales writers like Brian Tracy, Zig Ziglar, and Neil Rackham. Nothing here is a copied excerpt from any book; it's the agents' own operating instructions, written from those principles.

## Install

1. Copy the `agents/` folder's contents into your own project's `.claude/agents/` directory (or your user-level `~/.claude/agents/` to have them everywhere).
2. In Claude Code, describe what you're doing ("qualify this lead," "write a cold email for X," "they said it's too expensive") — the right agent is picked up automatically from its `description`, or invoke one by name directly.
3. Review every draft before it goes anywhere near a real prospect. These agents are good at structure and judgment; you're still the one who knows the actual relationship.

## Suggested price

$15–$29 one-time on Gumroad/Lemon Squeezy, positioned as a Claude Code add-on for freelancers and small teams doing their own sales. See `docs/MONETIZATION.md` (Track D) in the main repo for listing copy.
