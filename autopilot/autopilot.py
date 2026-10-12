#!/usr/bin/env python3
"""bonsai-garden autopilot: Bonsai does the work, a cloud advisor reviews, code enforces.

  autopilot.py loop        run milestones until done or blocked (the systemd service)
  autopilot.py tick        one step, then exit
  autopilot.py status      print the current state
  autopilot.py unblock     clear a blocked milestone so the loop resumes

Roles (config.json) are pi model strings, so any of them can be swapped:
  worker   Bonsai via turnstile (bench key, priority 20), in the eval Docker sandbox
  advisor  cloud model through meridian, read-only tools: plans, reviews every request,
           approves finished items and fact-checks write-ups
  fixer    cloud model with shell access, called only when the local model is down
           and rolling back the last infra change didn't help

Work happens on branch auto/<milestone> in its own worktree. State and the journal
(the worker's memory between sessions) are committed there under autopilot/state/.
Finished milestones are merged to main and pushed, which publishes the site; a status
page (site/autopilot.md) is pushed as things happen.
"""
import datetime
import fcntl
import json
import os
import pathlib
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "evals"))
sys.path.insert(0, str(HERE))
import infra  # noqa: E402
import run as ev  # noqa: E402  (sandbox, tap and event helpers from the eval harness)

CFG = json.loads((HERE / "config.json").read_text())
RT = HERE / ".runtime"
WT_ROOT = pathlib.Path(CFG["worktree_root"])
WT = None  # the current milestone's worktree; set by tick()
PUB = pathlib.Path(CFG["publisher"])
CLOUD_AGENT = HERE / ".cache" / "agent-cloud"
SB_REPO = f"{ev.SB_HOME}/garden"
PROMPTS = HERE / "prompts"
JOURNAL_TAIL = 15000
DIFF_MAX = 40000


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def say(msg):
    print(f"{now()} {msg}", flush=True)


def git(*args, cwd=None, check=True):
    p = subprocess.run(["git", *args], cwd=cwd or WT, capture_output=True, text=True)
    if check and p.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout.strip()


def last_json(text):
    """The last JSON object in a reply: a fenced json block, else any trailing object."""
    for block in reversed(re.findall(r"```json\s*(.*?)```", text, re.S)):
        try:
            return json.loads(block)
        except ValueError:
            pass
    dec = json.JSONDecoder()
    for i in reversed([i for i, c in enumerate(text) if c == "{"]):
        try:
            obj, _ = dec.raw_decode(text[i:])
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
    return None


def fill(template, **kw):
    return (PROMPTS / template).read_text().format(**kw)


# ---- state ----

class Milestone:
    def __init__(self, name):
        self.name = name
        self.spec = (HERE / "milestones" / f"{name}.md").read_text()
        self.wt = WT_ROOT / name
        self.dir = self.wt / "autopilot" / "state" / name

    @property
    def status_file(self):
        return self.dir / "status.json"

    def status(self):
        if self.status_file.exists():
            return json.loads(self.status_file.read_text())
        return {"phase": "plan", "item": 0, "round": 0, "reviews": 0, "base": None, "dropped": []}

    def save(self, st):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.status_file.write_text(json.dumps(st, indent=2) + "\n")

    def plan(self):
        p = self.dir / "plan.json"
        return json.loads(p.read_text())["items"] if p.exists() else []

    def journal(self, actor, text):
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.dir / "journal.md", "a") as f:
            f.write(f"\n### {now()} · {actor}\n\n{text.strip()}\n")

    def journal_tail(self):
        p = self.dir / "journal.md"
        t = p.read_text() if p.exists() else "(empty)"
        return t if len(t) <= JOURNAL_TAIL else "…\n" + t[-JOURNAL_TAIL:]


# ---- budget ----

def budget_left():
    p = RT / "budget.json"
    b = json.loads(p.read_text()) if p.exists() else {}
    return CFG["cloud_calls_per_day"] - b.get(datetime.date.today().isoformat(), 0)


