#!/usr/bin/env python3
"""Benchmark runner: arms x task sequences x repeats, each step a fresh pi session.

  python3 evals/run.py --arms baseline,mem0 --tasks inventory --repeats 3 [--out DIR]

For every (repeat, task, arm) it builds a private pi agent dir from the arm, copies
the task repo into a workspace under /tmp (so no AGENTS.md/CLAUDE.md from this repo
leaks in), and runs each step as `pi -p --mode json` in a new session. Memory state
lives in the run dir, so it carries across the steps of one sequence and never
across runs. Every LLM call goes through evals/tap.py, which tags it with the run
and step and forwards it to turnstile with the local-llm-bench key (priority 20),
so runs yield to interactive work. See docs/benchmark-plan.md.

Outputs (DIR defaults to evals/results/<date>-<arms>):
  manifest.json      pinned versions, server flags, arm and task configs
  results.jsonl      one record per step (checks, timings, per-role tokens)
  tap.jsonl          one record per LLM request
  runs/<run_id>/     pi event streams, stderr, per-step diffs, memory snapshot
  summary.md         written by evals/summarize.py at the end
"""
import argparse
import datetime
import hashlib
import http.client
import json
import os
import pathlib
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
CACHE = EVALS / ".cache"
WS_ROOT = pathlib.Path("/tmp/bonsai-garden-evals")
TAP_PORT = 8091  # inside the sandbox, relayed to the tap's Unix socket
TAP = f"http://127.0.0.1:{TAP_PORT}"
MEM0_PORT = 8092  # inside the sandbox, relayed to the step's mem0 server (self-hosted arms)
TURNSTILE = "http://127.0.0.1:8080"
EMBEDDER = "http://127.0.0.1:8095"
STEP_TIMEOUT = 1800
BENCH_RUNNER = pathlib.Path.home() / "Projects/local-llm-bench/turnstile_run.py"
SWAP_CONFIG = pathlib.Path("/etc/llama-swap/config.yaml")
TURNSTILE_CONFIG = pathlib.Path.home() / "Projects/gpu-turnstile/config.yaml"
MODEL_FILE = pathlib.Path.home() / "models/Ternary-Bonsai-2-27B-PQ2_0.gguf"
EMBED_UNIT = pathlib.Path.home() / ".config/systemd/user/bonsai-garden-embed.service"
PI_FLAGS = ["--no-skills", "--no-prompt-templates", "--no-themes"]
VENV = CACHE / "venv-sandbox"  # python + pinned pytest; built at its sandbox path /opt/venv
PYTEST = "pytest==8.4.2"
MEM0_SERVER = EVALS / "mem0_server.py"
NODE = pathlib.Path(shutil.which("pi")).resolve().parents[6]  # .../installation (node + global pi)

# What the agent sees inside bubblewrap. Neutral names on purpose: the arm, the
# results dir, and this repo must not be discoverable (an unsandboxed baseline agent
# searched the disk and copied a reference solution).
SB_HOME = "/home/dev"
SB_WS = f"{SB_HOME}/inventory"
SB_AGENT = f"{SB_HOME}/.pi/agent"
SB_MEM = f"{SB_HOME}/.local/share/mem0"
SB_VENV = "/opt/venv"
SB_NODE = "/opt/node"
SANDBOX_IMAGE = "ubuntu:24.04"


def bench_key():
    """The local-llm-bench turnstile key, read from its runner so it isn't copied here."""
    m = re.search(r'^KEY = "([^"]+)"', BENCH_RUNNER.read_text(), re.M)
    if not m:
        sys.exit(f"no KEY in {BENCH_RUNNER}")
    return m.group(1)


def sh(*cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw).stdout.strip()


