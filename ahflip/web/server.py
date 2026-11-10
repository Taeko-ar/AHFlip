"""HTTP server: static page files from static/, JSON API from routes.ROUTES. Localhost only."""

import contextlib
import http.server
import json
import threading
import time
import urllib.parse

from .. import config, db
from . import jobs
from .routes import ROUTES

STATIC_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}
# Page URLs, all served index.html. Keep in sync with PAGES in static/js/main.js; /deals, /search are old links.
PAGES = {"/", "/market", "/deals", "/search", "/watch", "/ledger", "/settings", "/setup"}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def static(self, name):
        # files are read per request, so page edits show on browser refresh
        root = config.STATIC.resolve()
        f = (root / name).resolve()
        if not f.is_relative_to(root) or f.suffix not in STATIC_TYPES or not f.is_file():  # no path traversal
            return self.send(404, {"error": "not found"})
        self.send(200, f.read_bytes(), STATIC_TYPES[f.suffix])

    def handle_req(self, method):
        # Only this PC's browser: blocks DNS rebinding and cross-site form posts.
        if (self.headers.get("Host") or "").rsplit(":", 1)[0] not in ("localhost", "127.0.0.1"):
            return self.send(403, {"error": "bad host"})
        u = urllib.parse.urlsplit(self.path)
        if method == "GET" and u.path in PAGES:  # each page has its own URL; static/js/main.js renders it
            return self.static("index.html")
        if method == "GET" and u.path.startswith("/static/"):
            return self.static(u.path[len("/static/") :])
        route = ROUTES.get((method, u.path))
        if not route:
            return self.send(404, {"error": "not found"})
        if method == "POST" and (self.headers.get("Content-Type") or "").split(";")[0] != "application/json":
            return self.send(415, {"error": "send JSON"})
        with db.session() as c:
            try:
                if method == "POST":
                    arg = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                else:
                    arg = dict(urllib.parse.parse_qsl(u.query))
                self.send(200, route(c, arg))
            except (ValueError, KeyError, TypeError) as e:
                self.send(400, {"error": str(e)})
            except Exception as e:
                self.send(500, {"error": str(e)})

    def do_GET(self):
        self.handle_req("GET")

    def do_POST(self):
        self.handle_req("POST")


def serve(port=8000):
    with db.session() as c:
        if db.meta(c, "retried") is None:
            db.set_meta(c, "retried", int(time.time()))  # first retry a day from now, not at startup
    threading.Thread(target=jobs.scheduler, daemon=True).start()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"ahflip on http://localhost:{port}  (Ctrl+C to stop)", flush=True)
    with contextlib.suppress(KeyboardInterrupt):
        srv.serve_forever()