def spend():
    RT.mkdir(parents=True, exist_ok=True)
    p = RT / "budget.json"
    b = json.loads(p.read_text()) if p.exists() else {}
    day = datetime.date.today().isoformat()
    b = {day: b.get(day, 0) + 1}
    p.write_text(json.dumps(b))


class OutOfBudget(Exception):
    pass


# ---- model calls ----

def call_log(label):
    d = RT / "calls"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{datetime.datetime.now():%Y%m%d-%H%M%S}-{label}.jsonl"


def ensure_cloud_agent():
    if (CLOUD_AGENT / "settings.json").exists():
        return
    CLOUD_AGENT.mkdir(parents=True, exist_ok=True)
    (CLOUD_AGENT / "settings.json").write_text("{}\n")
    subprocess.run(["pi", "install", CFG["cloud_extension"]], env=dict(os.environ, PI_CODING_AGENT_DIR=str(CLOUD_AGENT)),
                   stdin=subprocess.DEVNULL, check=True, capture_output=True, timeout=600)


def call_cloud(role, prompt, label):
    """A cloud role (advisor or fixer) as a host pi session through meridian."""
    ensure_cloud_agent()
    if budget_left() <= 0:
        raise OutOfBudget(role)
    spend()
    r = CFG["roles"][role]
    events = call_log(f"{role}-{label}")
    env = dict(os.environ, PI_CODING_AGENT_DIR=str(CLOUD_AGENT))
    with open(events, "w") as out:
        p = subprocess.run(["pi", "-p", "--mode", "json", "--no-session", *ev.PI_FLAGS,
                            "--model", f"{r['model']}:{r['thinking']}", "--tools", r["tools"], prompt],
                           cwd=WT, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.PIPE,
                           text=True, timeout=3600)
    e = ev.parse_events(events)
    say(f"{role}/{label}: exit {p.returncode}, {e['turns']} turns, {e['tool_calls']} tools")
    return e["final"], e


def worker_agent_dir():
    agent = RT / "agent-worker"
    if not (agent / "models.json").exists():
        agent.mkdir(parents=True, exist_ok=True)
        r = CFG["roles"]["worker"]
        (agent / "settings.json").write_text(json.dumps(
            {"defaultProvider": "garden", "defaultModel": r["model"], "defaultThinkingLevel": r["thinking"],
             # pi's default 16k reserve let a turn reach 66.5k (turnstile's estimate) + 16k
             # max_tokens > the 80k window; compact at ~52k instead.
             "compaction": {"reserveTokens": 28672}}))
        entry = json.loads((ROOT / "agent/models.bonsai-agent.json").read_text())
        entry["id"] = r["model"]
        (agent / "models.json").write_text(json.dumps({"providers": {"garden": {
            "baseUrl": f"{ev.TAP}/agent/v1", "api": "openai-completions", "apiKey": "tap",
            "compat": {"supportsStore": False, "supportsDeveloperRole": False,
                       "supportsReasoningEffort": False, "maxTokensField": "max_tokens"},
            "models": [entry]}}}, indent=2))
    return agent


