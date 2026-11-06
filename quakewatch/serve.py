"""Live dashboard server — stdlib http.server only.

GET /            dashboard page (stats + table, rendered from a live fetch)
GET /api/quakes?period=day&min_mag=4.5   JSON endpoint, 60s in-memory cache
Any fetch failure returns honest error JSON / an error page, never fake data.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .analyze import compute_stats, filter_quakes
from .client import FetchError, fetch_feed
from .model import Quake
from .report import render_html

_CACHE_TTL = 60  # seconds


class _Cache:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.data: list[Quake] = []
        self.fetched_at = 0.0
        self.period = ""
        self.error: str | None = None

    def get(self, period: str) -> tuple[list[Quake], str | None]:
        now = time.time()
        with self.lock:
            if self.data and self.period == period and now - self.fetched_at < _CACHE_TTL:
                return self.data, None
        try:
            quakes = fetch_feed(period=period)
            error = None
        except FetchError as exc:
            with self.lock:
                if self.data and self.period == period:
                    # Serve the last good data, but flag it as stale.
                    return self.data, f"stale — live fetch failed: {exc}"
            return [], str(exc)
        with self.lock:
            self.data, self.fetched_at, self.period, self.error = quakes, now, period, None
        return quakes, error


CACHE = _Cache()


def _handler_factory() -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep stdout clean
            pass

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - stdlib name
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            period = query.get("period", ["day"])[0]
            if period not in ("hour", "day", "week", "month"):
                period = "day"
            if parsed.path == "/api/quakes":
                min_mag = query.get("min_mag", [None])[0]
                quakes, error = CACHE.get(period)
                if error and not quakes:
                    payload = {"error": error, "quakes": [], "stats": None}
                    self._send(502, json.dumps(payload).encode(), "application/json")
                    return
                filtered = filter_quakes(
                    quakes, min_mag=float(min_mag) if min_mag else None
                )
                payload = {
                    "stats": compute_stats(filtered),
                    "quakes": [q.to_dict() for q in filtered],
                    "stale": error,
                }
                self._send(200, json.dumps(payload).encode(), "application/json")
                return
            if parsed.path in ("/", "/index.html"):
                quakes, error = CACHE.get(period)
                if error and not quakes:
                    body = (
                        "<!DOCTYPE html><html><body style='background:#0A0A0B;color:#F5F5F4;"
                        "font-family:system-ui;padding:40px'><h1>QuakeWatch</h1>"
                        f"<p>Could not reach the USGS feed: {error}</p>"
                        "<p>Check your connection and refresh.</p></body></html>"
                    )
                    self._send(502, body.encode(), "text/html; charset=utf-8")
                    return
                page = render_html(quakes, compute_stats(quakes), period)
                if error:
                    page = page.replace(
                        "</h1>", f"</h1><p>⚠ Showing cached data — {error}</p>", 1
                    )
                self._send(200, page.encode(), "text/html; charset=utf-8")
                return
            self._send(404, b"Not found", "text/plain")

    return Handler


def serve(port: int = 8000) -> None:
    """Start the dashboard server (blocking)."""
    server = ThreadingHTTPServer(("127.0.0.1", port), _handler_factory())
    print(f"QuakeWatch dashboard: http://127.0.0.1:{port}/  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
