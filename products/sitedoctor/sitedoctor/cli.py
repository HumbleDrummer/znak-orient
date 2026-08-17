"""SiteDoctor CLI: audit one domain you have a right to audit and write a report.

This deliberately does not accept a file of hundreds of domains to batch
scan. Auditing a site sends real requests to someone else's server and
some of the checks (SSL Labs-style deep scans, if you add one) are
rate-limited by their own terms of service against unattended bulk use.
Run it one domain at a time — your own sites, a client's site with their
knowledge, or a site whose owner requested the free audit themselves.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import checks
from .report import NeglectAssumptions, estimate_cost_of_neglect, render_report
from .scoring import ScoredAudit, score_audit


def run_audit(domain: str) -> ScoredAudit:
    url = f"https://{domain}"
    results = [
        checks.check_dns_resolves(domain),
        checks.check_ssl(domain),
        checks.check_response_profile(url),
        *checks.check_security_headers(url),
    ]
    return score_audit(domain, results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sitedoctor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit", help="Audit a single domain and write a Markdown report.")
    audit_parser.add_argument("domain", help="Bare domain, e.g. example.com (no scheme).")
    audit_parser.add_argument("--output", type=Path, default=None, help="Where to write the report (default: stdout).")
    audit_parser.add_argument("--monthly-visits", type=int, default=None, help="Enables the cost-of-neglect estimate.")
    audit_parser.add_argument("--conversion-rate", type=float, default=0.02)
    audit_parser.add_argument("--average-order-value", type=float, default=60.0)
    audit_parser.add_argument("--extra-load-seconds", type=float, default=2.0)

    args = parser.parse_args(argv)

    if args.command == "audit":
        audit = run_audit(args.domain)
        neglect = None
        if args.monthly_visits:
            neglect = estimate_cost_of_neglect(
                NeglectAssumptions(
                    extra_load_seconds=args.extra_load_seconds,
                    monthly_visits=args.monthly_visits,
                    baseline_conversion_rate=args.conversion_rate,
                    average_order_value=args.average_order_value,
                )
            )
        report = render_report(audit, neglect=neglect)
        if args.output:
            args.output.write_text(report, encoding="utf-8")
            print(f"wrote {args.output}")
        else:
            print(report)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
