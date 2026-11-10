import contextlib
import http.client
import http.server
import io
import json
import os
import tempfile
import threading
import unittest
from unittest import mock

from ahflip import config, db
from ahflip.web import server


class Server(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(os.remove, path)
        p = mock.patch.object(config, "DB_PATH", path)
        p.start()
        self.addCleanup(p.stop)  # cleanups run in reverse: server stops before the patch and the file go
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        t = threading.Thread(target=self.srv.serve_forever, daemon=True)
        t.start()
        self.addCleanup(t.join, 5)
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.port = self.srv.server_address[1]

    def req(self, method, path, body=None, headers=None, host="localhost"):
        h = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(h.close)
        h.putrequest(method, path, skip_host=True)
        if host is not None:
            h.putheader("Host", f"{host}:{self.port}")
        for k, v in (headers or {}).items():
            h.putheader(k, v)
        if body is not None:
            h.putheader("Content-Length", str(len(body)))
        h.endheaders(body)
        r = h.getresponse()
        data = r.read()
        return r.status, r.getheader("Content-Type"), data

    def test_pages(self):
        index = (config.STATIC / "index.html").read_bytes()
        for path in ("/", "/market", "/ledger?x=1"):
            self.assertEqual(self.req("GET", path), (200, "text/html; charset=utf-8", index))

    def test_static(self):
        code, ctype, data = self.req("GET", "/static/js/main.js")
        self.assertEqual((code, ctype), (200, "text/javascript; charset=utf-8"))
        self.assertEqual(data, (config.STATIC / "js" / "main.js").read_bytes())
        self.assertEqual(self.req("GET", "/static/style.css")[:2], (200, "text/css; charset=utf-8"))
        for path in ("/static/../server.py", "/static/../../config.py", "/static/x.txt", "/static/nope.js", "/static/js"):
            self.assertEqual(self.req("GET", path)[0], 404, path)

    def test_host(self):
        self.assertEqual(self.req("GET", "/", host="127.0.0.1")[0], 200)
        self.assertEqual(self.req("GET", "/", host="evil.com")[:1], (403,))
        self.assertEqual(json.loads(self.req("GET", "/", host=None)[2]), {"error": "bad host"})

    def test_api(self):
        self.assertEqual(self.req("GET", "/api/nope")[0], 404)
        self.assertEqual(self.req("PUT", "/api/settings")[0], 501)  # no do_PUT
        self.assertEqual(self.req("POST", "/")[0], 404)
        code, ctype, data = self.req("GET", "/api/settings")
        self.assertEqual((code, ctype, json.loads(data)["cut"]), (200, "application/json", 0.05))
        hdr = {"Content-Type": "application/json; charset=utf-8"}
        code, _, data = self.req("POST", "/api/settings", b'{"cut": 0.1}', hdr)
        self.assertEqual((code, json.loads(data)["cut"]), (200, 0.1))
        self.assertEqual(self.req("POST", "/api/settings", b"", hdr)[0], 200)  # empty body = {}
        self.assertEqual(self.req("POST", "/api/settings", None, hdr)[0], 200)  # no Content-Length
        self.assertEqual(self.req("POST", "/api/settings", b"{}", {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.req("POST", "/api/settings", b"{}")[0], 415)  # no Content-Type
        code, _, data = self.req("POST", "/api/settings", b'{"bogus": 1}', hdr)
        self.assertEqual((code, json.loads(data)), (400, {"error": "unknown setting bogus"}))
        self.assertEqual(self.req("POST", "/api/settings", b"not json", hdr)[0], 400)
        self.assertEqual(self.req("GET", "/api/history")[0], 400)  # KeyError: item

    def test_query_args_and_500(self):
        got = {}

        def echo(c, a):
            got.update(a)
            return a

        def boom(c, a):
            raise RuntimeError("kaput")

        with mock.patch.dict(server.ROUTES, {("GET", "/api/echo"): echo, ("GET", "/api/boom"): boom}):
            code, _, data = self.req("GET", "/api/echo?item=5&q=wool+cloth")
            self.assertEqual((code, json.loads(data)), (200, {"item": "5", "q": "wool cloth"}))
            code, _, data = self.req("GET", "/api/boom")
            self.assertEqual((code, json.loads(data)), (500, {"error": "kaput"}))


class Serve(unittest.TestCase):
    def test_serve(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(os.remove, path)
        out = io.StringIO()
        with (
            mock.patch.object(config, "DB_PATH", path),
            mock.patch.object(server.threading, "Thread") as thread,
            mock.patch.object(server.http.server, "ThreadingHTTPServer") as srv,
            mock.patch.object(server.time, "time", side_effect=[1000, 2000]),
            contextlib.redirect_stdout(out),
        ):
            srv.return_value.serve_forever.side_effect = KeyboardInterrupt
            server.serve(8123)
            with db.session() as c:
                self.assertEqual(db.meta(c, "retried"), 1000)  # first start: retry a day from now
            server.serve()
            with db.session() as c:
                self.assertEqual(db.meta(c, "retried"), 1000)  # kept on later starts
        thread.assert_called_with(target=server.jobs.scheduler, daemon=True)
        self.assertEqual(thread.return_value.start.call_count, 2)
        srv.assert_any_call(("127.0.0.1", 8123), server.Handler)
        srv.assert_called_with(("127.0.0.1", 8000), server.Handler)
        self.assertIn("http://localhost:8123", out.getvalue())


if __name__ == "__main__":
    unittest.main()
