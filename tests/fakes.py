"""Fake only the network: a loopback HTTP server that serves recorded fixtures. Our own code is never mocked."""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class FakeServer:
    """Serves `routes` {path-prefix: (status, body)}; the longest matching prefix wins; else 404.

    `hits` records every requested path+query. `flaky` {prefix: n} makes the first n requests to it answer 503.
    """

    def __init__(self, routes: dict[str, tuple[int, bytes]], flaky: dict[str, int] | None = None):
        self.routes = dict(routes)
        self.flaky = dict(flaky or {})
        self.hits: list[str] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                outer.hits.append(self.path)
                key = self.path.split("?")[0]
                match = [p for p in outer.routes if self.path.startswith(p) or key.startswith(p)]
                status, body = (404, b"not found")
                if match:
                    best = max(match, key=len)
                    if outer.flaky.get(best, 0) > 0:
                        outer.flaky[best] -= 1
                        status, body = 503, b"try later"
                    else:
                        status, body = outer.routes[best]
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):  # silence
                pass

        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._srv.server_address[1]}"
        self._thread = threading.Thread(target=self._srv.serve_forever, daemon=True)

    def __enter__(self) -> "FakeServer":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._srv.shutdown()
        self._srv.server_close()
