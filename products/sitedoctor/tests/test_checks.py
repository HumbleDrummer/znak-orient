import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sitedoctor import checks


class TestSslCheck(unittest.TestCase):
    def test_valid_certificate_passes(self):
        now = datetime(2026, 8, 1, tzinfo=timezone.utc)
        result = checks.check_ssl(
            "example.com", now=now, get_cert=lambda host, port: {"notAfter": "Dec 31 23:59:59 2026 GMT"}
        )
        self.assertEqual(result.status, "PASS")

    def test_expired_certificate_fails(self):
        now = datetime(2026, 8, 1, tzinfo=timezone.utc)
        result = checks.check_ssl(
            "example.com", now=now, get_cert=lambda host, port: {"notAfter": "Jan 1 00:00:00 2026 GMT"}
        )
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.severity, "critical")

    def test_expiring_soon_warns(self):
        now = datetime(2026, 8, 1, tzinfo=timezone.utc)
        result = checks.check_ssl(
            "example.com", now=now, get_cert=lambda host, port: {"notAfter": "Aug 10 00:00:00 2026 GMT"}
        )
        self.assertEqual(result.status, "WARN")

    def test_connection_failure_is_critical_fail(self):
        def raise_error(host, port):
            raise OSError("connection refused")

        result = checks.check_ssl("example.com", get_cert=raise_error)
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.severity, "critical")


class TestSecurityHeaders(unittest.TestCase):
    def test_all_present_passes(self):
        fetch = lambda url: {  # noqa: E731
            "status_code": 200,
            "headers": {
                "strict-transport-security": "max-age=63072000",
                "x-content-type-options": "nosniff",
                "content-security-policy": "default-src 'self'",
            },
        }
        results = checks.check_security_headers("https://example.com", fetch=fetch)
        self.assertTrue(all(item.status == "PASS" for item in results))

    def test_missing_headers_fail_with_expected_severity(self):
        fetch = lambda url: {"status_code": 200, "headers": {}}  # noqa: E731
        results = checks.check_security_headers("https://example.com", fetch=fetch)
        by_id = {item.id: item for item in results}
        self.assertEqual(by_id["header-strict-transport-security"].status, "FAIL")
        self.assertEqual(by_id["header-strict-transport-security"].severity, "high")


class TestResponseProfile(unittest.TestCase):
    def test_fast_response_passes(self):
        fetch = lambda url: {"elapsed_seconds": 0.8, "content_length": 50_000}  # noqa: E731
        result = checks.check_response_profile("https://example.com", fetch=fetch)
        self.assertEqual(result.status, "PASS")

    def test_slow_response_is_critical_fail(self):
        fetch = lambda url: {"elapsed_seconds": 5.1, "content_length": 50_000}  # noqa: E731
        result = checks.check_response_profile("https://example.com", fetch=fetch)
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.severity, "critical")


class TestDnsResolves(unittest.TestCase):
    def test_resolves_passes(self):
        result = checks.check_dns_resolves("example.com", resolve=lambda host: ["93.184.216.34"])
        self.assertEqual(result.status, "PASS")

    def test_no_records_fails(self):
        result = checks.check_dns_resolves("example.com", resolve=lambda host: [])
        self.assertEqual(result.status, "FAIL")


if __name__ == "__main__":
    unittest.main()
