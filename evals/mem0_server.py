#!/usr/bin/env python3
"""A minimal mem0 REST server for evals: Python `mem0.Memory` behind the endpoints
pi-memory-mem0's self-hosted mode calls, on a Unix socket.

  <mem0 venv>/bin/python -I mem0_server.py --unix SOCK --config config.json

Upstream's server (mem0 repo, server/main.py) wraps the same `Memory` calls but
also needs Postgres, auth, and a request-log DB. This keeps only the memory
endpoints, with the same request and response shapes, so each eval sequence can
run its own instance with its config and its store in the run dir. The mem0
version is whatever the venv has (an arm pins it, possibly to a fork's git ref).

  POST   /memories        {messages, user_id?, agent_id?, run_id?, metadata?, infer?, ...}
  GET    /memories        ?user_id=&agent_id=&run_id=&top_k=
  GET    /memories/{id}
  DELETE /memories/{id}
  POST   /search          {query, filters?, user_id?, agent_id?, run_id?, top_k?, threshold?}
  GET    /health
  GET    /_dump           every stored memory payload (for the run's memories.json)
"""
import argparse
import http.server
import json
import os
import socketserver
import sys
import threading
import traceback
import urllib.parse

from mem0 import Memory

LOCK = threading.Lock()  # local Qdrant and the history SQLite aren't safe to share across threads
ENTITY = ("user_id", "agent_id", "run_id")
ADD_KEYS = ENTITY + ("metadata", "expiration_date", "infer", "memory_type", "prompt")
SEARCH_KEYS = ("top_k", "threshold", "explain", "show_expired")


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    memory = None

    def address_string(self):
        return "unix"

    def log_message(self, fmt, *a):
        print(f"{self.command} {self.path} {fmt % a}", file=sys.stderr, flush=True)

    def _send(self, status, obj):
        body = json.dumps(obj, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n)) if n else {}

    def _call(self, fn):
        try:
            with LOCK:
                self._send(200, fn())
        except ValueError as e:
            # Same mapping as upstream: "not found" is a 404, other validation a 400.
            self._send(404 if "not found" in str(e).lower() else 400, {"detail": str(e)})
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"detail": f"{type(e).__name__}: {e}"})

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        m = self.memory
        if u.path == "/health":
            self._send(200, {"status": "ok"})
        elif u.path == "/_dump":
            self._call(lambda: dump(m))
        elif u.path == "/memories":
            filters = {k: q[k] for k in ENTITY if k in q}
            if not filters:
                self._send(400, {"detail": "one of user_id, agent_id, run_id is required"})
                return
            params = {"filters": filters}
            if "top_k" in q:
                params["top_k"] = int(q["top_k"])
            self._call(lambda: m.get_all(**params))
        elif u.path.startswith("/memories/"):
            mid = urllib.parse.unquote(u.path.split("/", 2)[2])
            self._call(lambda: m.get(mid))
        else:
            self._send(404, {"detail": "not found"})

    def do_POST(self):
        try:
            req = self._body()
        except ValueError:
            self._send(400, {"detail": "invalid JSON"})
            return
        m = self.memory
        if self.path == "/memories":
            if not any(req.get(k) for k in ENTITY):
                self._send(400, {"detail": "one of user_id, agent_id, run_id is required"})
                return
            params = {k: req[k] for k in ADD_KEYS if req.get(k) is not None}
            self._call(lambda: m.add(messages=req.get("messages") or [], **params))
        elif self.path == "/search":
            # Top-level entity ids are deprecated upstream but still folded into filters.
            filters = {**{k: req[k] for k in ENTITY if req.get(k)}, **(req.get("filters") or {})}
            params = {k: req[k] for k in SEARCH_KEYS if req.get(k) is not None}
            self._call(lambda: m.search(query=req.get("query", ""), filters=filters, **params))
        else:
            self._send(404, {"detail": "not found"})

    def do_DELETE(self):
        if not self.path.startswith("/memories/"):
            self._send(404, {"detail": "not found"})
            return
        mid = urllib.parse.unquote(self.path.split("/", 2)[2])

        def delete():
            self.memory.delete(memory_id=mid)
            return {"message": "Memory deleted successfully"}
        self._call(delete)


def dump(m):
    rows = m.vector_store.list(top_k=100000)
    # Qdrant's list returns ([points], next_offset); other stores return a plain list.
    if isinstance(rows, tuple):
        rows = rows[0]
    if rows and isinstance(rows[0], list):
        rows = rows[0]
    return [{"id": str(getattr(r, "id", "")), **(getattr(r, "payload", None) or {})} for r in rows]


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unix", required=True)
    ap.add_argument("--config", required=True, help="JSON for Memory.from_config")
    a = ap.parse_args()
    Handler.memory = Memory.from_config(json.loads(open(a.config).read()))
    if os.path.exists(a.unix):
        os.unlink(a.unix)
    srv = Server(a.unix, Handler)
    print(f"mem0 server on {a.unix}", file=sys.stderr, flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