def call_worker(prompt, label):
    """The worker: pi on Bonsai in the eval sandbox, seeing only the autopilot worktree."""
    r = CFG["roles"]["worker"]
    events = call_log(f"worker-{label}")
    sock = pathlib.Path(f"/tmp/garden-autopilot-{os.getpid()}.sock")
    tap = ev.start_tap(RT / "tap.jsonl", {"run": "autopilot", "step": label}, ev.bench_key(), sock)
    container = f"garden-autopilot-{os.getpid()}"
    cmd = ev.sandbox_cmd(container, [(WT, SB_REPO, "rw"), (worker_agent_dir(), ev.SB_AGENT, "rw"),
                                     (ev.VENV, ev.SB_VENV, "ro"), (sock, "/run/garden/tap.sock", "rw"),
                                     (ev.EVALS / "relay.py", "/opt/garden/relay.py", "ro")],
                         ev.sandbox_env({"PI_CODING_AGENT_DIR": ev.SB_AGENT}), workdir=SB_REPO)
    cmd += ["sh", "-c", f"python3 /opt/garden/relay.py {ev.TAP_PORT} /run/garden/tap.sock & "
            "sleep 0.5; exec \"$@\"", "sh",
            "pi", "-p", "--mode", "json", "--no-session", *ev.PI_FLAGS,
            "--model", f"garden/{r['model']}", "--thinking", r["thinking"], prompt]
    with open(events, "w") as out:
        p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        try:
            p.wait(CFG["worker_timeout_min"] * 60)
        except subprocess.TimeoutExpired:
            pass
        finally:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            ev.kill_container(container)
            ev.stop(tap)
            sock.unlink(missing_ok=True)
    e = ev.parse_events(events)
    say(f"worker/{label}: {e['turns']} turns, {e['tool_calls']} tools, errors {e['errors'][:2]}")
    return e["final"], e


# ---- git plumbing ----

def ensure_worktree(m):
    if m.wt.exists():
        return
    git("fetch", "-q", CFG["remote"], cwd=ROOT)
    branch = f"auto/{m.name}"
    WT_ROOT.mkdir(parents=True, exist_ok=True)
    if git("rev-parse", "--verify", "-q", branch, cwd=ROOT, check=False):
        git("worktree", "add", str(m.wt), branch, cwd=ROOT)
    else:
        git("worktree", "add", "-b", branch, str(m.wt), f"{CFG['remote']}/main", cwd=ROOT)


def commit(msg):
    git("add", "-A")
    if git("status", "--porcelain"):
        git("-c", "user.name=bonsai-autopilot", "-c", "user.email=autopilot@bonsai-garden.local",
            "commit", "-qm", msg)


def enforce_protected(m, base):
    """Revert the worker's edits to protected paths, i.e. changes since `base`, the commit
    taken just before its session."""
    changed = git("diff", "--name-only", base).splitlines() + \
        git("ls-files", "--others", "--exclude-standard").splitlines()
    bad = sorted({f for f in changed if any(f.startswith(p) for p in CFG["protected_paths"])})
    for f in bad:
        if subprocess.run(["git", "cat-file", "-e", f"{base}:{f}"], cwd=WT).returncode == 0:
            git("checkout", base, "--", f)
        else:
            (WT / f).unlink(missing_ok=True)
    if bad:
        m.journal("orchestrator", f"Reverted edits to protected paths: {', '.join(bad)}")
    return bad


def item_diff(st):
    d = git("diff", st["base"], "--", ".", ":(exclude)autopilot/state", check=False)
    return d if len(d) <= DIFF_MAX else d[:DIFF_MAX] + "\n… (truncated)"


SECRET_PATTERNS = [r"tk-[0-9a-f]{20,}", r"sk-[A-Za-z0-9_-]{20,}", r"gh[pousr]_[A-Za-z0-9]{20,}",
                   r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"AKIA[0-9A-Z]{16}"]
SECRET_FILES = [pathlib.Path.home() / "Projects/gpu-turnstile/config.yaml",
                pathlib.Path.home() / "Projects/gpu-turnstile/.keys.env", pathlib.Path.home() / ".pi/agent/auth.json"]


def secret_hits(rev_range, cwd):
    """Known key values and key-shaped strings added in rev_range. Pushes are public."""
    diff = "\n".join(l for l in git("diff", rev_range, cwd=cwd, check=False).splitlines() if l.startswith("+"))
    hits = [p for p in SECRET_PATTERNS if re.search(p, diff)]
    for f in SECRET_FILES:
        if f.exists():
            for v in set(re.findall(r"[A-Za-z0-9_\-]{24,}", f.read_text())):
                if v in diff:
                    hits.append(f"value from {f.name}")
    return hits


