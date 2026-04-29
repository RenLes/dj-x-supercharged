"""Shared OAuth 2.0 PKCE helpers — loopback server, Vercel fallback, code exchange."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import http.server
import secrets
import socketserver
import threading
import urllib.parse
import webbrowser
from dataclasses import dataclass


@dataclass
class PKCEPair:
    verifier: str
    challenge: str

    @classmethod
    def generate(cls) -> PKCEPair:
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        return cls(verifier=verifier, challenge=challenge)


class _CodeHandler(http.server.BaseHTTPRequestHandler):
    server_version = "djx-oauth/0.1"
    captured: dict | None = None

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        type(self).captured = params
        body = (
            "<html><body style='font-family:system-ui;padding:2em'>"
            "<h2>You can close this tab.</h2>"
            "<p>dj-x-supercharged received your authorization code.</p>"
            "</body></html>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, format: str, *args) -> None:
        return


def capture_via_loopback(redirect_uri: str, auth_url: str, timeout: float = 180.0) -> dict | None:
    """Spin up a one-shot HTTP server that captures the OAuth callback.

    Returns the parsed query params or None if it timed out.
    """
    parsed = urllib.parse.urlparse(redirect_uri)
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        return None
    port = parsed.port or 80

    class Handler(_CodeHandler):
        captured: dict | None = None

    try:
        httpd = socketserver.TCPServer(("127.0.0.1", port), Handler)
    except OSError:
        return None

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    with contextlib.suppress(Exception):
        webbrowser.open(auth_url)

    deadline = threading.Event()
    waited = 0.0
    step = 0.5
    while waited < timeout and Handler.captured is None:
        deadline.wait(step)
        waited += step

    httpd.shutdown()
    httpd.server_close()
    return Handler.captured


def vercel_fallback(auth_url: str, fallback_url: str) -> str:
    """Print instructions for pasting the code from a hosted callback page."""
    print()
    print("=" * 64)
    print(" Open this URL in any browser:")
    print(" " + auth_url)
    print()
    print(" After granting access you'll land on:")
    print(" " + fallback_url)
    print(" Copy the 'code' it shows and paste below.")
    print("=" * 64)
    return input("code> ").strip()


def manual_paste(auth_url: str) -> str:
    print()
    print("Open this URL, authorize, then paste the FULL redirect URL you land on:")
    print(auth_url)
    pasted = input("redirect-url> ").strip()
    parsed = urllib.parse.urlparse(pasted)
    return dict(urllib.parse.parse_qsl(parsed.query)).get("code", "").strip()
