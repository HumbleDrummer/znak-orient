"""Individual technical audit checks.

Every check accepts an injectable dependency (a fetch/resolve/get_cert
callable) so it can be unit tested without a real network call, and so a
CLI caller can swap in a rate-limited or cached fetcher when running
this against real sites. Nothing in this module scans anything on its
own; every call targets exactly the one hostname/URL the caller passes
in.
"""

from __future__ import annotations

import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

Severity = str  # "critical" | "high" | "medium" | "info"
Status = str  # "PASS" | "WARN" | "FAIL"


@dataclass(frozen=True)
class CheckResult:
    id: str
    label: str
    status: Status
    severity: Severity
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "severity": self.severity,
            "detail": self.detail,
        }


def _default_get_cert(hostname: str, port: int) -> dict[str, Any]:
    context = ssl.create_default_context()
    with socket.create_connection((hostname, port), timeout=8) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as tls:
            return tls.getpeercert()  # type: ignore[return-value]


def check_ssl(
    hostname: str,
    port: int = 443,
    *,
    now: datetime | None = None,
    get_cert: Callable[[str, int], dict[str, Any]] | None = None,
) -> CheckResult:
    """Certificate presence, expiry, and connection validity for hostname:port."""

    get_cert = get_cert or _default_get_cert
    now = now or datetime.now(timezone.utc)
    try:
        cert = get_cert(hostname, port)
    except Exception as exc:  # noqa: BLE001 - any TLS/connection failure is a FAIL finding
        return CheckResult(
            "ssl-cert-valid",
            "SSL certificate",
            "FAIL",
            "critical",
            f"Could not establish a valid TLS connection: {exc}",
        )
    not_after_raw = cert.get("notAfter")
    if not not_after_raw:
        return CheckResult(
            "ssl-cert-valid", "SSL certificate", "FAIL", "critical", "Certificate has no expiry field."
        )
    expires_at = datetime.strptime(not_after_raw, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    days_left = (expires_at - now).days
    if days_left < 0:
        return CheckResult(
            "ssl-cert-valid", "SSL certificate", "FAIL", "critical", f"Certificate expired {-days_left} day(s) ago."
        )
    if days_left <= 14:
        return CheckResult(
            "ssl-cert-valid", "SSL certificate", "WARN", "high", f"Certificate expires in {days_left} day(s)."
        )
    return CheckResult(
        "ssl-cert-valid", "SSL certificate", "PASS", "info", f"Valid, expires in {days_left} day(s)."
    )


def _default_fetch(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "SiteDoctor-Audit/1.0"})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - audited URL is caller-supplied
        body = response.read()
        elapsed = time.monotonic() - started
        return {
            "status_code": response.status,
            "headers": {key.lower(): value for key, value in response.headers.items()},
            "elapsed_seconds": elapsed,
            "content_length": len(body),
        }


def check_security_headers(
    url: str,
    *,
    fetch: Callable[[str], dict[str, Any]] | None = None,
) -> list[CheckResult]:
    """Presence of the headers that matter most for a customer-facing storefront."""

    fetch = fetch or _default_fetch
    required = {
        "strict-transport-security": ("high", "Forces HTTPS on return visits; missing it allows downgrade attacks."),
        "x-content-type-options": ("medium", "Missing it lets browsers guess content types, enabling some MIME sniffing attacks."),
        "content-security-policy": ("high", "Missing it removes a key defense against injected/malicious scripts."),
    }
    try:
        response = fetch(url)
    except urllib.error.URLError as exc:
        return [
            CheckResult(
                "security-headers-reachable", "Security headers", "FAIL", "critical", f"Could not fetch {url}: {exc}"
            )
        ]
    headers = response.get("headers", {})
    results = []
    for header_name, (severity, why) in required.items():
        if header_name in headers:
            results.append(
                CheckResult(f"header-{header_name}", header_name, "PASS", "info", "Present.")
            )
        else:
            results.append(
                CheckResult(f"header-{header_name}", header_name, "FAIL", severity, f"Missing. {why}")
            )
    return results


def check_response_profile(
    url: str,
    *,
    fetch: Callable[[str], dict[str, Any]] | None = None,
) -> CheckResult:
    """A cheap performance proxy: response time and payload size for the homepage.

    This is not a Lighthouse/Core Web Vitals substitute — it is a fast,
    dependency-free signal. For a full Core Web Vitals report, point the
    CLI's --pagespeed-key flag at Google's public PageSpeed Insights API
    instead (see cli.py); that is the tool actually built for this and
    it is safe to call against any public URL, since Google offers it
    specifically for that purpose.
    """

    fetch = fetch or _default_fetch
    try:
        response = fetch(url)
    except urllib.error.URLError as exc:
        return CheckResult("response-time", "Homepage response time", "FAIL", "critical", f"Could not fetch {url}: {exc}")
    elapsed = response.get("elapsed_seconds", 0.0)
    if elapsed > 4.0:
        severity, status = "critical", "FAIL"
    elif elapsed > 2.5:
        severity, status = "high", "WARN"
    else:
        severity, status = "info", "PASS"
    return CheckResult(
        "response-time",
        "Homepage response time",
        status,
        severity,
        f"{elapsed:.2f}s to first byte-complete response ({response.get('content_length', 0)} bytes).",
    )


def check_dns_resolves(
    hostname: str,
    *,
    resolve: Callable[[str], list[str]] | None = None,
) -> CheckResult:
    """Sanity check that the domain actually resolves before auditing it further."""

    resolve = resolve or (lambda host: socket.gethostbyname_ex(host)[2])
    try:
        addresses = resolve(hostname)
    except OSError as exc:
        return CheckResult("dns-resolves", "DNS resolution", "FAIL", "critical", f"Does not resolve: {exc}")
    if not addresses:
        return CheckResult("dns-resolves", "DNS resolution", "FAIL", "critical", "No A records returned.")
    return CheckResult("dns-resolves", "DNS resolution", "PASS", "info", f"Resolves to {', '.join(addresses)}.")
