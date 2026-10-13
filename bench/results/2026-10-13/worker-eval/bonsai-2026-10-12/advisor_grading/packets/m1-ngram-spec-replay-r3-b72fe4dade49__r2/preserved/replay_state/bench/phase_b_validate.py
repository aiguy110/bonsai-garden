#!/usr/bin/env python3
"""End-to-end checks for turnstile co-admission + virtual models against the live
stack (turnstile :8080 -> llama-swap :11435 -> 2-slot bonsai-2-27b).

  set -a; . ~/Projects/gpu-turnstile/.keys.env; set +a
  python3 bench/phase_b_validate.py | tee bench/results/<date>/phase_b_validate.txt

Needs PI_KEY and BONSAI_GARDEN_MEM_KEY in the environment. Sends real requests at
priority 40, so run it when nobody else needs the GPU.
"""
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request

TS = "http://127.0.0.1:8080"
LS = "http://127.0.0.1:11435"
AGENT_KEY = os.environ["PI_KEY"]
MEM_KEY = os.environ["BONSAI_GARDEN_MEM_KEY"]
PROMPT = "Explain, step by step, how a B-tree handles insertion when a node overflows."


def chat(model, key, max_tokens=256, content=PROMPT, extra=None):
    body = {"model": model, "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens, "temperature": 0, "top_k": 1, **(extra or {})}
    req = urllib.request.Request(f"{TS}/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            out = json.load(r)
            out["_wait_ms"] = int(r.headers.get("X-Turnstile-Wait") or 0)
    except urllib.error.HTTPError as e:
        out = {"_status": e.code, "_body": json.loads(e.read() or b"{}")}
    out["_t0"], out["_t1"] = t0, time.time()
    return out


def concurrently(*calls):
    res = [None] * len(calls)

    def run(i, c):
        res[i] = c()
    ts = [threading.Thread(target=run, args=(i, c)) for i, c in enumerate(calls)]
    for t in ts:
        t.start()
        time.sleep(0.05)
    for t in ts:
        t.join()
    return res


def slots():
    with urllib.request.urlopen(f"{LS}/upstream/bonsai-2-27b/slots") as r:
        return {s["id"]: s["id_task"] for s in json.load(r)}


def journal_since(since):
    return subprocess.run(["journalctl", "--user", "-u", "turnstile", "--since", since,
                           "--no-pager", "-o", "cat"], capture_output=True, text=True).stdout


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""), flush=True)


def main():
    chat("bonsai-agent", AGENT_KEY, 8, "hi")  # warm the model
    since = time.strftime("%Y-%m-%d %H:%M:%S")
    time.sleep(1)

    # 1. agent + mem together: joined, both at the 2-slot rate.
    s0 = slots()
    a, m = concurrently(lambda: chat("bonsai-agent", AGENT_KEY),
                        lambda: chat("bonsai-mem", MEM_KEY))
    s1 = slots()
    tps = [round(x["timings"]["predicted_per_second"], 1) for x in (a, m)]
    overlap = min(a["_t1"], m["_t1"]) - max(a["_t0"], m["_t0"])
    log = journal_since(since)
    check("agent+mem co-admitted", "msg=joined" in log and m["_wait_ms"] < 500,
          f"mem waited {m['_wait_ms']} ms, overlap {overlap:.1f}s")
    check("both decode at the 2-slot rate (~45 tok/s)", all(35 < t < 52 for t in tps), f"tok/s {tps}")
    check("alias logged", "alias=bonsai-mem" in log and "alias=bonsai-agent" in log)

    # 2. id_slot pinning and thinking off for mem.
    check("agent pinned to slot 0, mem to slot 1", s1[0] != s0[0] and s1[1] != s0[1], f"{s0} -> {s1}")
    msg = m["choices"][0]["message"]
    check("bonsai-mem returns no reasoning", not msg.get("reasoning_content"),
          f"reasoning chars {len(msg.get('reasoning_content') or '')}")
    am = a["choices"][0]["message"]
    check("bonsai-agent still reasons", bool(am.get("reasoning_content")),
          f"reasoning chars {len(am.get('reasoning_content') or '')}")

    # 3a. over maxCtx -> 400 without queueing.
    r = chat("bonsai-mem", MEM_KEY, 64, "x " * 20000)
    check("over-maxCtx request gets 400 context_length_exceeded",
          r.get("_status") == 400 and r["_body"]["error"]["code"] == "context_length_exceeded",
          json.dumps(r.get("_body"))[:160])

    # 3b. budgets that don't fit together run one after the other.
    since = time.strftime("%Y-%m-%d %H:%M:%S")
    time.sleep(1)
    big = "word " * 30000  # ~50k estimated tokens each; two exceed the 98304 pool
    b1, b2 = concurrently(lambda: chat("bonsai-agent", AGENT_KEY, 16, big),
                          lambda: chat("bonsai-2-27b", AGENT_KEY, 16, big))
    log = journal_since(since)
    check("over-budget pair serializes", "deferring: context budget" in log and b2["_t1"] > b1["_t1"],
          f"second waited {b2.get('_wait_ms')} ms")

    # 4. a lease arriving mid-stream waits for both LLM holders.
    since = time.strftime("%Y-%m-%d %H:%M:%S")
    time.sleep(1)
    lease = {}

    def take_lease():
        time.sleep(1.0)
        req = urllib.request.Request(f"{TS}/lease", data=b"{}", method="POST",
                                     headers={"Authorization": f"Bearer {MEM_KEY}"})
        with urllib.request.urlopen(req) as r:
            lid = json.load(r)["lease_id"]
        t0 = time.time()
        while True:
            with urllib.request.urlopen(f"{TS}/lease/{lid}") as r:
                st = json.load(r)
            if st["status"] == "granted":
                break
            time.sleep(0.2)
        lease["granted_at"] = time.time()
        lease["waited"] = lease["granted_at"] - t0
        urllib.request.urlopen(urllib.request.Request(f"{TS}/lease/{lid}/release", method="POST"))
    a, m, _ = concurrently(lambda: chat("bonsai-agent", AGENT_KEY),
                           lambda: chat("bonsai-mem", MEM_KEY), take_lease)
    check("lease waits for both LLM holders", lease["granted_at"] >= max(a["_t1"], m["_t1"]) - 0.5,
          f"lease waited {lease['waited']:.1f}s")
    # The lease evicted the model; reload it so the stack is left warm.
    chat("bonsai-agent", AGENT_KEY, 8, "hi")


if __name__ == "__main__":
    main()
