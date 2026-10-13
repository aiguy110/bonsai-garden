#!/usr/bin/env python3
"""Read historical Bonsai worker provenance from the operative M1 first-parent line.

Host-only and read-only.  Historical snapshots did not necessarily use today's
``autopilot/config.json`` path, so this inspector discovers JSON config and model
registration paths in each tree instead of assuming a path.  It writes the full
selection trail: the first-parent commit immediately before the first cloud case,
then any earlier first-parent snapshot that configures garden/bonsai-agent.
"""
import datetime as dt
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
CASES = ROOT / "bench" / "worker_eval" / "cases.jsonl"
OUT = ROOT / "bench" / "results" / dt.date.today().isoformat() / "worker_eval"
BRANCHES = ("auto/M1-ngram", "refs/heads/auto/M1-ngram", "origin/auto/M1-ngram")


def git(*args, check=True):
    p = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    if check and p.returncode:
        raise subprocess.CalledProcessError(p.returncode, ["git", *args], p.stdout, p.stderr)
    return p.stdout.strip()


def show(commit, path):
    return git("show", f"{commit}:{path}", check=False) or None


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def branch_tip():
    for branch in BRANCHES:
        tip = git("rev-parse", "--verify", branch, check=False)
        if tip:
            return branch, tip
    raise SystemExit("operative M1 branch is not available")


def first_cloud_start():
    rows = [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]
    if not rows:
        raise SystemExit("cases.jsonl has no rows")
    row = min(rows, key=lambda r: r["source_timestamp"])
    return row["start_commit"], row["source_timestamp"], row["case_id"]


def json_paths(commit):
    return [p for p in git("ls-tree", "-r", "--name-only", commit).splitlines()
            if p.endswith(".json")]


def worker_configs(commit):
    """Return JSON role configs, including non-Bonsai ones to expose a switch."""
    found = []
    for path in json_paths(commit):
        text = show(commit, path)
        if not text:
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            continue
        worker = value.get("roles", {}).get("worker") if isinstance(value, dict) else None
        if isinstance(worker, dict) and isinstance(worker.get("model"), str):
            found.append((path, text, value, worker))
    return found


def is_bonsai(worker):
    # Historical configs used a provider/model string, but retain the broad test
    # so the report remains useful if an older spelling is discovered.
    return "bonsai" in worker.get("model", "").lower()


def model_registrations(commit):
    found = []
    for path in json_paths(commit):
        text = show(commit, path)
        if not text or "bonsai-agent" not in text:
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("id") == "bonsai-agent":
            found.append((path, text, value))
    return found


def harness_files(commit):
    """Hashes for the historical harness sources that supply non-JSON arm knobs."""
    paths = ("autopilot/autopilot.py", "autopilot/extensions/submit_request.ts")
    return [{"path": path, "sha256": sha(text)} for path in paths
            if (text := show(commit, path)) is not None]


def main():
    branch, tip = branch_tip()
    cloud_commit, cloud_time, cloud_case = first_cloud_start()
    # These are ordered oldest -> newest and identify the operative line, not an
    # arbitrary merged ancestor.  Include the parent of the first cloud start,
    # which is the state immediately before that round began.
    line = git("rev-list", "--first-parent", "--reverse", tip).splitlines()
    if cloud_commit not in line:
        raise SystemExit(f"cloud start commit {cloud_commit} is not on {branch} first-parent line")
    cloud_index = line.index(cloud_commit)
    pre_cloud = line[max(0, cloud_index - 1)]
    examined = line[:cloud_index]
    candidates = []
    # Record every role-config state transition on the operative line.  The prior
    # implementation searched only for an exact Bonsai literal, which made a
    # failed search opaque: this trail proves both the selected snapshot and the
    # switch immediately following it.
    worker_states = []
    config_snapshots = []
    previous = None
    previous_config = None
    for commit in examined:
        # Keep raw historical autopilot config transitions too.  Older revisions
        # may predate the current roles.worker layout; their exact JSON is the
        # evidence needed to interpret a legacy worker spelling.
        raw_config = show(commit, "autopilot/config.json")
        if raw_config and raw_config != previous_config:
            try:
                config_value = json.loads(raw_config)
            except json.JSONDecodeError:
                config_value = {"unparseable": True}
            config_snapshots.append({
                "commit": commit,
                "commit_time": git("show", "-s", "--format=%cI", commit),
                "path": "autopilot/config.json",
                "sha256": sha(raw_config),
                "value": config_value,
            })
            previous_config = raw_config
        configs = worker_configs(commit)
        state = [(path, worker) for path, _text, _config, worker in configs]
        fingerprint = json.dumps(state, sort_keys=True)
        if fingerprint != previous:
            worker_states.append({
                "commit": commit,
                "commit_time": git("show", "-s", "--format=%cI", commit),
                "workers": [{"path": path, "value": worker} for path, worker in state],
            })
            previous = fingerprint
    for commit in reversed(examined):
        configs = [(x) for x in worker_configs(commit) if is_bonsai(x[3])]
        if not configs:
            continue
        registrations = model_registrations(commit)
        for config_path, config_text, config, worker in configs:
            candidates.append({
                "commit": commit,
                "commit_time": git("show", "-s", "--format=%cI", commit),
                "config_path": config_path,
                "config_sha256": sha(config_text),
                "worker": worker,
                "worker_timeout_min": config.get("worker_timeout_min"),
                "worker_memory": config.get("worker_memory"),
                "model_registrations": [{"path": path, "sha256": sha(text), "value": value}
                                        for path, text, value in registrations],
                "harness_files": harness_files(commit),
            })
        # The nearest Bonsai state is the provenance source; preserve the
        # transition trail separately instead of timestamp-ranking ancestors.
        break
    report = {
        "selection": "nearest first-parent Bonsai configuration before first cloud case start",
        "branch": branch, "branch_tip": tip,
        "first_cloud_case": cloud_case, "first_cloud_timestamp": cloud_time,
        "first_cloud_start_commit": cloud_commit,
        "pre_cloud_first_parent_commit": pre_cloud,
        "first_parent_commits_examined": len(examined),
        "candidates": candidates,
        "worker_state_transitions": worker_states,
        "autopilot_config_transitions": config_snapshots,
        "pre_cloud_json_paths": json_paths(pre_cloud),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / dt.datetime.now().strftime("historical-arm-provenance-%Y%m%dT%H%M%S.json")
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(target)
    if not candidates:
        raise SystemExit("no Bonsai worker config found before first cloud case; inspect pre_cloud_json_paths")
    print(json.dumps(candidates[0], indent=2))


if __name__ == "__main__":
    main()
