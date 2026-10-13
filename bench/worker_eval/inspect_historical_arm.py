#!/usr/bin/env python3
"""Read historical worker-arm provenance from git without changing the checkout.

Writes the last garden/bonsai worker config at or before the cloud-worker cutoff,
plus the model registration from that same commit.  This is a host-only diagnostic:
the sandbox intentionally has no git object store.
"""
import datetime as dt
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
CUTOFF = dt.datetime.fromisoformat("2026-10-12T08:33:00-04:00")
OUT = ROOT / "bench" / "results" / dt.date.today().isoformat() / "worker_eval"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main():
    rows = []
    commits = git("log", "--all", "--format=%H%x00%cI", "--", "autopilot/config.json").splitlines()
    for line in commits:
        commit, when = line.split("\x00")
        at = dt.datetime.fromisoformat(when)
        if at > CUTOFF:
            continue
        try:
            config_text = git("show", f"{commit}:autopilot/config.json")
            config = json.loads(config_text)
            worker = config["roles"]["worker"]
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
            continue
        if worker.get("model") != "garden/bonsai-agent":
            continue
        model_text = git("show", f"{commit}:agent/models.bonsai-agent.json")
        rows.append({
            "commit": commit,
            "commit_time": when,
            "config_path": "autopilot/config.json",
            "config_sha256": hashlib.sha256(config_text.encode()).hexdigest(),
            "worker": worker,
            "worker_timeout_min": config.get("worker_timeout_min"),
            "worker_memory": config.get("worker_memory"),
            "model_registration_path": "agent/models.bonsai-agent.json",
            "model_registration_sha256": hashlib.sha256(model_text.encode()).hexdigest(),
            "model_registration": json.loads(model_text),
        })
    rows.sort(key=lambda r: r["commit_time"], reverse=True)
    stamp = dt.datetime.now().strftime("historical-arm-provenance-%Y%m%dT%H%M%S.json")
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / stamp
    target.write_text(json.dumps({"cutoff": CUTOFF.isoformat(), "candidates": rows}, indent=2) + "\n")
    print(target)
    if not rows:
        raise SystemExit("no historical garden/bonsai worker config found")
    print(json.dumps(rows[0], indent=2))


if __name__ == "__main__":
    main()
