#!/usr/bin/env python3
"""Build the provenance-preserving cloud-worker corpus for W1 replays.

This is host-only: it reads the call archive, one authoritative M1 journal, and git;
it never writes under autopilot.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "bench" / "worker_eval"
CASES, INVENTORY = OUT / "cases.jsonl", OUT / "inventory.json"
CANONICAL = "Bonsai 2 27B (Ternary-Bonsai-2-27B, 2-bit), a local model on this machine's GPU"
CUTOFF = dt.datetime.fromisoformat("2026-10-12T08:33:00-04:00")
HEADER = re.compile(r"^### ([^·]+) · ([^\n]+)$", re.M)
WORKER = re.compile(r"^worker \(([^)]+)\), round (\d+)$")
ADVISOR = re.compile(r"^advisor \(([^)]+)\)$")
LOG = re.compile(r"^(\d{8}-\d{6})-worker-(.+)-r(\d+)\.jsonl$")
DESCRIPTION = re.compile(r"(?m)^(You are the research worker for bonsai-garden, running as )(.+?)(\. The project)$")
RATE_LIMIT = re.compile(r"rate.?limit|usage.?limit|\b429\b", re.I)


def sha(text): return hashlib.sha256(text.encode()).hexdigest()
def bytes_sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def host_paths():
    home = pathlib.Path.home()
    base = pathlib.Path(os.environ.get("GARDEN_SOURCE", home / "Projects" / "bonsai-garden"))
    calls = pathlib.Path(os.environ.get("GARDEN_CALLS", base / "autopilot" / ".runtime" / "calls"))
    # Do not merge journal copies: identical historical entries otherwise interrupt
    # worker-to-advisor association.  The M1 worktree is preferred explicitly.
    candidates = [
        pathlib.Path(os.environ["GARDEN_M1_JOURNAL"]) if os.environ.get("GARDEN_M1_JOURNAL") else None,
        home / "Projects" / "bonsai-garden-auto" / "M1-ngram" / "autopilot" / "state" / "M1-ngram" / "journal.md",
        base / "autopilot" / "state" / "M1-ngram" / "journal.md",
        ROOT / "autopilot" / "state" / "M1-ngram" / "journal.md",
    ]
    for path in candidates:
        if path and path.exists(): return calls, path
    raise SystemExit("M1-ngram journal not found (set GARDEN_M1_JOURNAL if needed)")


def entries(path):
    text = path.read_text(errors="replace"); headers = list(HEADER.finditer(text)); result = []
    for i, header in enumerate(headers):
        try: when = dt.datetime.fromisoformat(header.group(1).strip())
        except ValueError: continue
        result.append({"when": when, "actor": header.group(2).strip(),
                       "body": text[header.end():headers[i + 1].start() if i + 1 < len(headers) else len(text)].strip()})
    return result


def text_of(message):
    content = message.get("content", "")
    return content if isinstance(content, str) else "".join(x.get("text", "") for x in content if isinstance(x, dict))


def log_data(path):
    first_user = final = None; tool_request = None; model = None
    raw = path.read_text(errors="replace")
    for line in raw.splitlines():
        try: event = json.loads(line)
        except ValueError: continue
        if not isinstance(event, dict) or not isinstance(event.get("message") or {}, dict): continue
        msg = event.get("message") or {}
        if event.get("type") == "message_start" and msg.get("role") == "user" and first_user is None: first_user = text_of(msg)
        if event.get("type") == "message_end" and msg.get("role") == "assistant" and text_of(msg).strip(): final = text_of(msg)
        blocks = msg.get("content", []) if isinstance(msg.get("content"), list) else []
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "toolCall" and block.get("name") == "submit_request":
                try: tool_request = json.loads(block["arguments"]) if isinstance(block.get("arguments"), str) else block.get("arguments")
                except (ValueError, TypeError): pass
        model = model or event.get("model") or msg.get("model")
    return first_user, final, tool_request, model, raw


def last_json(text):
    for block in reversed(re.findall(r"```json\s*(.*?)```", text, re.S)):
        try:
            value = json.loads(block)
            if isinstance(value, dict): return value
        except ValueError: pass
    decoder = json.JSONDecoder()
    for pos in reversed([i for i, char in enumerate(text) if char == "{"]):
        try:
            value, _ = decoder.raw_decode(text[pos:])
            if isinstance(value, dict): return value
        except ValueError: pass
    return None


def substitute(prompt):
    matches = list(DESCRIPTION.finditer(prompt))
    if len(matches) != 1: raise ValueError(f"expected exactly one worker description, got {len(matches)}")
    return DESCRIPTION.sub(r"\1" + CANONICAL + r"\3", prompt, count=1), matches[0].group(2)


START_COMMIT_MAX_AGE = 300  # seconds; commit() skips unchanged trees, so older same-subject commits are stale


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    return p.stdout.strip()


def commits():
    # Keep every candidate: repeated plan rounds occur in history.  Selection is
    # tied to the call timestamp, rather than whichever ref git log happened to see last.
    output = git("log", "--all", "--format=%H%x00%aI%x00%s")
    found = {}
    for line in output.splitlines():
        try: commit, stamp, subject = line.split("\0", 2); when = dt.datetime.fromisoformat(stamp)
        except ValueError: continue
        match = re.fullmatch(r"autopilot\(([^)]+)\): before (.+) round (\d+)", subject)
        if match: found.setdefault((match.group(1), match.group(2), int(match.group(3))), []).append((when, commit, subject))
    return found


def select_commit(candidates, source_time):
    eligible = [c for c in candidates if c[0] <= source_time]
    if not eligible: return None
    latest = max(c[0] for c in eligible); winners = [c for c in eligible if c[0] == latest]
    return winners[0] if len(winners) == 1 else None


def workers_and_advisors(journal_entries):
    workers = []
    for i, entry in enumerate(journal_entries):
        match = WORKER.match(entry["actor"])
        if match: workers.append((i, entry, match.group(1), int(match.group(2))))
    return workers


def associated_worker(workers, rnd, source_time, next_start):
    # Window association: first `worker (...), round <n>` entry at/after this log's start
    # and before the next worker log's start.  Orphan logs (no entry) match nothing.
    for index, entry, model, round_ in workers:
        if round_ == rnd and entry["when"] >= source_time and (next_start is None or entry["when"] < next_start):
            return (0, index, entry, model)
    return None


def advisor_labels(kind):
    # autopilot.py:831-855: run/infra are reviewed as "<kind> request"; done as
    # "finished item" or "write-up"; continue and stuck get no review.
    return {"run": {"advisor (run request)"}, "infra": {"advisor (infra request)"},
            "done": {"advisor (finished item)", "advisor (write-up)"}}.get(kind, set())


def event_errors(path):
    spec = importlib.util.spec_from_file_location("garden_evals_run", ROOT / "evals" / "run.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.parse_events(pathlib.Path(path))["errors"]


def associated_advisor(journal_entries, worker_index, kind):
    expected = advisor_labels(kind)
    for entry in journal_entries[worker_index + 1:]:
        if WORKER.match(entry["actor"]): break
        if entry["actor"] not in expected: continue
        verdict = re.match(r"\*\*(approve|revise|reject)\*\*:\s*(.*)", entry["body"], re.S)
        if verdict: return entry, verdict.group(1), verdict.group(2).strip()
    return None


def same_json(a, b): return json.dumps(a, sort_keys=True, separators=(",", ":")) == json.dumps(b, sort_keys=True, separators=(",", ":"))


def build():
    calls, journal = host_paths()
    if not calls.is_dir(): raise SystemExit(f"call archive not found: {calls}")
    journal_entries = entries(journal); workers = workers_and_advisors(journal_entries); starts = commits()
    rows, skipped, eligible_revise = [], Counter(), 0
    claimed = {}
    # Scope to M1 logs: milestone heading of the prompt, and not after the last journal entry.
    last_entry = max(e["when"] for e in journal_entries)
    def in_scope(p):
        when = dt.datetime.strptime(LOG.match(p.name).group(1), "%Y%m%d-%H%M%S").replace(tzinfo=CUTOFF.tzinfo)
        if when > last_entry: return False
        head = log_data(p)[0] or ""
        return re.search(r"^## Milestone\s+# M1:", head, re.M) is not None
    logs = sorted(p for p in calls.glob("*-worker-*.jsonl") if LOG.match(p.name) and in_scope(p))
    starts_of = [dt.datetime.strptime(LOG.match(p.name).group(1), "%Y%m%d-%H%M%S").replace(tzinfo=CUTOFF.tzinfo) for p in logs]
    for n, path in enumerate(logs):
        match = LOG.match(path.name)
        next_start = starts_of[n + 1] if n + 1 < len(logs) else None
        stamp, item, rnd = match.group(1), match.group(2), int(match.group(3))
        source_time = dt.datetime.strptime(stamp, "%Y%m%d-%H%M%S").replace(tzinfo=CUTOFF.tzinfo)
        if source_time < CUTOFF - dt.timedelta(hours=1): skipped["before_cutoff"] += 1; continue
        prompt, final, tool_req, event_model, raw = log_data(path)
        worker_match = associated_worker(workers, rnd, source_time, next_start)
        if not worker_match: skipped["no_journal_worker"] += 1; continue
        _, worker_index, worker, source_model = worker_match
        if worker_index in claimed: raise SystemExit(f"journal worker entry claimed by two logs: {claimed[worker_index]} and {path.name}")
        claimed[worker_index] = path.name
        header = re.search(r"^## Current item: (.+?), round (\d+)", prompt or "", re.M)
        if not header or header.group(1).strip() != item or int(header.group(2)) != rnd: skipped["prompt_item_mismatch"] += 1; continue
        if worker["when"] < CUTOFF or "bonsai" in (source_model or "").lower(): skipped["before_cutoff_or_bonsai"] += 1; continue
        if any(RATE_LIMIT.search(str(e)) for e in event_errors(path)) or RATE_LIMIT.search(worker["body"]): skipped["rate_limited"] += 1; continue
        fallback, journal_req = last_json(final or ""), last_json(worker["body"])
        # Event evidence wins: submit_request, then final assistant JSON. Journal is
        # cross-check only and is never a request source.
        if isinstance(tool_req, dict): request, request_source = tool_req, "tool"
        elif isinstance(fallback, dict): request, request_source = fallback, "json_fallback"
        else: skipped["no_recoverable_request"] += 1; continue
        if not request.get("request"): skipped["malformed_request"] += 1; continue
        # The journal stores the request without `report` (autopilot.py:781-784).
        without_report = {k: v for k, v in request.items() if k != "report"}
        if journal_req is None: skipped["journal_request_missing"] += 1; continue
        if not same_json(without_report, journal_req): skipped["journal_request_mismatch"] += 1; continue
        if request["request"] in ("continue", "stuck"): skipped[f"unreviewed_{request['request']}_request"] += 1; continue
        advisor = associated_advisor(journal_entries, worker_index, request["request"])
        if not advisor: skipped["no_matching_advisor_verdict"] += 1; continue
        advisor_entry, verdict, notes = advisor
        if verdict == "revise": eligible_revise += 1
        try: changed, old_description = substitute(prompt or "")
        except ValueError: skipped["bad_worker_description"] += 1; continue
        if "bonsai" in old_description.lower(): skipped["bonsai_source"] += 1; continue
        selected = select_commit(starts.get(("M1-ngram", item, rnd), []), source_time)
        if not selected: skipped["no_unambiguous_start_commit"] += 1; continue
        commit_time, commit, subject = selected
        if (source_time - commit_time).total_seconds() > START_COMMIT_MAX_AGE: skipped["stale_start_commit"] += 1; continue
        rows.append({"case_id": f"m1-ngram-{item}-r{rnd}-{sha(path.name + sha(prompt))[:12]}",
          "milestone": "M1-ngram", "item": item, "round": rnd, "source_timestamp": source_time.isoformat(),
          "worker_entry_timestamp": worker["when"].isoformat(),
          "source_model": source_model or event_model or "unknown", "start_commit": commit, "start_commit_subject": subject,
          "source_first_user_prompt": prompt, "source_first_user_prompt_sha256": sha(prompt), "prompt": changed,
          "prompt_sha256": sha(changed), "event_log": str(path), "event_log_sha256": bytes_sha(path),
          "worker_description_from": old_description, "worker_description_to": CANONICAL,
          "request": request, "request_source": request_source, "advisor_timestamp": advisor_entry["when"].isoformat(),
          "advisor_actor": advisor_entry["actor"], "advisor_verdict": verdict, "advisor_notes": notes,
          "journal": str(journal), "journal_sha256": bytes_sha(journal)})
    rows.sort(key=lambda row: (row["source_timestamp"], row["case_id"]))
    return rows, skipped, eligible_revise


def validate(rows, eligible_revise):
    errors = []
    if len(rows) < 20: errors.append(f"need >=20 cases, got {len(rows)}")
    if len({r["item"] for r in rows}) < 2: errors.append("need >=2 plan items")
    if len({r["case_id"] for r in rows}) != len(rows): errors.append("case IDs are not unique")
    if eligible_revise and not any(r["advisor_verdict"] == "revise" for r in rows): errors.append("eligible revise case was not retained")
    for r in rows:
        if dt.datetime.fromisoformat(r["worker_entry_timestamp"]) < CUTOFF: errors.append(f"pre-cutoff: {r['case_id']}")
        if not r["prompt"].strip() or not isinstance(r["request"], dict) or not r["request"].get("request"): errors.append(f"empty prompt/request: {r['case_id']}")
        if r["request_source"] not in {"tool", "json_fallback"}: errors.append(f"bad request source: {r['case_id']}")
        if len(list(DESCRIPTION.finditer(r["source_first_user_prompt"]))) != 1: errors.append(f"source substitution count: {r['case_id']}")
        rebuilt, _ = substitute(r["source_first_user_prompt"])
        if "bonsai" in r["worker_description_from"].lower() or "bonsai" in r["source_model"].lower(): errors.append(f"bonsai source: {r['case_id']}")
        head = re.search(r"^## Current item: (.+?), round (\d+)", r["source_first_user_prompt"], re.M)
        if not head or head.group(1).strip() != r["item"] or int(head.group(2)) != r["round"]: errors.append(f"prompt item/round mismatch: {r['case_id']}")
        if rebuilt != r["prompt"] or sha(r["source_first_user_prompt"]) != r["source_first_user_prompt_sha256"]: errors.append(f"prompt provenance mismatch: {r['case_id']}")
        if r["advisor_actor"] not in advisor_labels(r["request"]["request"]): errors.append(f"advisor type mismatch: {r['case_id']}")
        if dt.datetime.fromisoformat(r["advisor_timestamp"]) < dt.datetime.fromisoformat(r["worker_entry_timestamp"]): errors.append(f"advisor precedes request: {r['case_id']}")
        if any(RATE_LIMIT.search(str(e)) for e in event_errors(r["event_log"])): errors.append(f"rate-limit failure included: {r['case_id']}")
        subject = git("show", "-s", "--format=%s", r["start_commit"])
        if subject != f"autopilot({r['milestone']}): before {r['item']} round {r['round']}": errors.append(f"bad start commit: {r['case_id']}")
        try: age = (dt.datetime.fromisoformat(r["source_timestamp"]) - dt.datetime.fromisoformat(git("show", "-s", "--format=%aI", r["start_commit"]))).total_seconds()
        except ValueError: age = None
        if age is None or not 0 <= age <= START_COMMIT_MAX_AGE: errors.append(f"start commit age out of range: {r['case_id']}")
    return errors


def inventory(rows, skipped, eligible_revise):
    return {"schema_version": 1, "canonical_worker_description": CANONICAL, "included": len(rows),
      "counts": {"source_model": dict(Counter(r["source_model"] for r in rows)), "item": dict(Counter(r["item"] for r in rows)),
                 "request_kind": dict(Counter(r["request"]["request"] for r in rows)), "advisor_verdict": dict(Counter(r["advisor_verdict"] for r in rows))},
      "eligible_revise": eligible_revise, "skipped": dict(skipped)}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    rows, skipped, eligible_revise = build(); errors = validate(rows, eligible_revise); inv = inventory(rows, skipped, eligible_revise)
    rendered = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    if args.check:
        if not CASES.exists() or CASES.read_text() != rendered: errors.append("cases.jsonl is not deterministic build output")
        try: inventory_matches = INVENTORY.exists() and json.loads(INVENTORY.read_text()) == inv
        except json.JSONDecodeError: inventory_matches = False
        if not inventory_matches: errors.append("inventory.json is not deterministic build output")
    if errors:
        print(json.dumps(inv, indent=2, sort_keys=True)); print("validation failed:\n- " + "\n- ".join(errors), file=sys.stderr); raise SystemExit(1)
    if not args.check:
        OUT.mkdir(parents=True, exist_ok=True); CASES.write_text(rendered); INVENTORY.write_text(json.dumps(inv, indent=2, sort_keys=True) + "\n")
    print(json.dumps(inv, indent=2, sort_keys=True))

if __name__ == "__main__": main()
