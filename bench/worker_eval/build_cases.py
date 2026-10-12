#!/usr/bin/env python3
"""Build the provenance-preserving cloud-worker corpus for the W1 replay.

This deliberately reads the autopilot call archive and journals; it never imports or
writes autopilot state.  It is run on the host because .runtime/calls is not part of
normal worktrees.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "bench" / "worker_eval"
CASES = OUT / "cases.jsonl"
INVENTORY = OUT / "inventory.json"
CANONICAL = "Bonsai 2 27B (Ternary-Bonsai-2-27B, 2-bit), a local model on this machine's GPU"
CUTOFF = dt.datetime.fromisoformat("2026-10-12T08:33:00-04:00")
HEADER = re.compile(r"^### ([^·]+) · ([^\n]+)$", re.M)
WORKER = re.compile(r"^worker \(([^)]+)\), round (\d+)$")
ADVISOR = re.compile(r"^advisor \(([^)]+)\)$")
LOG = re.compile(r"^(\d{8}-\d{6})-worker-(.+)-r(\d+)\.jsonl$")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def host_paths():
    home = pathlib.Path.home()
    base = pathlib.Path(os.environ.get("GARDEN_SOURCE", home / "Projects" / "bonsai-garden"))
    calls = pathlib.Path(os.environ.get("GARDEN_CALLS", base / "autopilot" / ".runtime" / "calls"))
    # The current checkout's journal is useful after a merged milestone; the auto
    # worktree copy is authoritative while a milestone is in progress.
    journals = [base / "autopilot" / "state" / "M1-ngram" / "journal.md",
                home / "Projects" / "bonsai-garden-auto" / "M1-ngram" / "autopilot" / "state" / "M1-ngram" / "journal.md",
                ROOT / "autopilot" / "state" / "M1-ngram" / "journal.md"]
    return calls, [p for i, p in enumerate(journals) if p.exists() and p not in journals[:i]]


def entries(path: pathlib.Path):
    text = path.read_text(errors="replace")
    hs = list(HEADER.finditer(text))
    result = []
    for i, h in enumerate(hs):
        try:
            when = dt.datetime.fromisoformat(h.group(1).strip())
        except ValueError:
            continue
        result.append({"when": when, "actor": h.group(2).strip(),
                       "body": text[h.end(): hs[i + 1].start() if i + 1 < len(hs) else len(text)].strip(),
                       "journal": str(path)})
    return result


def text_of(message):
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    return "".join(x.get("text", "") for x in content if isinstance(x, dict))


def log_data(path):
    first_user = final = None
    tool_request = None
    model = None
    for line in path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        msg = event.get("message") or {}
        if event.get("type") == "message_start" and msg.get("role") == "user" and first_user is None:
            first_user = text_of(msg)
        if event.get("type") == "message_end" and msg.get("role") == "assistant":
            if text_of(msg).strip(): final = text_of(msg)
        # pi's tool-call block is the strongest archival proof that submit_request
        # was used.  Its arguments may be an object or a JSON string.
        for block in msg.get("content", []) if isinstance(msg.get("content"), list) else []:
            if block.get("type") == "toolCall" and block.get("name") == "submit_request":
                args = block.get("arguments")
                try: tool_request = json.loads(args) if isinstance(args, str) else args
                except ValueError: pass
        model = model or event.get("model") or msg.get("model")
    return first_user, final, tool_request, model


def last_json(text):
    for block in reversed(re.findall(r"```json\s*(.*?)```", text, re.S)):
        try:
            obj = json.loads(block)
            if isinstance(obj, dict): return obj
        except ValueError: pass
    decoder = json.JSONDecoder()
    for i in reversed([i for i, c in enumerate(text) if c == "{"]):
        try:
            obj, _ = decoder.raw_decode(text[i:])
            if isinstance(obj, dict): return obj
        except ValueError: pass
    return None


def substitute(prompt):
    # The first worker-template line is intentionally the only alteration.  Do not
    # replace model mentions in journal material embedded later in the prompt.
    pat = r"(?m)^(You are the research worker for bonsai-garden, running as )(.+?)(\. The project)$"
    changed, n = re.subn(pat, r"\1" + CANONICAL + r"\3", prompt, count=1)
    if n != 1:
        raise ValueError("worker-description line was not found exactly once")
    return changed


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True).stdout.strip()


def commits():
    out = git("log", "--all", "--format=%H%x00%s")
    found = {}
    for line in out.splitlines():
        try: h, subject = line.split("\0", 1)
        except ValueError: continue
        m = re.fullmatch(r"autopilot\(([^)]+)\): before (.+) round (\d+)", subject)
        if m: found[(m.group(1), m.group(2), int(m.group(3)))] = (h, subject)
    return found


def parse_journal(paths):
    all_entries = sorted((e for p in paths for e in entries(p)), key=lambda e: e["when"])
    workers = {}
    advisors = []
    for e in all_entries:
        m = WORKER.match(e["actor"])
        if m:
            # Item is not present in the heading. Infer it from the request log name
            # later; timestamps and round disambiguate entries across plan items.
            e.update(model=m.group(1), round=int(m.group(2)))
            workers.setdefault(e["round"], []).append(e)
        if ADVISOR.match(e["actor"]):
            v = re.match(r"\*\*(approve|revise|reject)\*\*:\s*(.*)", e["body"], re.S)
            if v: advisors.append((e, v.group(1), v.group(2).strip()))
    return all_entries, workers, advisors


def associated_worker(workers, item, rnd, stamp):
    choices = workers.get(rnd, [])
    # Logs have second resolution and journal timestamps occur just after the call.
    # A 50 minute bound avoids accidentally attaching another item with the same round.
    target = dt.datetime.strptime(stamp, "%Y%m%d-%H%M%S").replace(tzinfo=CUTOFF.tzinfo)
    choices = sorted(choices, key=lambda e: abs((e["when"] - target).total_seconds()))
    return choices[0] if choices and abs((choices[0]["when"] - target).total_seconds()) < 3000 else None


def associated_advisor(all_entries, worker):
    start = all_entries.index(worker)
    for e in all_entries[start + 1:]:
        if WORKER.match(e["actor"]): break
        m = ADVISOR.match(e["actor"])
        if m:
            v = re.match(r"\*\*(approve|revise|reject)\*\*:\s*(.*)", e["body"], re.S)
            if v: return e, v.group(1), v.group(2).strip()
    return None


def build():
    calls, journals = host_paths()
    if not calls.is_dir(): raise SystemExit(f"call archive not found: {calls}")
    if not journals: raise SystemExit("M1-ngram journal not found (set GARDEN_SOURCE if needed)")
    all_entries, workers, _ = parse_journal(journals)
    starts = commits()
    rows, skipped = [], Counter()
    for path in sorted(calls.glob("*-worker-*.jsonl")):
        m = LOG.match(path.name)
        if not m: continue
        stamp, item, rnd = m.group(1), m.group(2), int(m.group(3))
        source_time = dt.datetime.strptime(stamp, "%Y%m%d-%H%M%S").replace(tzinfo=CUTOFF.tzinfo)
        if source_time < CUTOFF: skipped["before_cutoff"] += 1; continue
        prompt, final, tool_req, event_model = log_data(path)
        worker = associated_worker(workers, item, rnd, stamp)
        if not worker:
            skipped["no_journal_worker"] += 1; continue
        source_model = worker["model"] or event_model or "unknown"
        # This explicit exclusion protects against calls that created no useful work
        # during the Claude Max incident, even if a malformed journal was recoverable.
        if item == "spec-replay" and re.search(r"rate.?limit|usage.?limit|\b429\b", worker["body"], re.I):
            skipped["rate_limited"] += 1; continue
        journal_req = last_json(worker["body"])
        request, request_source = (tool_req, "tool") if tool_req else ((journal_req, "journal_request") if journal_req else (last_json(final or ""), "json_fallback"))
        if not prompt or not request or not isinstance(request, dict) or not request.get("request"):
            skipped["no_recoverable_request"] += 1; continue
        advisor = associated_advisor(all_entries, worker)
        if not advisor:
            skipped["no_advisor_verdict"] += 1; continue
        ae, verdict, notes = advisor
        key = ("M1-ngram", item, rnd)
        if key not in starts:
            skipped["no_start_commit"] += 1; continue
        changed = substitute(prompt)
        commit, subject = starts[key]
        rows.append({"case_id": f"m1-ngram-{item}-r{rnd}-{sha(str(path.resolve()) + sha(prompt))[:12]}",
          "milestone": "M1-ngram", "item": item, "round": rnd,
          "source_timestamp": source_time.isoformat(), "source_model": source_model,
          "start_commit": commit, "start_commit_subject": subject,
          "prompt": changed, "source_first_user_prompt_sha256": sha(prompt),
          "prompt_sha256": sha(changed), "event_log": str(path), "event_log_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
          "worker_description_from": re.search(r"running as (.+?)\. The project", prompt).group(1),
          "worker_description_to": CANONICAL, "request": request, "request_source": request_source,
          "advisor_timestamp": ae["when"].isoformat(), "advisor_verdict": verdict, "advisor_notes": notes,
          "journal": worker["journal"]})
    rows.sort(key=lambda r: (r["source_timestamp"], r["case_id"]))
    return rows, skipped


def validate(rows):
    errors = []
    ids = [r["case_id"] for r in rows]
    if len(ids) != len(set(ids)): errors.append("case IDs are not unique")
    if len(rows) < 20: errors.append(f"need >=20 cases, got {len(rows)}")
    if len({r["item"] for r in rows}) < 2: errors.append("need >=2 plan items")
    if any(dt.datetime.fromisoformat(r["source_timestamp"]) < CUTOFF for r in rows): errors.append("pre-cutoff row")
    if any(r["item"] == "spec-replay" and re.search(r"rate.?limit|usage.?limit|\b429\b", r["advisor_notes"], re.I) for r in rows): errors.append("included rate-limit failure")
    for r in rows:
        if not r["prompt"].strip() or not r["request"]: errors.append(f"empty prompt/request: {r['case_id']}")
        if r["prompt"].count(CANONICAL) != 1: errors.append(f"bad substitution count: {r['case_id']}")
        if r["advisor_timestamp"] < r["source_timestamp"]: errors.append(f"advisor precedes request: {r['case_id']}")
        subject = git("show", "-s", "--format=%s", r["start_commit"])
        expected = f"autopilot({r['milestone']}): before {r['item']} round {r['round']}"
        if subject != expected: errors.append(f"bad start commit: {r['case_id']}")
        # Audit proof: reconstruct the original only by changing the first line.
        original = re.sub(r"(?m)^(You are the research worker for bonsai-garden, running as )(.+?)(\. The project)$", r"\1" + r["worker_description_from"] + r"\3", r["prompt"], count=1)
        if sha(original) != r["source_first_user_prompt_sha256"]: errors.append(f"prompt provenance mismatch: {r['case_id']}")
    if rows and any(r["advisor_verdict"] == "revise" for r in rows) is False:
        # Eligible revise cases are checked during extraction: absent is informative,
        # not an unconditional error because a corpus could have none.
        print("warning: no revise cases included", file=sys.stderr)
    return errors


def inventory(rows, skipped):
    return {"schema_version": 1, "canonical_worker_description": CANONICAL,
      "included": len(rows), "counts": {"source_model": dict(Counter(r["source_model"] for r in rows)),
      "item": dict(Counter(r["item"] for r in rows)), "request_kind": dict(Counter(r["request"].get("request") for r in rows)),
      "advisor_verdict": dict(Counter(r["advisor_verdict"] for r in rows))}, "skipped": dict(skipped)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate the committed corpus without writing")
    args = ap.parse_args()
    rows, skipped = build()
    errors = validate(rows)
    inv = inventory(rows, skipped)
    rendered = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    if args.check:
        if not CASES.exists() or CASES.read_text() != rendered: errors.append("cases.jsonl is not the deterministic build output")
        if not INVENTORY.exists() or json.loads(INVENTORY.read_text()) != inv: errors.append("inventory.json is not the deterministic build output")
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        CASES.write_text(rendered)
        INVENTORY.write_text(json.dumps(inv, indent=2, sort_keys=True) + "\n")
    print(json.dumps(inv, indent=2, sort_keys=True))
    if errors:
        print("validation failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        raise SystemExit(1)

if __name__ == "__main__": main()