def substitute(obj, mapping):
    if isinstance(obj, dict):
        return {k: substitute(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute(v, mapping) for v in obj]
    if isinstance(obj, str):
        for k, v in mapping.items():
            obj = obj.replace(k, v)
    return obj


# ---- pinning ----

def file_sha256(path):
    """sha256 of a big file, cached by (size, mtime)."""
    st = path.stat()
    stamp = CACHE / f"sha256-{path.name}.json"
    if stamp.exists():
        c = json.loads(stamp.read_text())
        if c["size"] == st.st_size and c["mtime"] == st.st_mtime:
            return c["sha256"]
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    CACHE.mkdir(exist_ok=True)
    stamp.write_text(json.dumps({"size": st.st_size, "mtime": st.st_mtime, "sha256": h.hexdigest()}))
    return h.hexdigest()


def swap_entry(name):
    text = SWAP_CONFIG.read_text()
    m = re.search(rf'^  "?{re.escape(name)}"?:\s*\n((?:    .*\n|\s*\n)+)', text, re.M)
    return m.group(1) if m else None


def turnstile_routing():
    """models:/virtual: blocks from turnstile's config (no keys)."""
    text = TURNSTILE_CONFIG.read_text()
    i = text.find("\nmodels:")
    return text[i + 1:] if i >= 0 else None


def manifest(args, arms, tasks):
    return {
        "started": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "bonsai_garden_commit": sh("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        "bonsai_garden_dirty": bool(sh("git", "-C", str(ROOT), "status", "--porcelain")),
        "pi_version": sh("pi", "--version"),
        "pi_flags": PI_FLAGS,
        "model_file": str(MODEL_FILE),
        "model_sha256": file_sha256(MODEL_FILE),
        "llama_swap_entry": swap_entry("bonsai-2-27b"),
        "turnstile_routing": turnstile_routing(),
        "turnstile_commit": sh("git", "-C", str(TURNSTILE_CONFIG.parent), "rev-parse", "HEAD"),
        "embedder_unit": EMBED_UNIT.read_text() if EMBED_UNIT.exists() else None,
        "priority_key": "local-llm-bench",
        "python": sh(str(VENV / "bin/python"), "--version"),
        "pytest": PYTEST,
        "sandbox_image": sh("docker", "image", "inspect", SANDBOX_IMAGE, "--format", "{{.Id}}"),
        "mem0_server_freeze": {a["name"]: sh(str(mem0_venv(a) / "bin/pip"), "freeze")
                               for a in arms if "mem0_server" in a},
        "repeats": args.repeats,
        "arms": arms,
        "tasks": {name: t["spec"] for name, t in tasks.items()},
        "task_hashes": {name: t["hash"] for name, t in tasks.items()},
    }


def task_hash(d):
    h = hashlib.sha256()
    for p in sorted(d.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(str(p.relative_to(d)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


# ---- agent dirs ----

def agent_template(arm):
    """A cached agent dir with the arm's pi packages (and extra npm deps) installed."""
    key = hashlib.sha256(json.dumps([arm["packages"], arm.get("npm", [])]).encode()).hexdigest()[:12]
    d = CACHE / f"agent-{key}"
    if (d / ".ready").exists():
        return d
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    (d / "settings.json").write_text("{}\n")
    env = dict(os.environ, PI_CODING_AGENT_DIR=str(d))
    for src in arm["packages"]:
        p = subprocess.run(["pi", "install", src], env=env, capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=600)
        if p.returncode != 0:
            sys.exit(f"pi install {src} failed:\n{p.stdout}\n{p.stderr}")
    # Optional peers pi doesn't install (mem0's SQLite store needs better-sqlite3;
    # without it the extension's init fails silently in -p mode).
    if arm.get("npm"):
        subprocess.run(["npm", "install", "--no-audit", "--no-fund", *arm["npm"]], cwd=d / "npm",
                       check=True, capture_output=True, timeout=600)
    (d / ".ready").write_text("")
    return d


def mem0_venv(arm):
    """A cached venv with the arm's mem0 for its per-step server. `pip` is a list of pip
    requirements: a release (mem0ai==2.2.1) or a fork's git ref
    (mem0ai @ git+https://github.com/<fork>/mem0@<sha>), plus pinned extras."""
    spec = arm["mem0_server"]["pip"]
    d = CACHE / f"mem0srv-{hashlib.sha256(json.dumps(spec).encode()).hexdigest()[:12]}"
    if (d / ".ready").exists():
        return d
    shutil.rmtree(d, ignore_errors=True)
    subprocess.run([sys.executable, "-m", "venv", str(d)], check=True)
    p = subprocess.run([str(d / "bin/pip"), "install", "-q", *spec], capture_output=True, text=True,
                       timeout=1800)
    if p.returncode != 0:
        sys.exit(f"pip install {spec} failed:\n{p.stdout}\n{p.stderr}")
    (d / ".ready").write_text("")
    return d


def build_agent_dir(arm, run_dir):
    agent = run_dir / "agent"
    shutil.copytree(agent_template(arm), agent, symlinks=True,
                    ignore=shutil.ignore_patterns(".ready", "sessions"))
    installed = json.loads((agent / "settings.json").read_text())
    mapping = {"{MEM}": SB_MEM, "{TAP}": TAP, "{MEM0}": f"http://127.0.0.1:{MEM0_PORT}"}
    settings = {
        "defaultProvider": "garden",
        "defaultModel": arm["model"],
        "defaultThinkingLevel": arm["thinking"],
        **({"packages": installed["packages"]} if installed.get("packages") else {}),
        **substitute(arm["settings"], mapping),
    }
    (agent / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
    entry = json.loads((ROOT / "agent/models.bonsai-agent.json").read_text())
    models = {"providers": {"garden": {
        "baseUrl": f"{TAP}/agent/v1", "api": "openai-completions", "apiKey": "tap",
        "compat": {"supportsStore": False, "supportsDeveloperRole": False,
                   "supportsReasoningEffort": False, "maxTokensField": "max_tokens"},
        "models": [entry]}}}
    (agent / "models.json").write_text(json.dumps(models, indent=2) + "\n")
    (run_dir / "memory").mkdir(exist_ok=True)
    return agent


# ---- one step ----

def start_tap(log, tags, key, sock, routes=None):
    """A tap on a fresh Unix socket: the sandbox's only way out. It reaches turnstile
    (agent and mem roles, with the bench key) and the embedder, plus any extra
    `routes` ({role: url}) the caller adds, nothing else."""
    env = dict(os.environ, GARDEN_BENCH_KEY=key)
    cmd = [sys.executable, str(EVALS / "tap.py"), "--unix", str(sock), "--log", str(log),
           "--route", f"agent={TURNSTILE}:GARDEN_BENCH_KEY",
           "--route", f"mem={TURNSTILE}:GARDEN_BENCH_KEY",
           "--route", f"embed={EMBEDDER}"]
    for role, url in (routes or {}).items():
        cmd += ["--route", f"{role}={url}"]
    for k, v in tags.items():
        cmd += ["--tag", f"{k}={v}"]
    p = subprocess.Popen(cmd, env=env, stderr=subprocess.PIPE, text=True)
    for _ in range(50):
        if p.poll() is not None:
            sys.exit(f"tap exited: {p.stderr.read()}")
        with socket.socket(socket.AF_UNIX) as probe:
            if probe.connect_ex(str(sock)) == 0:
                return p
        time.sleep(0.1)
    p.kill()
    sys.exit("tap did not start")


def stop(p):
    if p.poll() is None:
        p.send_signal(signal.SIGTERM)
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            p.kill()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def unix_get(sock, path, timeout=60):
    """GET over a Unix socket; returns parsed JSON."""
    class Conn(http.client.HTTPConnection):
        def connect(self):
            self.sock = socket.socket(socket.AF_UNIX)
            self.sock.settimeout(timeout)
            self.sock.connect(str(sock))
    c = Conn("localhost", timeout=timeout)
    c.request("GET", path)
    r = c.getresponse()
    body = r.read()
    c.close()
    if r.status != 200:
        raise OSError(f"GET {path}: {r.status} {body[:200]!r}")
    return json.loads(body)


def start_mem0_server(ctx, step_i, tap_sock):
    """The arm's mem0 server for one step, outside the sandbox, on a fresh Unix socket.
    Its store lives in the run dir, so memory carries across steps (each step gets a
    fresh process, like each pi session). Its LLM and embedder traffic goes through
    a host relay to this step's tap, so it is metered and tagged like pi's.
    Returns (server sock, procs to stop)."""
    arm, run_dir = ctx["arm"], ctx["run_dir"]
    port = free_port()
    relay = subprocess.Popen([sys.executable, str(EVALS / "relay.py"), str(port), str(tap_sock)])
    store = run_dir / "mem0-server"
    store.mkdir(exist_ok=True)
    mapping = {"{HOSTTAP}": f"http://127.0.0.1:{port}", "{STORE}": str(store), "{CACHE}": str(CACHE)}
    cfg = substitute(arm["mem0_server"]["config"], mapping)
    (store / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")
    sock = pathlib.Path(f"/tmp/garden-mem0-{os.getpid()}.sock")
    sock.unlink(missing_ok=True)
    # MEM0_DIR keeps mem0's ~/.mem0 (user id, migrations store) inside the run.
    env = dict(os.environ, MEM0_TELEMETRY="false", MEM0_DIR=str(store / "home"),
               **substitute(arm["mem0_server"].get("env", {}), mapping))
    with open(run_dir / f"step{step_i}.mem0.log", "w") as log:
        srv = subprocess.Popen([str(ctx["mem0_venv"] / "bin/python"), "-I", str(MEM0_SERVER),
                                "--unix", str(sock), "--config", str(store / "config.json")],
                               env=env, stdout=log, stderr=subprocess.STDOUT, cwd=store)
    for _ in range(600):
        if srv.poll() is not None:
            stop(relay)
            sys.exit(f"mem0 server exited; see {run_dir}/step{step_i}.mem0.log")
        try:
            if unix_get(sock, "/health", timeout=2).get("status") == "ok":
                return sock, [srv, relay]
        except OSError:
            pass
        time.sleep(0.1)
    stop(srv)
    stop(relay)
    sys.exit("mem0 server did not start")


def text_of(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return c
    return "".join(x.get("text", "") for x in c or [] if isinstance(x, dict) and x.get("type") == "text")


def parse_events(path):
    turns = tools = 0
    final = ""
    errors = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        t = e.get("type")
        if t == "turn_end":
            turns += 1
        elif t == "tool_execution_start":
            tools += 1
        elif t == "message_end" and (e.get("message") or {}).get("role") == "assistant":
            m = e["message"]
            if text_of(m).strip():
                final = text_of(m)
            if m.get("stopReason") == "error" or m.get("errorMessage"):
                errors.append(m.get("errorMessage") or "error")
    return {"turns": turns, "tool_calls": tools, "final": final, "errors": errors}


def tap_stats(tap_log, run_id, step):
    out = {}
    if not tap_log.exists():
        return out
    for line in tap_log.read_text().splitlines():
        r = json.loads(line)
        if r.get("run") != run_id or r.get("step") != str(step) or not r["path"].endswith("/completions"):
            continue
        s = out.setdefault(r["role"], {"requests": 0, "prompt_n": 0, "cache_n": 0, "predicted_n": 0,
                                       "prompt_ms": 0.0, "predicted_ms": 0.0, "queue_wait_ms": 0,
                                       "wall_s": 0.0, "errors": 0})
        s["requests"] += 1
        s["queue_wait_ms"] += r.get("queue_wait_ms", 0)
        s["wall_s"] = round(s["wall_s"] + r["wall_s"], 3)
        if r["status"] != 200:
            s["errors"] += 1
        t = r.get("timings") or {}
        for k in ("prompt_n", "cache_n", "predicted_n"):
            s[k] += t.get(k) or 0
        for k in ("prompt_ms", "predicted_ms"):
            s[k] = round(s[k] + (t.get(k) or 0), 1)
    return out


def run_step(ctx, step_i, step):
    run_dir, ws, agent = ctx["run_dir"], ctx["ws"], ctx["agent"]
    tags = {"run": ctx["run_id"], "arm": ctx["arm"]["name"], "task": ctx["task"], "step": step_i}
    sock = pathlib.Path(f"/tmp/garden-tap-{os.getpid()}.sock")
    tap = start_tap(ctx["tap_log"], tags, ctx["key"], sock)
    env = sandbox_env({"PI_CODING_AGENT_DIR": SB_AGENT, **ctx["arm"]["env"]})
    events = run_dir / f"step{step_i}.events.jsonl"
    # Only the workspace, this run's agent dir, and its memory dir are writable or
    # visible; sessions aren't saved, so earlier steps can only come back via memory.
    container = f"garden-{ctx['run_id']}-s{step_i}-{os.getpid()}"
    mounts = [(ws, SB_WS, "rw"), (agent, SB_AGENT, "rw"), (run_dir / "memory", SB_MEM, "rw"),
              (VENV, SB_VENV, "ro"), (sock, "/run/garden/tap.sock", "rw"),
              (EVALS / "relay.py", "/opt/garden/relay.py", "ro")]
    # The relays give pi (and mem0 inside it) the tap at 127.0.0.1:TAP_PORT and, for
    # self-hosted arms, the step's mem0 server at 127.0.0.1:MEM0_PORT.
    relays = f"python3 /opt/garden/relay.py {TAP_PORT} /run/garden/tap.sock & "
    mem0_sock, mem0_procs = None, []
    if "mem0_server" in ctx["arm"]:
        try:
            mem0_sock, mem0_procs = start_mem0_server(ctx, step_i, sock)
        except BaseException:
            stop(tap)
            raise
        mounts.append((mem0_sock, "/run/garden/mem0.sock", "rw"))
        relays += f"python3 /opt/garden/relay.py {MEM0_PORT} /run/garden/mem0.sock & "
    sandbox = sandbox_cmd(container, mounts, env, workdir=SB_WS)
    sandbox += ["sh", "-c", relays + "sleep 0.5; exec \"$@\"", "sh"]
    t0 = time.time()
    # pi gets its own process group so nothing it spawns outlives the step, even if
    # the runner itself is interrupted (an orphan would keep talking to the next tap).
    with open(events, "w") as out, open(run_dir / f"step{step_i}.stderr", "w") as err:
        p = subprocess.Popen(sandbox + ["pi", "-p", "--mode", "json", "--no-session",
                                        "--model", f"garden/{ctx['arm']['model']}",
                                        "--thinking", ctx["arm"]["thinking"], *PI_FLAGS, step["prompt"]],
                             stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)
        try:
            rc = p.wait(STEP_TIMEOUT)
        except subprocess.TimeoutExpired:
            rc = "timeout"
        finally:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            kill_container(container)  # the docker client dying doesn't stop the container
            if mem0_sock:
                try:
                    dump = unix_get(mem0_sock, "/_dump")
                    (run_dir / "memories.json").write_text(json.dumps(dump, indent=2) + "\n")
                except OSError as e:
                    print(f"mem0 dump failed: {e}", file=sys.stderr)
                for proc in mem0_procs:
                    stop(proc)
                mem0_sock.unlink(missing_ok=True)
            stop(tap)
            sock.unlink(missing_ok=True)
    wall = time.time() - t0
    ev = parse_events(events)
    final_file = run_dir / f"step{step_i}.final.txt"
    final_file.write_text(ev["final"])
    chk = subprocess.run([str(VENV / "bin/python"), "-I", str(ctx["task_dir"] / "check.py"), str(ws),
                          str(step_i), str(final_file)], capture_output=True, text=True, timeout=600,
                         env=checker_env())
    try:
        verdict = json.loads(chk.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        verdict = {"pass": False, "checks": {}, "checker_error": chk.stderr[-2000:]}
    # Snapshot the step's changes, then commit so the next step's diff is its own.
    sh("git", "-C", str(ws), "add", "-A")
    (run_dir / f"step{step_i}.diff").write_text(sh("git", "-C", str(ws), "diff", "--cached"))
    sh("git", "-C", str(ws), "-c", "user.name=harness", "-c", "user.email=harness@local",
       "commit", "-qm", f"step {step_i}", "--allow-empty")
    return {"run_id": ctx["run_id"], "arm": ctx["arm"]["name"], "task": ctx["task"], "rep": ctx["rep"],
            "step": step_i, "pass": verdict["pass"], "checks": verdict.get("checks", {}),
            **({"checker_error": verdict["checker_error"]} if "checker_error" in verdict else {}),
            "exit": rc, "wall_s": round(wall, 1), "turns": ev["turns"], "tool_calls": ev["tool_calls"],
            "pi_errors": ev["errors"][:3], "llm": tap_stats(ctx["tap_log"], ctx["run_id"], step_i)}


def snapshot_memory(run_dir):
    db = run_dir / "memory" / "mem0-vectors.db"
    if not db.exists():
        return
    con = sqlite3.connect(db)
    rows = []
    for (table,) in con.execute("select name from sqlite_master where type='table'"):
        cols = [c[1] for c in con.execute(f"pragma table_info({table})")]
        if "payload" in cols:
            for (payload,) in con.execute(f"select payload from {table}"):
                try:
                    rows.append(json.loads(payload))
                except (TypeError, ValueError):
                    rows.append(payload)
    con.close()
    (run_dir / "memories.json").write_text(json.dumps(rows, indent=2) + "\n")


def run_sequence(args, out, arm, task_name, task, rep, key):
    run_id = f"{task_name}-{arm['name']}-r{rep}"
    run_dir = out / "runs" / run_id
    if (run_dir / "done").exists():
        print(f"skip {run_id} (done)", flush=True)
        return
    shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)
    ws = WS_ROOT / out.name / run_id
    shutil.rmtree(ws, ignore_errors=True)
    shutil.copytree(task["dir"] / "repo", ws)
    sh("git", "-C", str(ws), "init", "-q")
    sh("git", "-C", str(ws), "add", "-A")
    sh("git", "-C", str(ws), "-c", "user.name=harness", "-c", "user.email=harness@local",
       "commit", "-qm", "initial")
    ctx = {"run_id": run_id, "run_dir": run_dir, "ws": ws, "agent": build_agent_dir(arm, run_dir),
           "mem0_venv": mem0_venv(arm) if "mem0_server" in arm else None,
           "arm": arm, "task": task_name, "task_dir": task["dir"], "rep": rep, "key": key,
           "tap_log": out / "tap.jsonl"}
    for i, step in enumerate(task["spec"]["steps"]):
        print(f"{run_id} step {i} ...", end=" ", flush=True)
        rec = run_step(ctx, i, step)
        with open(out / "results.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"{'PASS' if rec['pass'] else 'fail'} {rec['checks']} {rec['wall_s']}s", flush=True)
    snapshot_memory(run_dir)
    (run_dir / "done").write_text("")


def sandbox_cmd(name, mounts, env, workdir=SB_HOME):
    """docker run argv for an isolated step. The container sees the host's /usr read-only
    (same Ubuntu release, so node and python just work), an empty tmpfs home and /tmp,
    its own PID namespace, no network, and only the given mounts."""
    args = ["docker", "run", "--rm", "--name", name, "--network", "none",
            "--user", f"{os.getuid()}:{os.getgid()}", "--read-only",
            "--tmpfs", "/tmp", "--tmpfs", f"{SB_HOME}:uid={os.getuid()},gid={os.getgid()}",
            "-v", "/usr:/usr:ro", "-v", f"{NODE}:{SB_NODE}:ro", "-w", workdir]
    for src, dst, mode in mounts:
        args += ["-v", f"{src}:{dst}:{mode}"]
    for k, v in env.items():
        args += ["-e", f"{k}={v}"]
    return args + [SANDBOX_IMAGE]


def sandbox_env(extra=None):
    return {"HOME": SB_HOME, "USER": "dev", "LANG": "C.UTF-8", "TERM": "dumb",
            "PATH": f"{SB_VENV}/bin:{SB_NODE}/bin:/usr/bin:/bin", "VIRTUAL_ENV": SB_VENV,
            **(extra or {})}


def kill_container(name):
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def ensure_venv():
    """Build the venv at its sandbox path so its scripts' shebangs work in there."""
    if (VENV / "bin/pytest").exists():
        return
    VENV.mkdir(parents=True, exist_ok=True)
    mounts = [(VENV, SB_VENV, "rw"), ("/etc/ssl/certs", "/etc/ssl/certs", "ro")]  # certs for pip
    cmd = sandbox_cmd("garden-venv", mounts, {"HOME": SB_HOME}) + [
        "sh", "-c", f"python3 -m venv {SB_VENV} && {SB_VENV}/bin/pip install -q {PYTEST}"]
    subprocess.run(cmd, check=True)


def checker_env():
    """The checker runs outside the sandbox with the same venv first on PATH."""
    return dict(os.environ, PATH=f"{VENV / 'bin'}:{os.environ['PATH']}", VIRTUAL_ENV=str(VENV))


def preflight(arms):
    try:
        urllib.request.urlopen(f"{TURNSTILE}/api/queue", timeout=5)
    except OSError as e:
        sys.exit(f"turnstile not reachable: {e}")
    if any(a["packages"] or "mem0_server" in a for a in arms):
        try:
            urllib.request.urlopen("http://127.0.0.1:8095/health", timeout=5)
        except OSError as e:
            sys.exit(f"embedder (:8095) not reachable: {e}; systemctl --user start bonsai-garden-embed")


def on_sigterm(*_):
    raise KeyboardInterrupt  # unwind like Ctrl-C so run_step's finally kills pi and the tap


def main():
    signal.signal(signal.SIGTERM, on_sigterm)
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="baseline,mem0")
    ap.add_argument("--tasks", default="inventory")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out")
    args = ap.parse_args()
    arms = [json.loads((EVALS / "arms" / f"{a}.json").read_text()) for a in args.arms.split(",")]
    tasks = {}
    for t in args.tasks.split(","):
        d = EVALS / "tasks" / t
        tasks[t] = {"dir": d, "spec": json.loads((d / "task.json").read_text()), "hash": task_hash(d)}
    # Absolute, because it ends up in docker -v mounts and the mem0 server's config.
    out = pathlib.Path(args.out).resolve() if args.out else \
        EVALS / "results" / f"{datetime.date.today()}-{'-'.join(a['name'] for a in arms)}"
    out.mkdir(parents=True, exist_ok=True)
    preflight(arms)
    ensure_venv()
    for a in arms:
        if "mem0_server" in a:
            mem0_venv(a)
    if not (out / "manifest.json").exists():
        (out / "manifest.json").write_text(json.dumps(manifest(args, arms, tasks), indent=2) + "\n")
    key = bench_key()
    # Interleave arms within each repeat so drift (thermal, other GPU users) hits both.
    for rep in range(args.repeats):
        for task_name, task in tasks.items():
            for arm in arms:
                run_sequence(args, out, arm, task_name, task, rep, key)
    subprocess.run([sys.executable, str(EVALS / "summarize.py"), str(out)])


if __name__ == "__main__":
    main()
