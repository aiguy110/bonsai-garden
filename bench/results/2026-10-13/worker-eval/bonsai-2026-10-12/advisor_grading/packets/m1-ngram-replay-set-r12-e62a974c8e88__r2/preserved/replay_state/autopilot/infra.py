#!/usr/bin/env python3
"""Transactional changes to the live llama-swap config, with health checks and rollback.

  infra.py check                 health through turnstile (bonsai-agent, bench key); no lease
  infra.py baseline              under a GPU lease: measure the live config, save it as known-good
  infra.py apply ENTRY.yaml      splice a serving/-style entry into the live config, validate
                                 scope, then under a lease: back up, write, restart llama-swap,
                                 health-check; restore the previous config on failure
  infra.py rollback              under a lease: restore known-good, restart, health-check

Every command prints one JSON object on its last stdout line. Only the "bonsai-2-27b"
entry's server flags may change; the model, mmproj and port lines must stay identical.
The lease (turnstile_run.py) keeps every other GPU client out while llama-swap restarts,
and the health check talks to llama-swap directly on :11435 for the same reason.
"""
import concurrent.futures
import datetime
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
RUNTIME = HERE / ".runtime" / "infra"
LIVE = pathlib.Path("/etc/llama-swap/config.yaml")
SWAP = "http://127.0.0.1:11435"
TURNSTILE = "http://127.0.0.1:8080"
ENTRY = "bonsai-2-27b"
BENCH_RUNNER = pathlib.Path.home() / "Projects/local-llm-bench/turnstile_run.py"
CFG = json.loads((HERE / "config.json").read_text())
PINNED = ("--model", "--mmproj", "--port")
DECODE_PROMPTS = ["Write a Python function that parses an ISO-8601 duration string into seconds, with tests.",
                  "Explain, step by step, how a B-tree handles insertion when a node overflows."]


