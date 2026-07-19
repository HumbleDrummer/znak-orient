"""Loopback-only HTTP surface for the ZNAK ORIENT local interface."""

from __future__ import annotations

import ipaddress
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .engine import OrientationError, orient

WEB_ROOT = Path(__file__).resolve().parent / "web"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_REQUEST_BYTES = 1_000_000
STATIC_FILES = {
    "/": (WEB_ROOT / "index.html", "text/html; charset=utf-8"),
    "/index.html": (WEB_ROOT / "index.html", "text/html; charset=utf-8"),
    "/styles.css": (WEB_ROOT / "styles.css", "text/css; charset=utf-8"),
    "/app.js": (WEB_ROOT / "app.js", "text/javascript; charset=utf-8"),
    "/design-concept.svg": (PROJECT_ROOT / "docs" / "design-concept.svg", "image/svg+xml"),
}
CSP = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _host_header_is_loopback(value: str) -> bool:
    if not value or value != value.strip() or any(character.isspace() for character in value):
        return False
    if any(character in value for character in "/\\@?#"):
        return False
    if value.startswith("["):
        closing = value.find("]")
        if closing < 0:
            return False
        host = value[1:closing]
        remainder = value[closing + 1 :]
        if remainder and (not remainder.startswith(":") or not remainder[1:].isdigit()):
            return False
        port_text = remainder[1:] if remainder else ""
    else:
        if value.count(":") > 1:
            return False
        host, separator, port_text = value.partition(":")
        if separator and not port_text.isdigit():
            return False
    if port_text and (len(port_text) > 5 or not (0 <= int(port_text) <= 65535)):
        return False
    return bool(host) and _is_loopback(host)


def _origin_is_loopback(value: str) -> bool:
    if not value or value != value.strip() or any(character.isspace() for character in value):
        return False
    try:
        origin = urlsplit(value)
        origin.port
    except ValueError:
        return False
    return (
        origin.scheme.lower() in {"http", "https"}
        and bool(origin.hostname)
        and _is_loopback(origin.hostname)
        and origin.username is None
        and origin.password is None
        and not origin.path
        and not origin.query
        and not origin.fragment
    )


def _handler(demo_path: Path, *, allow_non_loopback: bool):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ZnakOrientLocal/0.3C"
        sys_version = ""

        def log_message(self, format: str, *args: Any) -> None:
            # Avoid echoing imported content, request bodies, or query values to logs.
            return

        def _headers(self, status: HTTPStatus, content_type: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()

        def _send_bytes(self, status: HTTPStatus, content_type: str, payload: bytes) -> None:
            self._headers(status, content_type, len(payload))
            self.wfile.write(payload)

        def _send_json(self, status: HTTPStatus, value: Any) -> None:
            payload = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self._send_bytes(status, "application/json; charset=utf-8", payload)

        def _allow_request(self) -> bool:
            if allow_non_loopback:
                return True
            host_values = self.headers.get_all("Host", [])
            origin_values = self.headers.get_all("Origin", [])
            allowed = (
                len(host_values) == 1
                and _host_header_is_loopback(host_values[0])
                and len(origin_values) <= 1
                and (not origin_values or _origin_is_loopback(origin_values[0]))
            )
            if not allowed:
                if self.command == "POST":
                    try:
                        pending = int(self.headers.get("Content-Length", "0"))
                    except ValueError:
                        pending = 0
                    if 0 < pending <= MAX_REQUEST_BYTES:
                        self.rfile.read(pending)
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "LOOPBACK_REQUEST_REQUIRED"})
            return allowed

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            if not self._allow_request():
                return
            path = urlsplit(self.path).path
            if path == "/api/demo":
                try:
                    package = json.loads(demo_path.read_text(encoding="utf-8"))
                    self._send_json(HTTPStatus.OK, orient(package))
                except (OSError, json.JSONDecodeError, OrientationError) as exc:
                    self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "DEMO_PROCESSING_FAILED", "detail": str(exc)})
                return
            static = STATIC_FILES.get(path)
            if static is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"})
                return
            asset_path, content_type = static
            try:
                payload = asset_path.read_bytes()
            except OSError:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "STATIC_ASSET_MISSING"})
                return
            self._send_bytes(HTTPStatus.OK, content_type, payload)

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            if not self._allow_request():
                return
            path = urlsplit(self.path).path
            if path != "/api/orient":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"})
                return
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "JSON_REQUIRED"})
                return
            try:
                length = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                length = -1
            if length < 0 or length > MAX_REQUEST_BYTES:
                self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "REQUEST_SIZE_INVALID"})
                return
            try:
                package = json.loads(self.rfile.read(length).decode("utf-8"))
                self._send_json(HTTPStatus.OK, orient(package))
            except (UnicodeDecodeError, json.JSONDecodeError, OrientationError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "PACKAGE_REJECTED", "detail": str(exc)})

    return Handler


def build_server(host: str, port: int, demo_path: Path, *, allow_non_loopback: bool = False) -> ThreadingHTTPServer:
    if not allow_non_loopback and not _is_loopback(host):
        raise OrientationError("[SERVER-LOOPBACK] non-loopback binding requires --allow-non-loopback")
    if not isinstance(port, int) or isinstance(port, bool) or not (0 <= port <= 65535):
        raise OrientationError("[SERVER-PORT] port must be between 0 and 65535")
    return ThreadingHTTPServer((host, port), _handler(demo_path.resolve(), allow_non_loopback=allow_non_loopback))


def serve(host: str, port: int, demo_path: Path, *, allow_non_loopback: bool = False) -> None:
    server = build_server(host, port, demo_path, allow_non_loopback=allow_non_loopback)
    bound_host, bound_port = server.server_address[:2]
    print(f"ZNAK_ORIENT_LOCAL http://{bound_host}:{bound_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
