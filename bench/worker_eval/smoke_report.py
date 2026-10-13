#!/usr/bin/env python3
"""Write smoke.md for the W2 smoke run: one row per smoke arm.

  python3 bench/worker_eval/smoke_report.py DIR      (DIR = bench/results/<date>/worker-eval-w2-smoke)

Per arm: record.json found, extension load errors (lines of stderr.txt / events.jsonl that mention an
extension failing to load; the recon has no exact loader string, so the pattern is generic and the
matching lines are quoted), and the mechanism evidence from ext.jsonl.
"""
import json
import pathlib
import re
import sys

LOAD_ERR = re.compile(r"(failed|error|cannot|unable|could not)[^\n]{0,80}(extension|loading)|(extension|loading)[^\n]{0,80}(failed|error|cannot|unable)"
                      r"|Cannot find (module|package)|ERR_MODULE_NOT_FOUND", re.I)
CASE_GLOB = "*/r*/"


def jl(p):
    out = []
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def evidence(arm, ext, attempt):
    by = lambda e, ev=None: [x for x in ext if x.get("ext") == e and (ev is None or x.get("event") == ev)]
    if "think-drop" in arm:
        strips = [x for x in by("drop_old_thinking") if x.get("removed_chars", 0) > 0]
        return f"{len(strips)} strips, removed_chars total {sum(x['removed_chars'] for x in strips)}", bool(strips)
    if "reasoning-budget" in arm:
        reqs = by("reasoning_budget")
        msg = False
        if "smoke" in arm:  # budget message inside a thinking block of a model reply
            for line in (attempt / "events.jsonl").read_text().splitlines() if (attempt / "events.jsonl").exists() else []:
                if "Thinking budget reached" in line and '"thinking"' in line:
                    msg = True
                    break
        fields = sorted({f for x in reqs for f in x.get("fields", [])})
        return f"{len(reqs)} requests, fields {fields}, budget message in a thinking block: {msg if 'smoke' in arm else 'n/a'}", \
            bool(reqs) and (msg or "smoke" not in arm)
    if "session-budget" in arm:
        w, b = by("session_budget", "warn"), by("session_budget", "block")
        return f"{len(w)} warn, {len(b)} block events", bool(w) and bool(b)
    if "hashline" in arm:
        tools = [x for x in by("tool_audit", "tools")]
        added = sorted({t.get("name", str(t)) if isinstance(t, dict) else str(t) for x in tools for t in x.get("tools", [])})
        rec = json.loads((attempt / "record.json").read_text()) if (attempt / "record.json").exists() else {}
        used = {k: v for k, v in (rec.get("tools") or {}).items() if "hash" in k.lower() or k == "edit"}
        return f"tool list {added}; edit-like calls {used}", any("hash" in a.lower() for a in added)
    return f"{len(ext)} ext lines", True


def main(argv):
    root = pathlib.Path(argv[0])
    rows = ["# W2 smoke run", "", f"Source: {root}", "",
            "| arm | record.json | extension load errors | mechanism evidence | ok |", "|---|---|---|---|---|"]
    for armdir in sorted(p for p in root.iterdir() if p.is_dir()):
        attempts = sorted(armdir.glob(CASE_GLOB))
        if not attempts:
            rows.append(f"| {armdir.name} | not run | - | - | - |")
            continue
        a = attempts[0]
        has_rec = (a / "record.json").exists()
        err_lines = [l.strip()[:200] for f in ("stderr.txt", "events.jsonl") for l in
                     ((a / f).read_text().splitlines() if (a / f).exists() else []) if LOAD_ERR.search(l) and "tool_execution" not in l][:3]
        text, ok = evidence(armdir.name, jl(a / "ext.jsonl"), a)
        rows.append(f"| {armdir.name} | {'yes' if has_rec else 'NO'} | {'; '.join(err_lines).replace('|', '/') or 'none'} | {text} | "
                    f"{'yes' if ok and has_rec and not err_lines else 'NO'} |")
    (root / "smoke.md").write_text("\n".join(rows) + "\n")
    print("\n".join(rows))


if __name__ == "__main__":
    main(sys.argv[1:])