def log(rec):
    RUNTIME.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), **rec}
    with open(RUNTIME / "log.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def bench_key():
    return re.search(r'^KEY = "([^"]+)"', BENCH_RUNNER.read_text(), re.M).group(1)


def post(url, body, timeout, key=None):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, json.dumps(body).encode(), headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# ---- scope ----

def split_entry(text):
    """(text with the entry replaced by a marker, the entry's lines)."""
    m = re.search(rf'^  "?{re.escape(ENTRY)}"?:\s*\n((?:    .*\n|\s*\n)+)', text, re.M)
    if not m:
        raise ValueError(f"no {ENTRY} entry")
    return text[:m.start(1)] + "<ENTRY>\n" + text[m.end(1):], m.group(1)


def candidate_from_entry(entry_text):
    """Splice a serving/-style entry file ("bonsai-2-27b": at column 0, comments allowed)
    into the live config, so the full config (other models, local paths) never has to
    live in the repo."""
    lines = entry_text.splitlines()
    starts = [i for i, l in enumerate(lines) if re.match(rf'^"?{re.escape(ENTRY)}"?:\s*$', l)]
    if len(starts) != 1:
        raise ValueError(f"entry file must contain exactly one top-level {ENTRY}: key")
    body = [l for l in lines[starts[0] + 1:] if not l.startswith("#")]
    while body and not body[-1].strip():
        body.pop()
    if not body or any(l.strip() and not l.startswith("  ") for l in body):
        raise ValueError("entry body must be indented under the key")
    live = LIVE.read_text()
    rest, _ = split_entry(live)
    return rest.replace("<ENTRY>\n", "".join(f"  {l}\n" if l.strip() else "\n" for l in body) + "\n", 1)


def validate(candidate_text):
    """Reasons the candidate is out of scope (empty list = ok)."""
    import yaml
    errs = []
    try:
        yaml.safe_load(candidate_text)
    except yaml.YAMLError as e:
        return [f"not valid YAML: {e}"]
    live_rest, live_entry = split_entry(LIVE.read_text())
    try:
        cand_rest, cand_entry = split_entry(candidate_text)
    except ValueError as e:
        return [str(e)]
    if cand_rest != live_rest:
        errs.append(f"changes outside the {ENTRY} entry")
    pin = lambda e: [l.strip() for l in e.splitlines() if l.strip().startswith(PINNED)]
    if pin(cand_entry) != pin(live_entry):
        errs.append(f"changes a pinned line ({', '.join(PINNED)})")
    env = lambda e: e.split("cmd:")[0]
    if env(cand_entry) != env(live_entry):
        errs.append("changes the entry's env")
    if cand_entry == live_entry:
        errs.append("identical to the live entry")
    return errs


# ---- health ----

def chat(base, model, prompt, max_tokens, key=None, timeout=600, **extra):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
            "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}, **extra}
    return post(f"{base}/v1/chat/completions", body, timeout, key)


def answer_ok(r):
    return "42" in (r["choices"][0]["message"].get("content") or "")


def direct_health():
    """Correctness on one slot, then decode speed with both slots busy."""
    try:
        r = chat(SWAP, ENTRY, "What is 17 + 25? Reply with the number only.", 16)
        if not answer_ok(r):
            return {"ok": False, "why": f"wrong answer: {r['choices'][0]['message'].get('content')!r}"}
        single = chat(SWAP, ENTRY, DECODE_PROMPTS[0], 256, id_slot=0)["timings"]["predicted_per_second"]
        with concurrent.futures.ThreadPoolExecutor(2) as ex:
            futs = [ex.submit(chat, SWAP, ENTRY, DECODE_PROMPTS[i], 256, id_slot=i) for i in range(2)]
            conc = [f.result()["timings"]["predicted_per_second"] for f in futs]
    except (OSError, KeyError, ValueError) as e:
        return {"ok": False, "why": f"{type(e).__name__}: {e}"}
    return {"ok": True, "single_tok_s": round(single, 1), "conc_tok_s": [round(c, 1) for c in conc],
            "conc_mean_tok_s": round(sum(conc) / 2, 1)}


def turnstile_health(timeout=1800):
    """The path the worker uses. A long queue wait (interactive work) is 'busy', not broken."""
    try:
        r = chat(TURNSTILE, "bonsai-agent", "What is 17 + 25? Reply with the number only.", 64,
                 key=bench_key(), timeout=timeout)
        return {"ok": answer_ok(r), "why": None if answer_ok(r) else "wrong answer"}
    except TimeoutError:
        return {"ok": None, "why": "timeout (busy?)"}
    except urllib.error.HTTPError as e:
        return {"ok": False, "why": f"HTTP {e.code}: {e.read()[:300]!r}"}
    except OSError as e:
        return {"ok": False, "why": f"{type(e).__name__}: {e}"}


def restart_swap():
    p = subprocess.run(["sudo", "-n", "systemctl", "restart", "llama-swap"], capture_output=True, text=True)
    if p.returncode:
        return f"restart failed: {p.stderr.strip()}"
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{SWAP}/v1/models", timeout=5)
            return None
        except OSError:
            time.sleep(1)
    return "llama-swap did not come back on :11435"


# ---- locked operations (run inside a turnstile lease) ----

def locked_baseline():
    h = direct_health()
    if h["ok"]:
        RUNTIME.mkdir(parents=True, exist_ok=True)
        shutil.copy(LIVE, RUNTIME / "known-good.yaml")
        (RUNTIME / "baseline.json").write_text(json.dumps(h) + "\n")
    return log({"op": "baseline", **h})


def install(text):
    LIVE.write_text(text)
    err = restart_swap()
    return {"ok": False, "why": err} if err else direct_health()


def locked_apply(candidate):
    base = json.loads((RUNTIME / "baseline.json").read_text())
    floor = round(base["conc_mean_tok_s"] * CFG["infra"]["tok_s_floor_ratio"], 1)
    previous = LIVE.read_text()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy(LIVE, LIVE.with_name(f"config.yaml.bak.{stamp}"))
    h = install(pathlib.Path(candidate).read_text())
    if h["ok"] and h["conc_mean_tok_s"] < floor:
        h = {**h, "ok": False, "why": f"2-slot decode {h['conc_mean_tok_s']} tok/s below floor {floor}"}
    if h["ok"]:
        (RUNTIME / "pending-soak").write_text(json.dumps({"candidate": candidate, "backup": stamp,
                                                          "calls_left": CFG["infra"]["soak_worker_calls"]}))
        return log({"op": "apply", "candidate": candidate, "result": "applied", "floor": floor, **h})
    restored = install(previous)
    return log({"op": "apply", "candidate": candidate, "result": "rolled back", "floor": floor,
                "health": h, "after_restore": restored, "ok": False})


def locked_rollback():
    good = RUNTIME / "known-good.yaml"
    h = install(good.read_text())
    (RUNTIME / "pending-soak").unlink(missing_ok=True)
    return log({"op": "rollback", **h})


def under_lease(*args):
    out = RUNTIME / f"result-{time.time_ns()}.json"
    RUNTIME.mkdir(parents=True, exist_ok=True)
    p = subprocess.run([sys.executable, str(BENCH_RUNNER), "--", sys.executable, __file__, "_locked",
                        str(out), *args], capture_output=True, text=True, timeout=3600)
    if not out.exists():
        return log({"op": args[0], "ok": False, "why": f"lease run failed: {p.stderr[-1500:]}"})
    res = json.loads(out.read_text())
    out.unlink()
    return res


def main():
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "_locked":
        out, op, rest = args[0], args[1], args[2:]
        res = {"baseline": locked_baseline, "rollback": locked_rollback,
               "apply": lambda: locked_apply(rest[0])}[op]()
        pathlib.Path(out).write_text(json.dumps(res))
        return
    if cmd == "check":
        res = turnstile_health()
    elif cmd == "baseline":
        res = under_lease("baseline")
    elif cmd == "rollback":
        res = under_lease("rollback")
    elif cmd == "apply":
        src = str(pathlib.Path(args[0]).resolve())
        RUNTIME.mkdir(parents=True, exist_ok=True)
        cand = str(RUNTIME / f"candidate-{datetime.datetime.now():%Y%m%d-%H%M%S}.yaml")
        try:
            text = candidate_from_entry(pathlib.Path(src).read_text())
            pathlib.Path(cand).write_text(text)
            errs = validate(text)
        except (OSError, ValueError) as e:
            errs = [str(e)]
        if errs:
            res = log({"op": "apply", "candidate": cand, "ok": False, "result": "rejected", "why": errs})
        elif not (RUNTIME / "baseline.json").exists():
            res = {"ok": False, "why": "no baseline; run `infra.py baseline` first"}
        else:
            res = under_lease("apply", cand)
    else:
        sys.exit(__doc__)
    print(json.dumps(res))


if __name__ == "__main__":
    main()
