#!/usr/bin/env python3
"""Replay cloud-worker autopilot rounds with a local worker arm (W1).

  python3 bench/worker_eval/run.py ARM [--cases PATH] [--repeat N] [--out DIR]
                                       [--budget-min 145] [--only CASE_ID ...]

Per (arm, case, repeat): a fresh checkout of the case's start commit under /tmp (a new
repo holding only that commit's history, outside this worktree), a fresh pi agent dir,
and pi in the eval sandbox (no network) reaching live `bonsai-agent` through the tap
with the bench key. Results go to DIR/results.jsonl (one line per finished attempt)
and DIR/<case_id>/r<repeat>/ (manifest, events, final text, request, workspace diff).
A rerun skips attempts that already have a record, and never starts a case whose
session timeout does not fit in the remaining --budget-min.

autopilot.py and evals/run.py are imported read-only, lazily, so the parsing and
checking code here works (and is tested) without pi, docker or a GPU.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARMS = HERE / "arms"
KINDS = ("run", "infra", "continue", "done", "stuck")
MAX_TIMEOUT_MIN = 180
DESCRIPTION = re.compile(r"(?m)^(You are the research worker for bonsai-garden, running as )(.+?)(\. The project)$")
CONTEXT_OVERFLOW = re.compile(r"context_length_exceeded|exceeds? the (available )?context|context (length|window|size)"
                              r"|maximum context|n_ctx|prompt is too long|too many tokens|exceed_context_size", re.I)
OUTPUT_LIMIT = re.compile(r"output limit|max output|stopReason.?length", re.I)
RATE_LIMIT = re.compile(r"rate.?limit|usage limit|429|quota", re.I)


# ---- small helpers ----

def sha256_file(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def last_json(text):
    """The last JSON object in a reply: a fenced json block, else any trailing object
    (the same rule as autopilot.py's last_json)."""
    for block in reversed(re.findall(r"```json\s*(.*?)```", text or "", re.S)):
        try:
            obj = json.loads(block)
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
    dec = json.JSONDecoder()
    text = text or ""
    for i in reversed([i for i, c in enumerate(text) if c == "{"]):
        try:
            obj, _ = dec.raw_decode(text[i:])
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
    return None


# ---- arms ----

_TYPES = {"string": str, "integer": int, "number": (int, float), "array": list, "object": dict}


def load_arm(name_or_path):
    p = pathlib.Path(name_or_path)
    if not p.suffix:
        p = ARMS / f"{name_or_path}.json"
    arm = json.loads(p.read_text())
    errs = validate_arm(arm, json.loads((ARMS / "schema.json").read_text()))
    if arm.get("name") != p.stem:
        errs.append(f"name {arm.get('name')!r} must equal the file name {p.stem!r}")
    if arm.get("worker_memory") is not None:
        errs.append("worker_memory other than null is not implemented (W3)")
    if errs:
        raise ValueError(f"{p}: " + "; ".join(errs))
    return arm, sha256_file(p)


def validate_arm(arm, schema):
    """The subset of the schema the arm format uses: required, additionalProperties,
    type, enum, minimum/exclusiveMinimum, pattern."""
    errs = []
    props = schema["properties"]
    for k in schema["required"]:
        if k not in arm:
            errs.append(f"missing {k}")
    for k, v in arm.items():
        if k not in props:
            errs.append(f"unknown field {k}")
            continue
        s = props[k]
        if "enum" in s:
            if v not in s["enum"]:
                errs.append(f"{k} must be one of {s['enum']}")
            continue
        t = s.get("type")
        if t and (not isinstance(v, _TYPES[t]) or (isinstance(v, bool) and t != "boolean")):
            errs.append(f"{k} must be {t}")
            continue
        if "pattern" in s and not re.search(s["pattern"], v):
            errs.append(f"{k} does not match {s['pattern']}")
        if "minimum" in s and v < s["minimum"]:
            errs.append(f"{k} below {s['minimum']}")
        if "exclusiveMinimum" in s and v <= s["exclusiveMinimum"]:
            errs.append(f"{k} must be above {s['exclusiveMinimum']}")
        if t == "array" and not all(isinstance(x, str) for x in v):
            errs.append(f"{k} must hold strings")
    return errs


# ---- cases and prompt ----

def load_cases(path):
    cases = [json.loads(line) for line in pathlib.Path(path).read_text().splitlines() if line.strip()]
    ids = [c["case_id"] for c in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate case_id in " + str(path))
    return cases


def render_prompt(case, arm):
    """The case's prompt with the replayed model's description in the first line. The
    line must name exactly the description the case recorded, once, and nothing else
    may change."""
    prompt = case["prompt"]
    old, new = case["worker_description_to"], arm["worker_description"]
    found = DESCRIPTION.findall(prompt)
    if len(found) != 1 or found[0][1] != old:
        raise ValueError(f"{case['case_id']}: prompt names {[f[1] for f in found]}, expected exactly {old!r}")
    out = DESCRIPTION.sub(lambda m: m.group(1) + new + m.group(3), prompt, count=1)
    again = DESCRIPTION.findall(out)
    if len(again) != 1 or again[0][1] != new:
        raise ValueError(f"{case['case_id']}: replay-model line not rendered")
    if out.replace(new, old, 1) != prompt:
        raise ValueError(f"{case['case_id']}: prompt changed outside the model line")
    return out


# ---- events ----

def _text(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return c
    return "".join(x.get("text", "") for x in c or [] if isinstance(x, dict) and x.get("type") == "text")


def parse_events(path):
    """Counts and errors from pi's --mode json event stream."""
    r = {"turns": 0, "tool_calls": 0, "tools": Counter(), "tool_errors": Counter(),
         "compaction_start": 0, "compaction_end": 0, "stop_reasons": [], "errors": [],
         "final": "", "events": 0, "bad_lines": 0}
    names = {}
    for line in pathlib.Path(path).read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except ValueError:
            r["bad_lines"] += 1
            continue
        if not isinstance(e, dict):
            r["bad_lines"] += 1
            continue
        r["events"] += 1
        t = e.get("type")
        if t == "turn_end":
            r["turns"] += 1
        elif t == "tool_execution_start":
            r["tool_calls"] += 1
            r["tools"][e.get("toolName", "?")] += 1
            names[e.get("toolCallId")] = e.get("toolName", "?")
        elif t == "tool_execution_end":
            res = e.get("result") if isinstance(e.get("result"), dict) else {}
            if e.get("isError") or res.get("isError"):
                r["tool_errors"][e.get("toolName") or names.get(e.get("toolCallId"), "?")] += 1
        elif t == "compaction_start":
            r["compaction_start"] += 1
        elif t == "compaction_end":
            r["compaction_end"] += 1
        elif t == "message_end" and (e.get("message") or {}).get("role") == "assistant":
            m = e["message"]
            r["stop_reasons"].append(m.get("stopReason"))
            if _text(m).strip():
                r["final"] = _text(m)
            if m.get("stopReason") == "error" or m.get("errorMessage"):
                r["errors"].append(m.get("errorMessage") or "error")
    r["tools"], r["tool_errors"] = dict(r["tools"]), dict(r["tool_errors"])
    r["last_stop"] = r["stop_reasons"][-1] if r["stop_reasons"] else None
    return r


def classify(events, timed_out, exit_code=None):
    """Explicit failure-mode flags. Output limit: a reply that stopped on `length`."""
    msgs = [str(m) for m in events["errors"]]
    return {
        "timeout": bool(timed_out),
        "context_overflow": any(CONTEXT_OVERFLOW.search(m) for m in msgs),
        "output_limit": "length" in events["stop_reasons"] or any(OUTPUT_LIMIT.search(m) for m in msgs),
        "rate_limit": any(RATE_LIMIT.search(m) for m in msgs),
        "pi_exit_nonzero": exit_code not in (None, 0) and not timed_out,
    }


def flag_triggers(events):
    """What set each message-based flag, so a surprising flag can be audited."""
    out = {}
    for name, rx in (("context_overflow", CONTEXT_OVERFLOW), ("output_limit", OUTPUT_LIMIT), ("rate_limit", RATE_LIMIT)):
        hits = [str(m)[:300] for m in events["errors"] if rx.search(str(m))]
        if hits:
            out[name] = hits
    if "length" in events["stop_reasons"]:
        out.setdefault("output_limit", []).append("stopReason=length")
    return out


# ---- requests ----

def detect_request(request_file, final_text):
    """request.json (the submit_request tool) first, else the last JSON object in the
    final reply, else none. Returns (source, body)."""
    request_file = pathlib.Path(request_file)
    if request_file.exists():
        try:
            body = json.loads(request_file.read_text())
            if isinstance(body, dict):
                return "tool", body
        except ValueError:
            pass
    body = last_json(final_text)
    return ("json_fallback", body) if body else ("none", None)


def _inside(path, base):
    try:
        rel = pathlib.Path(path).resolve().relative_to(pathlib.Path(base).resolve())
    except ValueError:
        return False
    return str(rel) != "."


def check_run_command(cmd, repo):
    """The orchestrator's check (autopilot.py check_run_command) against a given repo."""
    try:
        argv = shlex.split(cmd)
    except ValueError as e:
        return None, f"unparseable: {e}"
    if len(argv) < 2 or argv[0] not in ("python3", "bash"):
        return None, "must start with python3 or bash"
    repo = pathlib.Path(repo)
    script = (repo / argv[1]).resolve()
    if not (str(script).startswith(str(repo / "bench") + "/") or str(script).startswith(str(repo / "evals") + "/")):
        return None, "script must be under bench/ or evals/"
    if not script.is_file():
        return None, f"{argv[1]} does not exist"
    if any(c in cmd for c in "|;&><`$"):
        return None, "no shell operators"
    return argv, None


def validate_request(req, repo, orchestrator_check=None):
    """Errors for a request: submit_request.ts's field and path rules, then the
    orchestrator's (check_run_command for run; the serving/candidates rule for infra).
    `orchestrator_check(cmd, repo) -> (argv, err)` defaults to the local copy."""
    check = orchestrator_check or check_run_command
    errs = []
    if not isinstance(req, dict):
        return ["request is not a JSON object"]
    repo = pathlib.Path(repo)
    kind = req.get("request")
    if kind not in KINDS:
        return [f'"request" must be one of {", ".join(KINDS)}']
    if not isinstance(req.get("report"), str) or not req["report"].strip():
        errs.append('"report" is required')

    def need(k):
        if not isinstance(req.get(k), str) or not req[k].strip():
            errs.append(f'"{k}" is required for a {kind} request')

    if kind == "run":
        need("command")
        need("why")
        if not isinstance(req.get("gpu"), bool):
            errs.append('"gpu" is required for a run request (true or false)')
        t = req.get("timeout_min")
        if t is not None and not (isinstance(t, int) and not isinstance(t, bool) and 1 <= t <= MAX_TIMEOUT_MIN):
            errs.append(f'"timeout_min" must be a whole number from 1 to {MAX_TIMEOUT_MIN}')
        cmd = req["command"].strip() if isinstance(req.get("command"), str) else ""
        if cmd:
            if re.search(r"[|;&><`$]", cmd):
                errs.append("command: no shell operators (| ; & > < ` $); pass plain arguments")
            argv = cmd.split()
            if len(argv) < 2 or argv[0] not in ("python3", "bash"):
                errs.append("command must be `python3 <script> ARGS` or `bash <script> ARGS`")
            else:
                script = repo / argv[1]
                if not (_inside(script, repo / "bench") or _inside(script, repo / "evals")):
                    errs.append(f"script {argv[1]} must be under bench/ or evals/")
                elif not script.is_file():
                    errs.append(f"script {argv[1]} does not exist; write it first")
            _, err = check(req["command"], repo)
            if err:
                errs.append(f"orchestrator: {err}")
    elif kind == "infra":
        need("entry")
        need("why")
        if isinstance(req.get("entry"), str) and req["entry"].strip():
            entry = repo / req["entry"]
            if not _inside(entry, repo / "serving" / "candidates"):
                errs.append("entry must be a file under serving/candidates/")
            elif not entry.is_file():
                errs.append(f"entry {req['entry']} does not exist; write it first")
    elif kind == "continue":
        need("note")
    elif kind == "done":
        need("summary")
    elif kind == "stuck":
        need("why")
    return errs


# ---- attempts: records, resume, budget ----

def attempt_key(arm_name, case_id, repeat):
    return (arm_name, case_id, repeat)


def load_records(results):
    results = pathlib.Path(results)
    recs = []
    if results.exists():
        for line in results.read_text().splitlines():
            if line.strip():
                try:
                    recs.append(json.loads(line))
                except ValueError:
                    pass  # a torn last line: that attempt reruns
    return recs


def completed(recs):
    return {attempt_key(r["arm"], r["case_id"], r["repeat"]) for r in recs if r.get("complete")}


def append_record(results, rec):
    results = pathlib.Path(results)
    results.parent.mkdir(parents=True, exist_ok=True)
    with open(results, "a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def schedule(arm_name, cases, repeats):
    """Repeat-major, so a partial chunk covers every case once before any twice."""
    return [(c, rep) for rep in range(1, repeats + 1) for c in cases]


def run_all(arm, cases, repeats, results, budget_min, attempt, clock=time.monotonic, log=print):
    """Run the attempts not yet recorded. `attempt(case, repeat) -> record`. Stops at the
    first attempt whose session timeout no longer fits in the budget (cases are not
    reordered to find a shorter fit, so each attempt's position is predictable)."""
    done = completed(load_records(results))
    t0 = clock()
    todo = [(c, r) for c, r in schedule(arm["name"], cases, repeats)
            if attempt_key(arm["name"], c["case_id"], r) not in done]
    stats = {"skipped": len(cases) * repeats - len(todo), "ran": 0, "remaining": len(todo)}
    fails = 0
    for case, rep in todo:
        left = budget_min * 60 - (clock() - t0)
        if left < arm["session_timeout_min"] * 60:
            log(f"budget: {left / 60:.1f} min left, a session may take {arm['session_timeout_min']}; stopping")
            break
        rec = attempt(case, rep)
        if rec is None:  # infrastructure failure: no record, so a rerun retries it
            fails += 1
            if fails >= 3:
                log("3 attempts in a row failed to run; stopping")
                break
            continue
        fails = 0
        append_record(results, rec)
        stats["ran"] += 1
        stats["remaining"] -= 1
    return stats


def build_record(arm, case, repeat, req_source, req, errs, events, flags, wall_s, extra=None):
    cloud_kind = (case.get("request") or {}).get("request")
    kind = req.get("request") if isinstance(req, dict) else None
    rec = {
        "complete": True, "arm": arm["name"], "case_id": case["case_id"], "repeat": repeat,
        "item": case.get("item"), "advisor_verdict": case.get("advisor_verdict"),
        "request_source": req_source, "request": req, "validation_errors": errs,
        "valid_request": req is not None and not errs,
        "cloud_kind": cloud_kind, "replay_kind": kind,
        "kind_match": kind is not None and kind == cloud_kind,
        "wall_s": round(wall_s, 1), "turns": events["turns"], "tool_calls": events["tool_calls"],
        "tools": events["tools"], "tool_errors": events["tool_errors"],
        "compaction_start": events["compaction_start"], "compaction_end": events["compaction_end"],
        "stop_reasons": events["stop_reasons"], "last_stop": events["last_stop"],
        "errors": events["errors"], **flags,
    }
    rec.update(extra or {})
    return rec


# ---- host side: imports, manifest, sandbox ----

def load_module(name, path, alias=None):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    if alias:
        sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


def load_ev():
    """evals/run.py (sandbox, tap, pinning), registered as `run` as autopilot.py expects."""
    if "run" in sys.modules and hasattr(sys.modules["run"], "start_tap"):
        return sys.modules["run"]
    return load_module("garden_evals_run", ROOT / "evals" / "run.py", alias="run")


def resolve_venv(ev):
    """Mount the venv the live worker mounted: the main checkout's, when this worktree has none
    (autopilot/autopilot.py:44-47,372). Never create it: docker -v would leave a root-owned dir."""
    main_venv = pathlib.Path.home() / "Projects" / "bonsai-garden" / "evals" / ".cache" / "venv-sandbox"
    if not os.access(pathlib.Path(ev.VENV) / "bin" / "python", os.X_OK):
        ev.VENV = main_venv
    if not (os.access(pathlib.Path(ev.VENV) / "bin" / "python", os.X_OK)
            and (pathlib.Path(ev.VENV) / "bin" / "pytest").exists()):
        sys.exit(f"sandbox venv {ev.VENV} has no bin/python and bin/pytest; refusing to launch")


def orchestrator_check():
    """autopilot.py's own check_run_command, pointed at a repo through its WT global;
    falls back to the local copy if autopilot can't be imported."""
    try:
        load_ev()
        ap = load_module("garden_autopilot", ROOT / "autopilot" / "autopilot.py")
    except Exception as e:  # noqa: BLE001
        print(f"warning: autopilot.py not importable ({e}); using the local run-command check", file=sys.stderr)
        return check_run_command

    def check(cmd, repo):
        ap.WT = pathlib.Path(repo)
        return ap.check_run_command(cmd)
    return check


def model_registration(arm):
    entry = json.loads((ROOT / "agent" / "models.bonsai-agent.json").read_text())
    entry["id"] = arm["model"].split("/", 1)[1]
    entry["maxTokens"] = arm["max_output_tokens"]
    entry["contextWindow"] = arm["context_window"]
    return entry


def agent_files(arm, ev_tap):
    """settings.json and models.json for a worker session (autopilot.py
    worker_agent_dir() for provider garden, memory off)."""
    provider, model = arm["model"].split("/", 1)
    settings = {"defaultProvider": provider, "defaultModel": model, "defaultThinkingLevel": arm["thinking"],
                "compaction": {"reserveTokens": arm["compaction_reserve_tokens"]}}
    models = {"providers": {provider: {
        "baseUrl": f"{ev_tap}/agent/v1", "api": "openai-completions", "apiKey": "tap",
        "compat": {"supportsStore": False, "supportsDeveloperRole": False,
                   "supportsReasoningEffort": False, "maxTokensField": "max_tokens"},
        "models": [model_registration(arm)]}}}
    return settings, models


def make_agent_dir(arm, base, ev_tap):
    agent = pathlib.Path(base) / "agent"
    (agent / "extensions").mkdir(parents=True)
    settings, models = agent_files(arm, ev_tap)
    (agent / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
    (agent / "models.json").write_text(json.dumps(models, indent=2) + "\n")
    for rel in arm["extensions"]:
        shutil.copy(ROOT / rel, agent / "extensions" / pathlib.Path(rel).name)
    return agent


def git(*args, cwd=None, env=None):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    if p.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout.strip()


def make_checkout(commit, base):
    """A new repo holding only `commit` and its ancestors, checked out detached. Not a
    clone, so no later branch (and no cloud answer) is visible from it."""
    dest = pathlib.Path(base) / "garden"
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=ROOT)
    git("init", "-q", str(dest))
    env = dict(os.environ, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="uploadpack.allowAnySHA1InWant",
               GIT_CONFIG_VALUE_0="true")
    git("fetch", "-q", "--no-tags", common, commit, cwd=dest, env=env)
    git("checkout", "-q", "--detach", commit, cwd=dest)
    if git("rev-parse", "HEAD", cwd=dest) != commit:
        raise RuntimeError("checkout is not at the start commit")
    if _inside(dest, ROOT):
        raise RuntimeError("checkout must be outside the milestone worktree")
    return dest


def workspace_diff(checkout):
    git("add", "-A", cwd=checkout)
    return subprocess.run(["git", "diff", "--cached", "--binary", "HEAD"], cwd=checkout,
                          capture_output=True, text=True, errors="replace").stdout


def safe(f, default=None):
    try:
        return f()
    except Exception as e:  # noqa: BLE001
        return default if default is not None else f"unavailable: {e}"


def pinned_model_sha256(ev):
    """Return a real SHA-256 model pin, repairing a bad hash-cache entry.

    ``evals.run.file_sha256`` trusts a matching size/mtime cache, including its
    stored digest.  A parseable cache with a non-digest value is therefore as
    harmful as a truncated cache.  Delete either kind and retry once; never
    launch an attempt with anything other than a lowercase 64-hex digest.
    """
    cache = pathlib.Path(ev.CACHE) / f"sha256-{pathlib.Path(ev.MODEL_FILE).name}.json"
    repaired = False
    try:
        digest = ev.file_sha256(ev.MODEL_FILE)
    except (json.JSONDecodeError, KeyError, TypeError):
        digest = None
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        cache.unlink(missing_ok=True)
        repaired = True
        digest = ev.file_sha256(ev.MODEL_FILE)
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError(f"file_sha256 returned an invalid SHA-256 digest: {digest!r}")
    return digest, repaired


def run_manifest(ev, arm, arm_hash, cases_path, cases_hash, args, model_hash, hash_cache_repaired):
    return {
        "started": now_iso(),
        "repo_commit": safe(lambda: git("rev-parse", "HEAD", cwd=ROOT)),
        "repo_dirty": safe(lambda: bool(git("status", "--porcelain", cwd=ROOT))),
        "arm": arm, "arm_sha256": arm_hash,
        "cases_path": str(cases_path), "cases_sha256": cases_hash,
        "repeat": args.repeat, "budget_min": args.budget_min,
        "pi_version": safe(lambda: ev.sh("pi", "--version")),
        "pi_flags": ev.PI_FLAGS,
        "sandbox_venv": str(ev.VENV),
        "sandbox_venv_python": safe(lambda: ev.sh(str(ev.VENV / "bin" / "python"), "--version")),
        "model_registration": model_registration(arm),
        "model_file": str(ev.MODEL_FILE),
        "model_sha256": model_hash,
        "model_sha256_cache_repaired": hash_cache_repaired,
        "llama_swap_entry": safe(lambda: ev.swap_entry("bonsai-2-27b")),
        "turnstile_routing": safe(lambda: ev.turnstile_routing()),
        "turnstile_commit": safe(lambda: ev.sh("git", "-C", str(ev.TURNSTILE_CONFIG.parent), "rev-parse", "HEAD")),
        "priority_key": "local-llm-bench",
        "sandbox_image": safe(lambda: ev.sh("docker", "image", "inspect", ev.SANDBOX_IMAGE, "--format", "{{.Id}}")),
        "route": "sandbox tap -> turnstile agent role (bench key) -> bonsai-agent; sandbox network none",
    }


def run_session(ev, arm, arm_hash, case, repeat, adir, check):
    """One attempt. Returns its record. Everything transient lives under one /tmp dir."""
    adir = pathlib.Path(adir)
    shutil.rmtree(adir, ignore_errors=True)
    adir.mkdir(parents=True)
    prompt = render_prompt(case, arm)
    base = pathlib.Path(tempfile.mkdtemp(prefix="w1-replay-", dir="/tmp"))
    container = f"garden-w1-{os.getpid()}-{int(time.time())}"
    sock = base / "tap.sock"
    tap = None
    timed_out, rc = False, None
    t0 = time.time()
    try:
        checkout = make_checkout(case["start_commit"], base)
        agent = make_agent_dir(arm, base, ev.TAP)
        (adir / "manifest.json").write_text(json.dumps({
            "arm": arm["name"], "arm_sha256": arm_hash,
            "case_id": case["case_id"], "repeat": repeat, "start_commit": case["start_commit"],
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "case_prompt_sha256": case.get("prompt_sha256"), "checkout": str(checkout),
            "started": now_iso(), "pi": ["pi", "-p", "--mode", "json", "--no-session", *ev.PI_FLAGS,
                                         "--model", arm["model"], "--thinking", arm["thinking"], "<prompt>"],
        }, indent=2) + "\n")
        tap = ev.start_tap(base / "tap.jsonl", {"run": "worker-eval", "step": f"{arm['name']}/{case['case_id']}/r{repeat}"},
                           ev.bench_key(), sock)
        sb_repo = f"{ev.SB_HOME}/garden"
        mounts = [(checkout, sb_repo, "rw"), (agent, ev.SB_AGENT, "rw"), (ev.VENV, ev.SB_VENV, "ro"),
                  (sock, "/run/garden/tap.sock", "rw"), (ev.EVALS / "relay.py", "/opt/garden/relay.py", "ro")]
        cmd = ev.sandbox_cmd(container, mounts, ev.sandbox_env({"PI_CODING_AGENT_DIR": ev.SB_AGENT}), workdir=sb_repo)
        cmd += ["sh", "-c", f"python3 /opt/garden/relay.py {ev.TAP_PORT} /run/garden/tap.sock & "
                "sleep 0.5; exec \"$@\"", "sh",
                "pi", "-p", "--mode", "json", "--no-session", *ev.PI_FLAGS,
                "--model", arm["model"], "--thinking", arm["thinking"], prompt]
        with open(adir / "events.jsonl", "w") as out, open(adir / "stderr.txt", "w") as err:
            p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)
            try:
                rc = p.wait(arm["session_timeout_min"] * 60)
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                if p.poll() is None:
                    os.killpg(p.pid, signal.SIGKILL)
                    p.wait()
                ev.kill_container(container)
        wall = time.time() - t0
        events = parse_events(adir / "events.jsonl")
        (adir / "final.txt").write_text(events["final"])
        source, req = detect_request(agent / "request.json", events["final"])
        errs = validate_request(req, checkout, check) if req is not None else ["no request"]
        if req is not None:
            (adir / "request.json").write_text(json.dumps(req, indent=2) + "\n")
        (adir / "workspace.diff").write_text(workspace_diff(checkout))
        tap_bytes = safe(lambda: (base / "tap.jsonl").stat().st_size, 0)
        safe(lambda: shutil.copy(base / "tap.jsonl", adir / "tap.jsonl"), None)
        rec = build_record(arm, case, repeat, source, req, errs, events, classify(events, timed_out, rc), wall,
                           {"flag_triggers": flag_triggers(events), "pi_exit_code": rc, "attempt_dir": str(adir), "tap_log_bytes": tap_bytes,
                            "finished": now_iso()})
        (adir / "record.json").write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
        return rec
    finally:
        ev.kill_container(container)
        if tap:
            ev.stop(tap)
        shutil.rmtree(base, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("arm", help="arm name under bench/worker_eval/arms/ (or a path to an arm .json)")
    ap.add_argument("--cases", default=str(HERE / "cases.jsonl"))
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--out", help="stable output directory (default bench/results/<today>/worker_eval/<arm>)")
    ap.add_argument("--budget-min", type=float, default=145, help="chunk budget; a case only starts if its timeout fits")
    ap.add_argument("--only", action="append", default=[], help="run only this case_id (repeatable)")
    ap.add_argument("--limit", type=int, help="run only the first N cases (smoke runs)")
    args = ap.parse_args(argv)
    if args.budget_min > 150:
        sys.exit("--budget-min must leave room inside a 150-minute run request")

    arm, arm_hash = load_arm(args.arm)
    cases = load_cases(args.cases)
    cases_hash = sha256_file(args.cases)
    if args.only:
        missing = set(args.only) - {c["case_id"] for c in cases}
        if missing:
            sys.exit(f"unknown case ids: {sorted(missing)}")
        cases = [c for c in cases if c["case_id"] in args.only]
    if args.limit:
        cases = cases[:args.limit]
    for c in cases:
        render_prompt(c, arm)  # fail before launching anything
    out = pathlib.Path(args.out) if args.out else \
        ROOT / "bench" / "results" / datetime.date.today().isoformat() / "worker_eval" / arm["name"]
    results = out / "results.jsonl"
    prior = load_records(results)
    if any(r.get("arm_sha256") not in (None, arm_hash) for r in prior):
        sys.exit(f"{results} holds records from a different arm definition; use a new --out")

    ev = load_ev()
    resolve_venv(ev)
    try:
        model_hash, hash_cache_repaired = pinned_model_sha256(ev)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"cannot pin model sha256; refusing to launch: {e}")
    ev.preflight([])
    check = orchestrator_check()
    out.mkdir(parents=True, exist_ok=True)
    man = run_manifest(ev, arm, arm_hash, args.cases, cases_hash, args, model_hash, hash_cache_repaired)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    (out / f"manifest-{stamp}.json").write_text(json.dumps(man, indent=2) + "\n")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))

    def attempt(case, rep):
        print(f"[{now_iso()}] {arm['name']} {case['case_id']} r{rep}", flush=True)
        try:
            rec = run_session(ev, arm, arm_hash, case, rep, out / case["case_id"] / f"r{rep}", check)
        except (Exception, SystemExit) as e:  # noqa: BLE001  (start_tap exits via SystemExit)
            if isinstance(e, SystemExit) and e.code == 143:  # SIGTERM: stop the chunk
                raise
            print(f"  attempt did not run: {type(e).__name__}: {e}", flush=True)
            with open(out / "infra-errors.jsonl", "a") as f:
                f.write(json.dumps({"time": now_iso(), "case_id": case["case_id"], "repeat": rep,
                                    "error": f"{type(e).__name__}: {e}"}) + "\n")
            return None
        rec.update(arm_sha256=arm_hash, cases_sha256=cases_hash, manifest=f"manifest-{stamp}.json",
                   repo_commit=man["repo_commit"])
        print(f"  valid={rec['valid_request']} kind={rec['replay_kind']} match={rec['kind_match']} "
              f"{rec['wall_s']}s turns={rec['turns']} tools={rec['tool_calls']}", flush=True)
        return rec

    stats = run_all(arm, cases, args.repeat, results, args.budget_min, attempt)
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