def push(cwd, refspec, rev_range):
    hits = secret_hits(rev_range, cwd)
    if hits:
        raise RuntimeError(f"refusing to push {refspec}: possible secrets ({', '.join(sorted(set(hits)))})")
    git("push", "-q", "-f", CFG["remote"], refspec, cwd=cwd)


def publish(msg, merge_branch=None):
    """Push to main from the publisher worktree (never the user's checkout), then
    fast-forward the main checkout if it is clean and on main."""
    git("fetch", "-q", CFG["remote"], cwd=ROOT)
    if not PUB.exists():
        git("worktree", "add", "--detach", str(PUB), f"{CFG['remote']}/main", cwd=ROOT)
    git("checkout", "-q", "--detach", f"{CFG['remote']}/main", cwd=PUB)
    if merge_branch:
        git("-c", "user.name=bonsai-autopilot", "-c", "user.email=autopilot@bonsai-garden.local",
            "merge", "--no-ff", "-m", msg, merge_branch, cwd=PUB)
    write_status_page()
    git("add", "-A", cwd=PUB)
    if git("status", "--porcelain", cwd=PUB):
        git("-c", "user.name=bonsai-autopilot", "-c", "user.email=autopilot@bonsai-garden.local",
            "commit", "-qm", msg, cwd=PUB)
    if git("rev-parse", "HEAD", cwd=PUB) != git("rev-parse", f"{CFG['remote']}/main", cwd=PUB):
        push(PUB, "HEAD:main", f"{CFG['remote']}/main..HEAD")
        (RT / "last-push").write_text(now())
        if git("branch", "--show-current", cwd=ROOT) == "main" and not git("status", "--porcelain", cwd=ROOT):
            git("merge", "-q", "--ff-only", f"{CFG['remote']}/main", cwd=ROOT, check=False)


def maybe_publish_status(force=False):
    last = RT / "last-push"
    if not force and last.exists():
        age = time.time() - last.stat().st_mtime
        if age < CFG["status_push_min_interval_min"] * 60:
            return
    try:
        publish("autopilot: status update")
    except RuntimeError as e:
        say(f"status publish failed: {e}")


def write_status_page():
    lines = ["---", "title: Autopilot status", "kind: Live status",
             f"updated: {datetime.date.today().isoformat()}", "---", "",
             f"*Updated {now()}. Written by `autopilot/autopilot.py`; see the "
             "[roadmap](https://github.com/aiguy110/bonsai-garden/blob/main/docs/roadmap.md) "
             "for how it works.*", ""]
    lines += [f"Cloud advisor calls left today: **{budget_left()}** of {CFG['cloud_calls_per_day']}.", ""]
    for name in CFG["milestones"]:
        m = Milestone(name)
        st, plan = m.status(), m.plan()
        lines += [f"## {name}", "", f"**Phase:** {st['phase']}"
                  + (f" — {st.get('blocked')}" if st.get("blocked") else ""), ""]
        for i, it in enumerate(plan):
            mark = "✅" if i < st["item"] else ("▶️" if i == st["item"] and st["phase"] == "work" else "⬜")
            if it["id"] in st.get("dropped", []):
                mark = "✖️"
            lines.append(f"- {mark} **{it['title']}**" + (f" (round {st['round']})" if mark == "▶️" else ""))
        jp = m.dir / "journal.md"
        if jp.exists():
            heads = re.findall(r"^### (.*)$", jp.read_text(), re.M)[-12:]
            lines += ["", "<details><summary>Recent journal entries</summary>", "", *[f"- {h}" for h in heads],
                      "", f"Full journal: [branch auto/{name}](https://github.com/aiguy110/bonsai-garden/blob/"
                      f"auto/{name}/autopilot/state/{name}/journal.md)", "</details>"]
        lines.append("")
    il = infra.RUNTIME / "log.jsonl"
    if il.exists():
        lines += ["## Live-stack changes", "", "| time | op | result | 2-slot tok/s |", "|---|---|---|---|"]
        for rec in [json.loads(x) for x in il.read_text().splitlines()[-8:]]:
            tok = rec.get("conc_mean_tok_s") or (rec.get("after_restore") or {}).get("conc_mean_tok_s", "")
            lines.append(f"| {rec['ts']} | {rec['op']} | {rec.get('result', 'ok' if rec.get('ok') else 'fail')} | {tok} |")
    (PUB / "site" / "autopilot.md").write_text("\n".join(lines) + "\n")


