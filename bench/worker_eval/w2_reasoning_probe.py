#!/usr/bin/env python3
"""W2 reasoning-budget probe (GPU). Three identical requests to bonsai-agent through the same
route run.py uses (sandbox-less tap -> turnstile agent role with the bench key; never :11435):
no budget, budget 256 + message, budget 1024 + message. max_tokens 4096.

Pass, per budgeted request: reasoning chars <= (budget + 64) * 4, the message text appears in
the reasoning, and the answer is non-empty. Field names default to the milestone's
(reasoning_budget_tokens / reasoning_budget_message); recon/llama.txt says whether the server
agrees, and --budget-field / --message-field override them.

  python3 bench/worker_eval/w2_reasoning_probe.py
"""
import argparse
import datetime
import http.client
import importlib.util
import json
import pathlib
import socket
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MESSAGE = "\n[Thinking budget reached. Stop thinking and act now with what you have.]\n"
PROMPT = ("Think very carefully and at length before answering. Count the ways to tile a 3x10 board with 1x2 dominoes. "
          "Work it out by a transfer-matrix recurrence, then check it by brute-force reasoning about the first column, "
          "then double-check the arithmetic a third way. Finally reply with one line starting 'ANSWER:'.")


def load_ev():
    spec = importlib.util.spec_from_file_location("garden_evals_run", ROOT / "evals/run.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run"] = mod
    spec.loader.exec_module(mod)
    return mod


def post(sock, path, body, timeout):
    class Conn(http.client.HTTPConnection):
        def connect(self):
            self.sock = socket.socket(socket.AF_UNIX)
            self.sock.settimeout(timeout)
            self.sock.connect(str(sock))
    c = Conn("localhost", timeout=timeout)
    t0 = time.time()
    c.request("POST", path, json.dumps(body), {"Content-Type": "application/json"})
    r = c.getresponse()
    raw = r.read()
    c.close()
    return r.status, raw, time.time() - t0


def split(resp):
    ch = (resp.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
    content = msg.get("content") or ""
    if not reasoning and "</think>" in content:
        reasoning, _, content = content.partition("</think>")
        reasoning = reasoning.replace("<think>", "")
    return reasoning, content, ch.get("finish_reason")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget-field", default="reasoning_budget_tokens")
    ap.add_argument("--message-field", default="reasoning_budget_message")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--out")
    a = ap.parse_args()
    out = pathlib.Path(a.out) if a.out else ROOT / "bench/results" / datetime.date.today().isoformat() / "worker-eval-w2/reasoning-probe"
    out.mkdir(parents=True, exist_ok=True)
    ev = load_ev()
    base = pathlib.Path(tempfile.mkdtemp(prefix="w2-probe-"))
    sock, taplog = base / "tap.sock", out / "tap.jsonl"
    taplog.write_text("")
    tap = ev.start_tap(taplog, {"run": "worker-eval-w2", "step": "reasoning-probe"}, ev.bench_key(), sock)
    variants = [("no-budget", None), ("budget-256", 256), ("budget-1024", 1024)]
    results = []
    try:
        for name, budget in variants:
            body = {"model": "bonsai-agent", "max_tokens": 4096, "stream": False,
                    "messages": [{"role": "user", "content": PROMPT}]}
            if budget:
                body[a.budget_field] = budget
                body[a.message_field] = MESSAGE
            status, raw, wall = post(sock, "/agent/v1/chat/completions", body, a.timeout)
            (out / f"{name}.response.json").write_bytes(raw)
            try:
                resp = json.loads(raw)
            except ValueError:
                resp = {}
            reasoning, content, finish = split(resp)
            r = {"name": name, "budget": budget, "request_fields": {k: v for k, v in body.items() if k != "messages"},
                 "status": status, "wall_s": round(wall, 1), "finish_reason": finish,
                 "reasoning_chars": len(reasoning), "answer_chars": len(content.strip()),
                 "completion_tokens": (resp.get("usage") or {}).get("completion_tokens"),
                 "message_in_reasoning": MESSAGE.strip() in reasoning, "answer_head": content.strip()[:200],
                 "reasoning_tail": reasoning[-300:]}
            if budget:
                r["limit_chars"] = (budget + 64) * 4
                r["pass"] = bool(status == 200 and r["reasoning_chars"] <= r["limit_chars"]
                                 and r["message_in_reasoning"] and r["answer_chars"] > 0)
            results.append(r)
            print(name, json.dumps({k: r[k] for k in ("status", "reasoning_chars", "answer_chars", "message_in_reasoning")}), flush=True)
    finally:
        ev.stop(tap)
    tapr = [json.loads(l) for l in taplog.read_text().splitlines() if l.strip()]
    for r, t in zip(results, tapr):
        r["tap_timings"] = t.get("timings")
        r["tap_wall_s"] = t.get("wall_s")
    budgeted = [r for r in results if r["budget"]]
    res = {"prompt": PROMPT, "message": MESSAGE, "requests": results, "tap_records": len(tapr),
           "rule": "per budgeted request: reasoning chars <= (budget+64)*4, message in reasoning, answer non-empty",
           "pass": all(r.get("pass") for r in budgeted) and len(budgeted) == 2}
    (out / "result.json").write_text(json.dumps(res, indent=2) + "\n")
    print("PASS" if res["pass"] else "FAIL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
