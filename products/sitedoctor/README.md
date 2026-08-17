# SiteDoctor — technical audit engine for e-commerce sites

A dependency-free (Python standard library only, same philosophy as znak-orient) technical audit engine: point it at a domain, get a scored report covering SSL certificate health, security headers, homepage response time, and DNS resolution, with an optional "estimated cost of neglect" section and optional competitor comparison. Built as monetization Track E — see `docs/MONETIZATION.md` in the repo root.

This started from a much more aggressive prompt: scrape 500 store domains, cold-email them on a fixed day-0/3/7/14 schedule until they convert, and don't stop until commission appears. What's built here keeps the parts of that idea that are genuinely good — the audit tech, the report format, the partner/referral revenue model — and changes the acquisition model from **push** (scrape + unsolicited cold email) to **pull** (someone requests their own free audit). That's not a weaker version of the same plan; it's a legally cleaner one that also converts better, since a self-requested audit implies real interest and a self-requested audit is a clean, low-risk basis to email back under GDPR/Polish e-commerce law, unlike a cold blast to a scraped list.

## What's built and working

- `sitedoctor/checks.py` — SSL certificate validity/expiry, required security headers (HSTS, CSP, X-Content-Type-Options), homepage response time, DNS resolution. Every check takes an injectable fetch/resolve function, so it's unit-testable without hitting a real network.
- `sitedoctor/scoring.py` — turns check results into a 0-100 score with critical/high/medium buckets.
- `sitedoctor/report.py` — renders a Markdown report, including an "estimated cost of neglect" section (explicitly labeled as an estimate based on a commonly cited rule of thumb, not a measured fact) and an optional competitor score table.
- `sitedoctor/cli.py` — `python -m sitedoctor.cli audit <domain> --output report.md`, one domain at a time by design (see below).
- `tests/` — 19 unit tests, all passing, no network required (`python -m unittest discover -s tests`).
- `templates/emails/` — a day-0/3/7/14 sequence, rewritten for opt-in delivery (see `templates/emails/README.md` for why that distinction matters legally).
- `templates/partner-agreement.md` — a starting-point draft for a white-label revenue-share agreement (40% recurring + $200 setup fee, matching the original brief) — needs a real lawyer before anyone signs it.
- `examples/github-actions-weekly-audit.yml` — a template workflow for re-auditing an explicit, committed list of domains you have permission to audit — not a scraper.

## What's deliberately not built, and why

- **A 500-domain scraped target list.** Building a scraper to harvest domains and infer contact emails from public data, then cold-emailing them, is the part of the original brief with real legal exposure (unsolicited commercial email law varies by market and "add an unsubscribe link" doesn't resolve it) and the part most likely to get the sending domain blocklisted before it ever converts. The pull-model landing page (below) replaces it.
- **A landing page + hosted dashboard (Vercel/Supabase).** These need real accounts and a hosting decision that's yours to make, not mine — I can build the actual landing page markup and API contract on request, but I can't provision the hosting/database accounts myself.
- **PageSpeed Insights / SSL Labs API integration.** Both are real, legitimate tools built for exactly this use case, but both need an API key you provision, and SSL Labs specifically asks bulk/automated users to contact them first — wire these in once you have keys and have read their current usage terms; `checks.py` is written so a Google PageSpeed check would slot in as one more injectable check function.
- **Automatic sending of the email sequence.** The templates exist; nothing in this repo sends an email. A human (or a transactional email service you configure, like Resend/Mailgun) triggers each send, and should be able to stop the sequence the moment someone replies "stop" — the templates all include that line.
- **The $392 MRR / $4,000 setup-fee "24-day" projection from the original brief.** That number assumed a 500→100→10→20 conversion funnel with no stated basis. Real numbers depend on your actual landing page traffic and partner conversations — nothing here should be presented as a guaranteed outcome.

## Try it

```bash
cd products/sitedoctor
python -m unittest discover -s tests -v
python -m sitedoctor.cli audit example.com --monthly-visits 10000
```

The second command makes a real network request to example.com — that's expected; it's how the tool works. Only ever run it against a domain you have the right to audit.
