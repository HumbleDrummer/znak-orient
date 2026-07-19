from __future__ import annotations

import json
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from znak_orient.engine import OrientationError
from znak_orient.server import CSP, build_server


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "evidence-package.json"


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server = build_server("127.0.0.1", 0, DEMO)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def get(self, path):
        return urlopen(self.base_url + path, timeout=2)

    def raw_request(self, method, path, *, headers=None, body=None, server=None):
        target = server or self.server
        connection = HTTPConnection("127.0.0.1", target.server_port, timeout=2)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_index_and_static_assets_have_security_headers(self):
        with self.get("/") as response:
            body = response.read().decode("utf-8")
            self.assertIn("ZNAK ORIENT", body)
            self.assertIn('id="orientation-guide"', body)
            self.assertEqual(CSP, response.headers["Content-Security-Policy"])
            self.assertEqual("nosniff", response.headers["X-Content-Type-Options"])
            self.assertEqual("DENY", response.headers["X-Frame-Options"])
        with self.get("/app.js") as response:
            script = response.read().decode("utf-8")
            self.assertNotIn("innerHTML", script)
            self.assertIn("textContent", script)
            self.assertIn('setText("assistant-cue", checkpoint.primary_next_step.instruction)', script)
        with self.get("/styles.css") as response:
            styles = response.read().decode("utf-8")
            self.assertIn("prefers-reduced-motion", styles)
            self.assertIn(".guide-character, .guide-arm, .guide-signal", styles)

    def test_demo_api_returns_scoped_pass_and_blocked_project_position(self):
        with self.get("/api/demo") as response:
            result = json.loads(response.read().decode("utf-8"))
        self.assertEqual("PASS", result["run_receipt"]["status"])
        self.assertEqual("BLOCKED", result["checkpoint"]["voltage"])
        self.assertIn("not yet judge-ready", result["checkpoint"]["city_position"])

    def test_post_orient_processes_json_without_persistence(self):
        payload = DEMO.read_bytes()
        request = Request(
            self.base_url + "/api/orient",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            result = json.loads(response.read().decode("utf-8"))
        self.assertEqual("judge-safe-orientation-demo-001", result["package_id"])

    def test_wrong_media_type_and_unknown_path_fail_closed(self):
        request = Request(self.base_url + "/api/orient", data=b"{}", method="POST")
        with self.assertRaises(HTTPError) as wrong_type:
            urlopen(request, timeout=2)
        self.assertEqual(415, wrong_type.exception.code)
        with self.assertRaises(HTTPError) as not_found:
            self.get("/../../private.txt")
        self.assertEqual(404, not_found.exception.code)

    def test_non_loopback_binding_requires_explicit_override(self):
        with self.assertRaisesRegex(OrientationError, "non-loopback"):
            build_server("0.0.0.0", 0, DEMO)

    def test_non_loopback_host_and_origin_are_rejected_before_routing(self):
        loopback_host = f"127.0.0.1:{self.server.server_port}"
        cases = [
            ("GET", "/not-a-route", {"Host": "attacker.example"}, None),
            ("GET", "/api/demo", {"Host": "attacker.example@127.0.0.1"}, None),
            ("GET", "/api/demo", {"Host": loopback_host, "Origin": "https://attacker.example"}, None),
            ("GET", "/api/demo", {"Host": loopback_host, "Origin": "http://attacker.example@127.0.0.1"}, None),
            ("POST", "/api/orient", {"Host": loopback_host, "Origin": "null"}, b"{}"),
        ]
        for method, path, headers, body in cases:
            with self.subTest(method=method, path=path, headers=headers):
                status, payload = self.raw_request(method, path, headers=headers, body=body)
                self.assertEqual(403, status)
                self.assertEqual({"error": "LOOPBACK_REQUEST_REQUIRED"}, json.loads(payload))

    def test_loopback_host_and_origin_remain_allowed(self):
        status, payload = self.raw_request(
            "GET",
            "/api/demo",
            headers={
                "Host": f"localhost:{self.server.server_port}",
                "Origin": f"http://[::1]:{self.server.server_port}",
            },
        )
        self.assertEqual(200, status)
        self.assertEqual("judge-safe-orientation-demo-001", json.loads(payload)["package_id"])

    def test_explicit_non_loopback_override_preserves_request_behavior(self):
        override_server = build_server("127.0.0.1", 0, DEMO, allow_non_loopback=True)
        override_thread = threading.Thread(target=override_server.serve_forever, daemon=True)
        override_thread.start()
        try:
            status, payload = self.raw_request(
                "GET",
                "/api/demo",
                headers={"Host": "attacker.example", "Origin": "https://attacker.example"},
                server=override_server,
            )
            self.assertEqual(200, status)
            self.assertEqual("judge-safe-orientation-demo-001", json.loads(payload)["package_id"])
        finally:
            override_server.shutdown()
            override_server.server_close()
            override_thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
