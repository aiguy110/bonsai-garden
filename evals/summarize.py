#!/usr/bin/env python3
"""Summarize an eval results dir: summarize.py DIR -> DIR/summary.md (also printed)."""
import collections
import json
import pathlib
import statistics
import sys

out = pathlib.Path(sys.argv[1])
recs = [json.loads(l) for l in (out / "results.jsonl").read_text().splitlines() if l.strip()]
man = json.loads((out / "manifest.json").read_text())


def mean(xs):
    xs = list(xs)
    return statistics.mean(xs) if xs else 0


def spread(xs):
    xs = list(xs)
    return f"{mean(xs):.0f} ± {statistics.pstdev(xs):.0f}" if len(xs) > 1 else f"{mean(xs):.0f}"


def role(r, name, key):
    return (r.get("llm") or {}).get(name, {}).get(key, 0)


lines = [f"# Eval summary: {out.name}", "",
         f"Started {man['started']}, pi {man['pi_version']}, bonsai-garden {man['bonsai_garden_commit'][:8]}"
         f"{' (dirty)' if man['bonsai_garden_dirty'] else ''}, {man['repeats']} repeats.", ""]
groups = collections.defaultdict(list)
for r in recs:
    groups[(r["task"], r["step"], r["arm"])].append(r)
check_names = sorted({c for r in recs for c in r["checks"]})

for task in sorted({r["task"] for r in recs}):
    lines += [f"## {task}", "",
              "| step | arm | n | pass | " + " | ".join(check_names) +
              " | wall s | turns | agent prefill tok | agent gen tok | mem calls | mem gen tok | queue wait s |",
              "|---" * (5 + len(check_names) + 7) + "|"]
    for (t, step, arm), rs in sorted(groups.items()):
        if t != task:
            continue
        n = len(rs)
        cells = [str(step), arm, str(n), f"{sum(r['pass'] for r in rs)}/{n}"]
        cells += [f"{sum(bool(r['checks'].get(c)) for r in rs)}/{n}" for c in check_names]
        cells += [spread(r["wall_s"] for r in rs), spread(r["turns"] for r in rs),
                  spread(role(r, "agent", "prompt_n") for r in rs),
                  spread(role(r, "agent", "predicted_n") for r in rs),
                  f"{mean(role(r, 'mem', 'requests') for r in rs):.1f}",
                  spread(role(r, "mem", "predicted_n") for r in rs),
                  f"{mean((role(r, 'agent', 'queue_wait_ms') + role(r, 'mem', 'queue_wait_ms')) / 1000 for r in rs):.1f}"]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    seq = collections.defaultdict(list)
    for r in recs:
        if r["task"] == task:
            seq[(r["arm"], r["rep"])].append(r)
    lines += ["Whole-sequence pass (all steps):", ""]
    for arm in sorted({a for a, _ in seq}):
        runs = [rs for (a, _), rs in seq.items() if a == arm]
        ok = sum(all(r["pass"] for r in rs) for rs in runs)
        lines.append(f"- {arm}: {ok}/{len(runs)}")
    lines.append("")

text = "\n".join(lines)
(out / "summary.md").write_text(text + "\n")
print(text)
