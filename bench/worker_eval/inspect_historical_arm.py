#!/usr/bin/env python3
"""Read historical Bonsai worker provenance from the operative M1 lineage.

This is host-only and read-only: the sandbox worktree deliberately has no git
object store.  It examines every commit reachable from auto/M1-ngram before the
cloud-worker cutoff, rather than only commits which changed config.json (the
old inspector missed a still-in-force config).  It writes candidates and the
exact source file hashes for citation in the worker arm README.
"""
import datetime as dt
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
CUTOFF = dt.datetime.fromisoformat("2026-10-12T08:33:00-04:00")
OUT = ROOT / "bench" / "results" / dt.date.today().isoformat() / "worker_eval"
BRANCHES = ("auto/M1-ngram", "refs/heads/auto/M1-ngram", "origin/auto/M1-ngram")
CONFIG = "autopilot/config.json"
MODEL = "agent/models.bonsai-agent.json"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def show(commit, path):
    try:
        return git("show", f"{commit}:{path}")
    except subprocess.CalledProcessError:
        return None


def branch_tip():
    for branch in BRANCHES:
        try:
            return branch, git("rev-parse", "--verify", branch)
        except subprocess.CalledProcessError:
            pass
    raise SystemExit("operative M1 branch is not available")


def main():
    branch, tip = branch_tip()
    commits = git("rev-list", "--topo-order", "--date-order", tip).splitlines()
    rows = []
    seen_configs = set()
    for commit in commits:
        when = git("show", "-s", "--format=%cI", commit)
        if dt.datetime.fromisoformat(when) > CUTOFF:
            continue
        config_text = show(commit, CONFIG)
        if config_text is None:
            continue
        # Many commits retain the same configuration.  Cite the oldest relevant
        # commit once, so the report is compact but still on the M1 lineage.
        config_sha = hashlib.sha256(config_text.encode()).hexdigest()
        if config_sha in seen_configs:
            continue
        seen_configs.add(config_sha)
        try:
            config = json.loads(config_text)
            worker = config["roles"]["worker"]
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
        if worker.get("model") != "garden/bonsai-agent":
            continue
        model_text = show(commit, MODEL)
        if model_text is None:
            continue
        try:
            registration = json.loads(model_text)
        except json.JSONDecodeError:
            continue
        rows.append({
            "commit": commit,
            "commit_time": when,
            "lineage_branch": branch,
            "lineage_tip": tip,
            "config_path": CONFIG,
            "config_sha256": config_sha,
            "worker": worker,
            "worker_timeout_min": config.get("worker_timeout_min"),
            "worker_memory": config.get("worker_memory"),
            "model_registration_path": MODEL,
            "model_registration_sha256": hashlib.sha256(model_text.encode()).hexdigest(),
            "model_registration": registration,
        })
    # rev-list order is graph order, not timestamp order; make selection explicit.
    rows.sort(key=lambda row: row["commit_time"], reverse=True)
    stamp = dt.datetime.now().strftime("historical-arm-provenance-%Y%m%dT%H%M%S.json")
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / stamp
    target.write_text(json.dumps({
        "cutoff": CUTOFF.isoformat(),
        "branch": branch,
        "branch_tip": tip,
        "candidates": rows,
    }, indent=2) + "\n")
    print(target)
    if not rows:
        raise SystemExit("no Bonsai worker config found on operative M1 lineage")
    print(json.dumps(rows[0], indent=2))


if __name__ == "__main__":
    main()