# ---- health and hand-off ----

def watchdog(m):
    """True if the local model is usable. Handles soak promotion, rollback, and the cloud
    hand-off. Blocks the milestone if nothing works."""
    h = infra.turnstile_health()
    soak = infra.RUNTIME / "pending-soak"
    if h["ok"] is not False:
        if h["ok"] and soak.exists():
            s = json.loads(soak.read_text())
            s["calls_left"] -= 1
            if s["calls_left"] <= 0:
                shutil.copy(infra.LIVE, infra.RUNTIME / "known-good.yaml")
                soak.unlink()
                infra.log({"op": "promote", "ok": True, "candidate": s["candidate"]})
                m.journal("orchestrator", "The applied config survived its soak period and is now known-good.")
            else:
                soak.write_text(json.dumps(s))
        return True
    incident = [f"Health check through turnstile failed: {h['why']}"]
    m.journal("orchestrator", incident[0])
    if soak.exists():
        r = json.loads(subprocess.run([sys.executable, str(HERE / "infra.py"), "rollback"], capture_output=True,
                                      text=True).stdout.strip().splitlines()[-1])
        incident.append(f"Automatic rollback to known-good: {json.dumps(r)}")
        m.journal("orchestrator", incident[-1])
        h = infra.turnstile_health()
        if h["ok"] is not False:
            m.journal("orchestrator", "Service restored by rollback. The applied change is considered failed.")
            maybe_publish_status(force=True)
            return True
    say("handing off to the cloud fixer")
    try:
        final, _ = call_cloud("fixer", fill("fixer.md", incident="\n".join(incident),
                                            known_good=infra.RUNTIME / "known-good.yaml",
                                            infra_log=infra.RUNTIME / "log.jsonl",
                                            infra_py=HERE / "infra.py"), "incident")
        res = last_json(final) or {}
        m.journal("fixer (cloud)", final)
    except OutOfBudget:
        res = {"fixed": False, "diagnosis": "cloud budget exhausted"}
    h = infra.turnstile_health()
    if h["ok"] is False:
        block(m, f"local model down; fixer: {res.get('diagnosis', 'no diagnosis')}")
        return False
    return True


def block(m, why):
    st = m.status()
    st["phase"], st["blocked"] = "blocked", why
    m.save(st)
    m.journal("orchestrator", f"BLOCKED: {why}")
    commit(f"autopilot({m.name}): blocked")
    maybe_publish_status(force=True)


# ---- requests ----

def check_run_command(cmd):
    try:
        argv = shlex.split(cmd)
    except ValueError as e:
        return None, f"unparseable: {e}"
    if len(argv) < 2 or argv[0] not in ("python3", "bash"):
        return None, "must start with python3 or bash"
    script = (WT / argv[1]).resolve()
    if not (str(script).startswith(str(WT / "bench") + "/") or str(script).startswith(str(WT / "evals") + "/")):
        return None, "script must be under bench/ or evals/"
    if not script.is_file():
        return None, f"{argv[1]} does not exist"
    if any(c in cmd for c in "|;&><`$"):
        return None, "no shell operators"
    return argv, None


