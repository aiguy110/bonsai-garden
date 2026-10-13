#!/usr/bin/env python3
"""M1 replay probe: recorded agent / mem0 requests against a private llama-server.

  turnstile_run.py -- python3 bench/spec_replay.py OUTDIR LABEL SAMPLING [extra server args...]

SAMPLING is greedy|prod. The server cmd is the one in
serving/llama-swap.bonsai-2-27b.yaml (port 8089, LLAMA_ATTN_ROT_DISABLE=1) plus the
extra args. A LABEL ending in '-nommproj' drops --mmproj/--no-mmproj-offload.
If a config with --spec-type refuses to run with mmproj (server exits, or the log
says speculation is not supported by the context), it is rerun automatically as
LABEL-nommproj and the reason goes to notes.txt.

Phases, each on a FRESH server (the n-gram pool persists across requests):
  single-agent  agent.jsonl in order, slot 0, slot 1 idle
  single-mem    mem.jsonl in order, slot 1, slot 0 idle
  dual-agent    agent fg on slot 0, mem loop bg on slot 1 until fg is done
  dual-mem      mem fg on slot 1, agent loop bg on slot 0 until fg is done

max_tokens per request = max(recorded predicted_n, floor) (floor 768 agent, 1024
mem), identical in every arm, so output lengths and tok/s are comparable.
tool_call_json_valid: every tool_call's arguments parse as JSON; for mem requests
without tool calls the content must parse as JSON; otherwise True.
"""
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8089
REPLAY = os.path.join(ROOT, "bench/.replay/m1")
YAML = os.path.join(ROOT, "serving/llama-swap.bonsai-2-27b.yaml")
FLOOR = {"agent": 768, "mem": 1024}
SLOT = {"agent": 0, "mem": 1}
REFUSAL = ["not supported by this context", "unsupported batch.has_embd",
           "speculative decoding is disabled", "speculation is disabled",
           "speculative decoding not supported"]
NOTABLE = REFUSAL + ["will use checkpoints", "restore checkpoint",
                     "speculative", "spec type", "ngram"]


def load(role):
    with open(f"{REPLAY}/{role}.jsonl") as f:
        return [json.loads(l) for l in f if l.strip()]


def server_cmd(extra, nommproj):
    txt = open(YAML).read()
    block = re.search(r"cmd: \|\n(.*?)\n\s*ttl:", txt, re.S).group(1)
    toks = shlex.split(block.replace("${PORT}", str(PORT)).replace("\\\n", " "))
    toks = [os.path.expanduser(t) for t in toks]
    if nommproj:
        out, skip = [], False
        for t in toks:
            if skip:
                skip = False
                continue
            if t == "--mmproj":
                skip = True
                continue
            if t == "--no-mmproj-offload":
                continue
            out.append(t)
        toks = out
    return toks + list(extra)


def post(body):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3600) as r:
        return json.load(r)


def make_body(item, sampling, slot):
    b = dict(item["body"])
    role = item["role"]
    b["max_tokens"] = max(item["meta"]["predicted_n"], FLOOR[role])
    b["stream"] = False
    b["id_slot"] = slot
    b["seed"] = 0
    if sampling == "greedy":
        b["temperature"] = 0
        b["top_k"] = 1
    elif role == "agent":
        b.update(temperature=1.0, top_p=0.95, top_k=20)
    else:
        b["temperature"] = 0.2
    return b


def json_ok(s):
    try:
        json.loads(s)
        return True
    except Exception:
        return False


