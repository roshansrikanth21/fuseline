"""Request guards for a local, unauthenticated API.

Fuseline holds sensitive case data and has no login, so the only thing standing between it
and any web page open in the examiner's browser is:

* a ``Host`` allow-list (defeats DNS-rebinding, where a hostile site resolves its own name
  to 127.0.0.1 to read the API as same-origin), and
* an ``Origin`` check on state-changing requests (a cross-site form or ``fetch`` can POST a
  multipart upload without any CORS pre-flight).
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
LOOPBACK_HOSTNAMES = {"127.0.0.1", "localhost", "::1"}
LOOPBACK_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:[0-9]+)?$"


def hostname(host_header: str) -> str:
    """Strip the port from a Host header, keeping bracketed IPv6 literals intact."""
    host = host_header.strip().lower()
    if host.startswith("["):
        end = host.find("]")
        return host[: end + 1] if end != -1 else host
    return host.split(":", 1)[0]


class LocalOnlyMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        allowed_hosts: Iterable[str],
        allowed_origins: Iterable[str] = (),
        allow_loopback_origins: bool = True,
    ) -> None:
        self.app = app
        self.allowed_hosts = {h.lower() for h in allowed_hosts}
        self.allowed_origins = {o.rstrip("/").lower() for o in allowed_origins}
        self.allow_loopback_origins = allow_loopback_origins

    def _host_ok(self, host_header: str) -> bool:
        return "*" in self.allowed_hosts or hostname(host_header) in self.allowed_hosts

    def _origin_ok(self, origin: str, host_header: str) -> bool:
        normalized = origin.rstrip("/").lower()
        if normalized in self.allowed_origins:
            return True
        parts = urlsplit(normalized)
        if parts.netloc and parts.netloc == host_header.strip().lower():
            return True
        # Exact hostname match: "http://localhost.evil.com" or "http://127.0.0.1.evil.com" must not pass.
        return (
            self.allow_loopback_origins
            and parts.scheme in {"http", "https"}
            and (parts.hostname or "") in LOOPBACK_HOSTNAMES
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        host_header = headers.get("host", "")
        if not self._host_ok(host_header):
            await JSONResponse({"detail": "Host not allowed"}, status_code=400)(scope, receive, send)
            return

        origin = headers.get("origin")
        if scope["method"] in UNSAFE_METHODS and origin and not self._origin_ok(origin, host_header):
            await JSONResponse({"detail": "Cross-origin request blocked"}, status_code=403)(scope, receive, send)
            return

        is_api = scope["path"].startswith("/api/")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                out = MutableHeaders(scope=message)
                out.setdefault("X-Content-Type-Options", "nosniff")
                out.setdefault("Referrer-Policy", "no-referrer")
                out.setdefault("X-Frame-Options", "DENY")
                if is_api:
                    out.setdefault("Cache-Control", "no-store")
            await send(message)

        await self.app(scope, receive, send_with_headers)
