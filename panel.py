"""
A tiny local web server for the tuning panel (panel.html).

It only listens on 127.0.0.1. The browser talks to it with JSON; the server
never touches the simulation itself, it just queues requests for the main
loop (inbox) and serves the latest snapshot the main loop published (state).
"""

from __future__ import annotations

import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HTML = Path(__file__).with_name("panel.html")
TOKEN_HEADER = "X-Desktop-Universe"   # a custom header: other websites cannot send it to us


class Panel:
    def __init__(self, port: int = 8765):
        self.inbox: queue.Queue = queue.Queue()
        self._state = {}
        self._lock = threading.Lock()
        panel = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code, body: bytes, ctype="application/json"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
                elif self.path == "/api/state":
                    with panel._lock:
                        body = json.dumps(panel._state, ensure_ascii=False).encode()
                    self._send(200, body)
                else:
                    self._send(404, b'{"error": "not found"}')

            def do_POST(self):
                if self.headers.get(TOKEN_HEADER) != "1":
                    return self._send(403, b'{"error": "forbidden"}')
                try:
                    n = int(self.headers.get("Content-Length", 0))
                    data = json.loads(self.rfile.read(n) or b"{}")
                except (ValueError, json.JSONDecodeError):
                    return self._send(400, b'{"error": "bad json"}')
                if self.path == "/api/preset":
                    panel.inbox.put(("preset", data))
                elif self.path == "/api/cmd":
                    panel.inbox.put((data.get("cmd"), data))
                else:
                    return self._send(404, b'{"error": "not found"}')
                self._send(200, b'{"ok": true}')

        self.server = None
        for p in range(port, port + 10):           # step aside if the port is taken
            try:
                self.server = ThreadingHTTPServer(("127.0.0.1", p), Handler)
                break
            except OSError:
                continue
        if self.server is None:
            raise OSError(f"no free port in {port}-{port + 9}")
        self.port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}/"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def publish(self, state: dict):
        with self._lock:
            self._state = state

    def messages(self):
        while True:
            try:
                yield self.inbox.get_nowait()
            except queue.Empty:
                return

    def close(self):
        self.server.shutdown()