class Run:
    def __init__(self, outdir, label, sampling, extra, nommproj):
        self.dir = f"{outdir}/{label}-{sampling}"
        self.label, self.sampling, self.extra, self.nommproj = label, sampling, extra, nommproj
        os.makedirs(self.dir, exist_ok=True)
        os.makedirs(f"{REPLAY}/outputs", exist_ok=True)
        self.outputs = open(f"{REPLAY}/outputs/{label}-{sampling}.jsonl", "w")
        self.reqs = open(f"{self.dir}/requests.jsonl", "w")
        self.vram = open(f"{self.dir}/vram.txt", "w")
        self.notes = open(f"{self.dir}/notes.txt", "w")
        self.lock = threading.Lock()
        self.rows = []

    def note(self, s):
        self.notes.write(s + "\n")
        self.notes.flush()

    def start(self, phase):
        logp = f"{self.dir}/server_{phase}.log"
        log = open(logp, "w")
        env = dict(os.environ, LLAMA_ATTN_ROT_DISABLE="1")
        cmd = server_cmd(self.extra, self.nommproj)
        if phase == "single-agent":
            self.note("cmd: " + " ".join(cmd))
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2).read()
            raise SystemExit(f"stale server already answering on :{PORT}")
        except OSError:
            pass
        self.srv = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)
        for _ in range(600):
            if self.srv.poll() is not None:
                break
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2).read()
                return logp, True
            except Exception:
                time.sleep(1)
        return logp, False

    def stop(self):
        if self.srv.poll() is None:
            self.srv.terminate()
            try:
                self.srv.wait(60)
            except subprocess.TimeoutExpired:
                self.srv.kill()
        self.srv.wait()

    def log_hits(self, logp, phase):
        hits = []
        try:
            for ln in open(logp, errors="replace"):
                if any(p in ln for p in NOTABLE):
                    hits.append(ln.rstrip())
        except OSError:
            pass
        for h in hits[:12]:
            self.note(f"[{phase}] log: {h[:300]}")
        return [h for h in hits if any(p in h for p in REFUSAL)]

    def one(self, phase, item, fgbg, first_flag):
        role = item["role"]
        slot = SLOT[role]
        body = make_body(item, self.sampling, slot)
        row = dict(phase=phase, role=role, fg_bg=fgbg, id=item["id"], slot=slot,
                   max_tokens=body["max_tokens"])
        try:
            r = post(body)
            t = r.get("timings", {})
            m = r["choices"][0]["message"]
            tcs = m.get("tool_calls") or []
            if tcs:
                valid = all(json_ok(tc["function"]["arguments"]) for tc in tcs)
            elif role == "mem":
                valid = json_ok(m.get("content") or "")
            else:
                valid = True
            blob = (m.get("reasoning_content") or "") + (m.get("content") or "") + \
                json.dumps(tcs, sort_keys=True)
            row.update(prompt_n=t.get("prompt_n"), cache_n=t.get("cache_n"),
                       predicted_n=t.get("predicted_n"), predicted_ms=t.get("predicted_ms"),
                       predicted_per_second=t.get("predicted_per_second"),
                       draft_n=t.get("draft_n", 0), draft_n_accepted=t.get("draft_n_accepted", 0),
                       finish_reason=r["choices"][0].get("finish_reason"),
                       tool_call_json_valid=valid,
                       out_sha256=hashlib.sha256(blob.encode()).hexdigest())
            out = dict(phase=phase, id=item["id"], fg_bg=fgbg, message=m)
        except Exception as e:  # keep going; the row records the failure
            row["error"] = repr(e)[:300]
            out = dict(phase=phase, id=item["id"], fg_bg=fgbg, error=row["error"])
        row["t_end"] = time.time()
        with self.lock:
            self.rows.append(row)
            self.reqs.write(json.dumps(row) + "\n")
            self.reqs.flush()
            self.outputs.write(json.dumps(out) + "\n")
            self.outputs.flush()
        if first_flag:
            self.vram.write(f"== {phase} (after first fg request)\n")
            self.vram.write(subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv"],
                capture_output=True, text=True).stdout)
            self.vram.flush()

    def phase(self, name, fg_role, bg_role):
        logp, ok = self.start(name)
        try:
            if not ok:
                self.note(f"[{name}] server did not become healthy (exit={self.srv.poll()})")
                if self.log_hits(logp, name) and self.extra and not self.nommproj:
                    self.note(f"[{name}] speculation refused at startup")
                    return "refused"
                return "failed"
            refusals = self.log_hits(logp, name)
            if refusals and any(a.startswith("--spec-type") for a in self.extra) \
                    and not self.nommproj:
                self.note(f"[{name}] speculation refused: {refusals[0]}")
                return "refused"
            fg = load(fg_role)
            bg = load(bg_role) if bg_role else []
            stop = threading.Event()

            def loop():
                i = 0
                while not stop.is_set():
                    self.one(name, bg[i % len(bg)], "bg", False)
                    i += 1

            th = threading.Thread(target=loop, daemon=True) if bg else None
            t0 = time.time()
            if th:
                th.start()
            for i, item in enumerate(fg):
                self.one(name, item, "fg", i == 0)
            t_fg = time.time()
            self.note(f"[{name}] fg wall_s={t_fg - t0:.1f}")
            stop.set()
            if th:
                th.join()
            self.note(f"[{name}] window t0={t0:.3f} t_fg_end={t_fg:.3f} t_join_end={time.time():.3f}")
            if self.srv.poll() is not None:
                self.note(f"[{name}] server died during phase (exit={self.srv.poll()})")
                self.log_hits(logp, name)
                return "failed"
            self.log_hits(logp, name)
            return "ok"
        finally:
            self.stop()

    def run(self):
        for name, fg, bg in [("single-agent", "agent", None), ("single-mem", "mem", None),
                             ("dual-agent", "agent", "mem"), ("dual-mem", "mem", "agent")]:
            st = self.phase(name, fg, bg)
            if st != "ok":
                return st, name
        spec = any(a.startswith("--spec-type") for a in self.extra)
        fgs = [r for r in self.rows if r["fg_bg"] == "fg"]
        if spec and all(not (r.get("draft_n") or 0) for r in fgs):
            self.note("draft_n is 0 for every foreground request; see log lines above")
        self.note("done")
        return "ok", None


def main():
    outdir, label, sampling = sys.argv[1:4]
    extra = sys.argv[4:]
    assert sampling in ("greedy", "prod")
    nommproj = label.endswith("-nommproj")
    run = Run(outdir, label, sampling, extra, nommproj)
    st, ph = run.run()
    if st == "refused" and not nommproj and any(a.startswith("--spec-type") for a in extra):
        run.note(f"mmproj config {st} in phase {ph}; rerunning as {label}-nommproj")
        run = Run(outdir, f"{label}-nommproj", sampling, extra, True)
        st, ph = run.run()
    print("result", st, ph, flush=True)
    sys.exit(0 if st == "ok" else 1)


if __name__ == "__main__":
    main()