def execute_run(m, item, req, rnd):
    argv, err = check_run_command(req.get("command", ""))
    if err:
        return f"Run request rejected by the orchestrator: {err}"
    timeout = min(int(req.get("timeout_min", 60)), 180) * 60
    outdir = WT / "bench" / "results" / datetime.date.today().isoformat() / "autopilot"
    outdir.mkdir(parents=True, exist_ok=True)
    logf = outdir / f"{item['id']}-r{rnd}.log"
    full = [sys.executable, str(ev.BENCH_RUNNER), "--", *argv] if req.get("gpu") else argv
    say(f"run: {' '.join(full)}")
    t0 = time.time()
    with open(logf, "w") as f:
        try:
            p = subprocess.run(full, cwd=WT, stdout=f, stderr=subprocess.STDOUT, timeout=timeout,
                               stdin=subprocess.DEVNULL)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    tail = logf.read_text(errors="replace")[-3000:]
    return (f"Ran `{req['command']}` (gpu={bool(req.get('gpu'))}) in {time.time() - t0:.0f}s, exit {rc}. "
            f"Full output: `{logf.relative_to(WT)}`. Last lines:\n\n```\n{tail}\n```")


def execute_infra(m, req):
    entry = (WT / req.get("entry", "")).resolve()
    if not str(entry).startswith(str(WT / "serving" / "candidates") + "/") or not entry.is_file():
        return "Infra request rejected: entry must be an existing file under serving/candidates/."
    say(f"infra apply {entry}")
    out = subprocess.run([sys.executable, str(HERE / "infra.py"), "apply", str(entry)], capture_output=True,
                         text=True).stdout.strip().splitlines()
    res = json.loads(out[-1]) if out else {"ok": False, "why": "no output"}
    if res.get("result") == "applied":
        shutil.copy(entry, WT / "serving" / "llama-swap.bonsai-2-27b.yaml")
        msg = ("Applied to the live server. Post-deploy health: "
               f"single {res.get('single_tok_s')} tok/s, 2-slot {res.get('conc_tok_s')} tok/s "
               f"(floor {res.get('floor')}). It becomes known-good after "
               f"{CFG['infra']['soak_worker_calls']} healthy worker calls; any failure before then rolls it back. "
               "`serving/llama-swap.bonsai-2-27b.yaml` now holds this entry.")
    else:
        msg = f"Not applied ({res.get('result', 'failed')}); the previous config is live. Details: {json.dumps(res)}"
    maybe_publish_status(force=True)
    return msg


def review(m, item, kind, subject, instructions, st):
    final, _ = call_cloud("advisor", fill("review.md", milestone=m.spec, item_id=item["id"],
                                          item=json.dumps(item, indent=2), kind=kind, subject=subject,
                                          diff=item_diff(st), journal=m.journal_tail(),
                                          instructions=instructions), f"{kind}-{item['id']}")
    v = last_json(final) or {"verdict": "revise", "notes": "(advisor reply had no verdict JSON)\n" + final[-2000:]}
    m.journal(f"advisor ({kind})", f"**{v.get('verdict')}**: {v.get('notes', '')}")
    return v


REVIEW_RUN = ("The worker wants to run this on the host (outside its sandbox). Read the script(s). Approve only "
              "if it is safe (no destructive commands, writes only under the repo or /tmp, private llama-server on "
              "port 8089 if it starts one, never touches the live services on :8080/:11435), and it plausibly "
              "measures what the item needs. Otherwise say exactly what to fix.")
REVIEW_INFRA = ("The worker wants to apply this entry to the live server it runs on. The orchestrator will "
                "health-check and auto-rollback, but approve only if the measurements in the repo justify it "
                "and the change is limited to what they support.")
REVIEW_DONE = ("The worker says this item is done. Check its acceptance criteria against the files in the repo "
               "(read them). Approve only if met and the numbers are real (traceable to results files).")
REVIEW_WRITEUP = ("This is the milestone write-up for the public research site. Fact-check every number and claim "
                  "against the results files, check the summaries are <=200 words and readable, and that "
                  "series/project pages were updated per site/AUTHORING.md. Approve only if accurate.")


# ---- the state machine ----

