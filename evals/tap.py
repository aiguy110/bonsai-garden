#!/usr/bin/env python3
"""Metering tap for OpenAI-compatible traffic: sits between a client (pi, mem0)
and turnstile, forwards every request unchanged except for routing, and appends
one JSONL record per request with llama-server's `timings` (prompt_n = tokens
actually prefilled, cache_n = tokens reused) and `usage`.

  tap.py --port 8091 --log run.jsonl --route agent=http://127.0.0.1:8080:KEYVAR \
         --route mem=http://127.0.0.1:8080:KEYVAR2

A client uses base URL http://127.0.0.1:8091/<role>/v1. The role prefix is
stripped; the request goes to that route's upstream with `Authorization: Bearer
$KEYVAR` (the key is read from the environment, so it never lands in a config
file). `--inject role='{"json": ...}'` deep-merges fields into that role's
request bodies (tap wins over the client), for things turnstile can't do yet.
"""
import argparse
import http.client
import http.server
import json
import os
import sys
import threading
import time
import urllib.parse

LOCK = threading.Lock()
HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade",
       "proxy-authorization", "proxy-authenticate", "host", "content-length"}


def merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            merge(dst[k], v)
        else:
            dst[k] = v
    return dst


class Tap(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    routes = {}
    injects = {}
    log_path = None
    tag = {}

    def log_message(self, *a):
        pass

    def _route(self):
        parts = self.path.lstrip("/").split("/", 1)
        role = parts[0]
        if role not in self.routes:
            return None
        return role, self.routes[role], "/" + (parts[1] if len(parts) > 1 else "")

    def do_GET(self):
        self._proxy(None)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self._proxy(self.rfile.read(n) if n else b"")

    def _proxy(self, body):
        route = self._route()
        if route is None:
            self.send_error(404, "unknown role prefix")
            return
        role, (base, key), path = route
        req = None
        if body:
            try:
                req = json.loads(body)
                if role in self.injects:
                    merge(req, json.loads(json.dumps(self.injects[role])))
                body = json.dumps(req).encode()
            except ValueError:
                req = None
        u = urllib.parse.urlsplit(base)
        conn = http.client.HTTPConnection(u.hostname, u.port, timeout=3600)
        hdrs = {k: v for k, v in self.headers.items() if k.lower() not in HOP | {"authorization"}}
        if key:
            hdrs["Authorization"] = f"Bearer {key}"
        if body is not None:
            hdrs["Content-Length"] = str(len(body))
        t0 = time.time()
        conn.request(self.command, u.path.rstrip("/") + path, body=body, headers=hdrs)
        resp = conn.getresponse()
        ttfb = time.time() - t0
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() not in HOP:
                self.send_header(k, v)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        timings = usage = None
        buf = pending = b""
        while True:
            chunk = resp.read1(65536)
            if not chunk:
                break
            self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
            self.wfile.flush()
            buf = (buf + chunk)[-1048576:]
            *lines, pending = (pending + chunk).split(b"\n")
            for line in lines:
                line = line.strip()
                if line.startswith(b"data: {"):
                    try:
                        d = json.loads(line[6:])
                    except ValueError:
                        continue
                    timings = d.get("timings") or timings
                    usage = d.get("usage") or usage
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()
        if timings is None and usage is None:
            try:
                d = json.loads(buf)
                timings, usage = d.get("timings"), d.get("usage")
            except ValueError:
                pass
        if self.log_path and req is not None:
            rec = {"ts": round(t0, 3), "role": role, "path": path, "status": resp.status,
                   "model": req.get("model"), "stream": bool(req.get("stream")),
                   "n_messages": len(req.get("messages") or []),
                   "wall_s": round(time.time() - t0, 3), "ttfb_s": round(ttfb, 3),
                   "queue_wait_ms": int(resp.getheader("X-Turnstile-Wait") or 0),
                   "timings": timings, "usage": usage, **self.tag}
            with LOCK, open(self.log_path, "a") as f:
                f.write(json.dumps(rec) + "\n")
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8091)
    ap.add_argument("--log", required=True)
    ap.add_argument("--route", action="append", default=[],
                    help="role=http://host:port[:ENVVAR_WITH_KEY]")
    ap.add_argument("--inject", action="append", default=[], help="role=JSON")
    ap.add_argument("--tag", action="append", default=[], help="k=v added to every record")
    a = ap.parse_args()
    for r in a.route:
        role, rest = r.split("=", 1)
        base, var = rest, None
        if rest.count(":") > 2:
            base, var = rest.rsplit(":", 1)
        Tap.routes[role] = (base, os.environ.get(var) if var else None)
    for i in a.inject:
        role, js = i.split("=", 1)
        Tap.injects[role] = json.loads(js)
    Tap.tag = dict(t.split("=", 1) for t in a.tag)
    Tap.log_path = a.log
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), Tap)
    print(f"tap on :{a.port} routes={list(Tap.routes)}", file=sys.stderr, flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