def do_plan(m, st):
    final, _ = call_cloud("advisor", fill("planner.md", milestone=m.spec), "plan")
    plan = last_json(final)
    if not plan or not plan.get("items"):
        m.journal("advisor (plan)", "No usable plan JSON:\n\n" + final[-3000:])
        return
    m.dir.mkdir(parents=True, exist_ok=True)
    (m.dir / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    m.journal("advisor (plan)", "\n".join(f"{i + 1}. **{it['title']}**: {it['acceptance']}"
                                          for i, it in enumerate(plan["items"])))
    st.update(phase="work", item=0, round=0, reviews=0, base=git("rev-parse", "HEAD"))
    m.save(st)
    commit(f"autopilot({m.name}): plan")
    maybe_publish_status(force=True)


def next_item(m, st, dropped=False):
    plan = m.plan()
    if dropped:
        st.setdefault("dropped", []).append(plan[st["item"]]["id"])
    st.update(item=st["item"] + 1, round=0, reviews=0, base=git("rev-parse", "HEAD"))
    if st["item"] >= len(plan):
        st["phase"] = "publish"
    m.save(st)


def do_work(m, st):
    plan = m.plan()
    item = plan[st["item"]]
    if not watchdog(m):
        return
    st["round"] += 1
    m.save(st)
    if st["round"] > CFG["worker_rounds_per_item"]:
        m.journal("orchestrator", f"Item `{item['id']}` used all {CFG['worker_rounds_per_item']} rounds; dropped.")
        next_item(m, st, dropped=True)
        commit(f"autopilot({m.name}): drop {item['id']}")
        return
    prompt = fill("worker.md", protected=", ".join(CFG["protected_paths"]), milestone=m.spec,
                  plan="\n".join(f"{i + 1}. {it['title']}" + (" ← current" if i == st["item"] else "")
                                 for i, it in enumerate(plan)),
                  item_id=item["id"], round=st["round"], max_rounds=CFG["worker_rounds_per_item"],
                  timeout_min=CFG["worker_timeout_min"],
                  item=f"**{item['title']}**\n\n{item['instructions']}\n\n**Acceptance:** {item['acceptance']}",
                  journal=m.journal_tail())
    commit(f"autopilot({m.name}): before {item['id']} round {st['round']}")
    pre = git("rev-parse", "HEAD")
    final, e = call_worker(prompt, f"{item['id']}-r{st['round']}")
    enforce_protected(m, pre)
    req = last_json(final) or {"request": "continue", "note": "(no request JSON)"}
    m.journal(f"worker (Bonsai), round {st['round']}", final or f"(no final message; errors: {e['errors'][:3]})")
    if not last_json(final):
        stat = git("diff", "--stat", pre) or "(no file changes)"
        m.journal("orchestrator", "The session ended without a request (cut off by the time limit or an "
                  f"error), so nothing ran. Files changed in it:\n\n```\n{stat}\n```\n\nNext session: don't "
                  "polish further. Check those files briefly, then end early with a `run` request. Running "
                  "the script is how you test it.")
    kind = req.get("request")
    if kind == "run":
        v = review(m, item, "run request", f"```json\n{json.dumps(req, indent=2)}\n```", REVIEW_RUN, st)
        if v.get("verdict") == "approve":
            m.journal("orchestrator", execute_run(m, item, req, st["round"]))
    elif kind == "infra":
        v = review(m, item, "infra request", f"```json\n{json.dumps(req, indent=2)}\n```", REVIEW_INFRA, st)
        if v.get("verdict") == "approve":
            m.journal("orchestrator", execute_infra(m, req))
    elif kind == "done":
        writeup = st["item"] == len(plan) - 1
        if writeup:
            chk = subprocess.run([sys.executable, str(WT / "tools/check_site.py"), str(WT / "site")],
                                 capture_output=True, text=True)
            if chk.returncode:
                m.journal("orchestrator", f"check_site.py failed:\n\n```\n{chk.stdout[-2000:]}\n```")
                commit(f"autopilot({m.name}): {item['id']} round {st['round']}")
                return
        v = review(m, item, "write-up" if writeup else "finished item", req.get("summary", ""),
                   REVIEW_WRITEUP if writeup else REVIEW_DONE, st)
        if v.get("verdict") == "approve":
            commit(f"autopilot({m.name}): {item['id']} approved")
            next_item(m, st)
        else:
            st["reviews"] += 1
            if st["reviews"] >= CFG["review_rounds_per_item"]:
                m.journal("orchestrator", f"Item `{item['id']}` failed review {st['reviews']} times; dropped.")
                next_item(m, st, dropped=True)
            m.save(st)
    commit(f"autopilot({m.name}): {item['id']} round {st['round']}")
    maybe_publish_status()


def do_publish(m, st):
    try:
        push(WT, f"auto/{m.name}", f"{CFG['remote']}/main...HEAD")
        publish(f"Merge autopilot milestone {m.name}", merge_branch=f"auto/{m.name}")
    except RuntimeError as e:
        block(m, f"merge/publish failed: {e}")
        return
    st["phase"] = "done"
    m.save(st)
    m.journal("orchestrator", "Milestone merged into main and published.")
    commit(f"autopilot({m.name}): done")
    push(WT, f"auto/{m.name}", f"{CFG['remote']}/main...HEAD")


def current():
    for name in CFG["milestones"]:
        m = Milestone(name)
        if m.status()["phase"] != "done":
            return m
    return None


def tick():
    global WT
    m = current()
    if m is None:
        return "idle"
    ensure_worktree(m)
    WT = m.wt
    st = m.status()
    if st["phase"] == "blocked":
        return "blocked"
    try:
        if st["phase"] == "plan":
            do_plan(m, st)
        elif st["phase"] == "work":
            do_work(m, st)
        elif st["phase"] == "publish":
            do_publish(m, st)
    except OutOfBudget:
        m.journal("orchestrator", "Cloud call budget for today is spent; pausing until tomorrow.")
        commit(f"autopilot({m.name}): out of budget")
        maybe_publish_status(force=True)
        return "budget"
    if m.status()["phase"] != "blocked":
        try:
            push(WT, f"auto/{m.name}", f"{CFG['remote']}/main...HEAD")
        except RuntimeError as e:
            block(m, str(e))
    return m.status()["phase"]


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    RT.mkdir(parents=True, exist_ok=True)
    if cmd == "status":
        for name in CFG["milestones"]:
            m = Milestone(name)
            print(name, json.dumps(m.status()) if m.status_file.exists() else "(not started)")
        print("cloud calls left today:", budget_left())
        return
    lock = open(RT / "lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("another autopilot is running")
    if cmd == "unblock":
        global WT
        m = current()
        WT = m.wt if m else None
        if m and m.status()["phase"] == "blocked":
            st = m.status()
            st["phase"] = "work" if m.plan() else "plan"
            st.pop("blocked", None)
            m.save(st)
            m.journal("orchestrator", "Unblocked by the user.")
            commit(f"autopilot({m.name}): unblocked")
        return
    if cmd == "tick":
        print(tick())
        return
    if cmd == "loop":
        crashes = 0
        while True:
            try:
                state = tick()
                crashes = 0
            except Exception as e:  # keep the service alive; record and back off
                say(f"tick failed: {type(e).__name__}: {e}")
                state, crashes = "error", crashes + 1
                if crashes >= 3 and WT is not None:  # the same step keeps failing: stop and say so
                    try:
                        block(current(), f"tick crashed 3 times in a row; last: {type(e).__name__}: {e}")
                        crashes = 0
                    except Exception as e2:
                        say(f"could not record the block: {e2}")
            if state in ("idle", "blocked", "budget", "error", "done"):
                time.sleep(1800 if state != "error" else 300)
        return
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
