#!/usr/bin/env python3
"""Compare worker-eval arms with a baseline (W2).

  python3 bench/worker_eval/compare.py --baseline DIR [--baseline DIR2] --arm DIR [--arm DIR ...] --out PREFIX

DIR is a run output directory (results.jsonl, <case>/r<n>/{record.json,tap.jsonl,ext.jsonl},
manifest-*.json). The first --baseline is the one every arm is compared with (the honest
baseline); an optional second is the W1 run. Writes PREFIX.json and PREFIX.md. Deterministic:
bootstrap seed 20261013, 10000 draws, resampling cases (both repeats of a case move together).

spread S for a metric = the baseline's |repeat-1 - repeat-2| value; with a second baseline,
max(S, |baseline - second baseline|). beyond_spread = the 95% CI excludes 0 AND |delta| > S.
"""
import argparse
import json
import pathlib
import random
import statistics
import sys
from collections import Counter

SEED, DRAWS = 20261013, 10000
KINDS = ("run", "infra", "continue", "done", "stuck", "none")
METRICS = ("valid", "kind_match", "median_wall_s")


def load_dir(d):
    d = pathlib.Path(d)
    recs = {}
    for f in sorted(d.glob("*/r*/record.json")):
        r = json.loads(f.read_text())
        r["_dir"] = f.parent
        recs[(r["case_id"], r["repeat"])] = r
    if not recs and (d / "results.jsonl").exists():
        for line in (d / "results.jsonl").read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                r["_dir"] = d / r["case_id"] / f"r{r['repeat']}"
                recs[(r["case_id"], r["repeat"])] = r
    manifests = [json.loads(m.read_text()) for m in sorted(d.glob("manifest-*.json"))]
    return {"dir": str(d), "records": [recs[k] for k in sorted(recs)], "manifests": manifests}


def jsonl(path):
    out = []
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def med(xs):
    return round(statistics.median(xs), 3) if xs else None


def is_edit_like(tool):
    return tool == "edit" or "hashline" in tool.lower() or tool.lower().startswith("hash")


def summarize(run):
    recs = run["records"]
    n = len(recs)
    kinds = Counter((r.get("replay_kind") or "none") for r in recs)
    calls, errs = Counter(), Counter()
    flags = Counter()
    ext = Counter()
    per = {"decode_s": [], "prefill_s": [], "predicted_n": [], "prompt_n": [], "max_prompt_tokens": []}
    for r in recs:
        calls.update(r.get("tools") or {})
        errs.update(r.get("tool_errors") or {})
        for f in ("timeout", "context_overflow", "output_limit"):
            flags[f] += bool(r.get(f))
        no_req = r.get("request") is None
        flags["no_request"] += no_req
        flags["invalid"] += (not no_req) and not r.get("valid_request")
        for e in jsonl(r["_dir"] / "ext.jsonl"):
            ext[f"{e.get('ext')}:{e.get('event', 'action')}"] += 1
            if e.get("removed_chars"):
                ext[f"{e.get('ext')}:removed_chars"] += e["removed_chars"]
            if e.get("removed_blocks"):
                ext[f"{e.get('ext')}:removed_blocks"] += e["removed_blocks"]
        tap = jsonl(r["_dir"] / "tap.jsonl")
        if tap:
            t = [x.get("timings") or {} for x in tap]
            per["decode_s"].append(sum(x.get("predicted_ms", 0) for x in t) / 1000)
            per["prefill_s"].append(sum(x.get("prompt_ms", 0) for x in t) / 1000)
            per["predicted_n"].append(sum(x.get("predicted_n", 0) for x in t))
            per["prompt_n"].append(sum(x.get("prompt_n", 0) for x in t))
            per["max_prompt_tokens"].append(max((x.get("usage") or {}).get("prompt_tokens", 0) for x in tap))
    valid = sum(bool(r.get("valid_request")) for r in recs)
    km = sum(bool(r.get("kind_match")) for r in recs)
    edit_calls = sum(v for k, v in calls.items() if is_edit_like(k))
    edit_errs = sum(v for k, v in errs.items() if is_edit_like(k))
    return {
        "dir": run["dir"], "arm": recs[0]["arm"] if recs else None, "records": n,
        "valid": valid, "kind_match": km, "kind_match_of_valid": sum(bool(r.get("kind_match")) for r in recs if r.get("valid_request")),
        "median_wall_s": med([r["wall_s"] for r in recs]), "median_turns": med([r["turns"] for r in recs]),
        "replay_kind": {k: kinds.get(k, 0) for k in KINDS},
        "flags": {k: flags.get(k, 0) for k in ("timeout", "context_overflow", "output_limit", "no_request", "invalid")},
        "tool_calls": dict(sorted(calls.items())), "tool_errors": dict(sorted(errs.items())),
        "edit_like_calls": edit_calls, "edit_like_errors": edit_errs,
        "edit_like_error_rate": round(edit_errs / edit_calls, 4) if edit_calls else None,
        "compaction_starts": sum(r.get("compaction_start") or 0 for r in recs),
        "tap_attempts": len(per["decode_s"]),
        "tap_median": {k: med(v) for k, v in per.items()},
        "tap_sum_predicted_n": sum(per["predicted_n"]),
        "ext_actions": dict(sorted(ext.items())),
    }


def by_case(run):
    out = {}
    for r in run["records"]:
        out.setdefault(r["case_id"], []).append(r)
    return out


def stat(recs, metric):
    if metric == "median_wall_s":
        return statistics.median([r["wall_s"] for r in recs]) if recs else None
    key = "valid_request" if metric == "valid" else "kind_match"
    return sum(bool(r.get(key)) for r in recs)


def per_repeat(run, metric):
    vals = []
    for rep in (1, 2):
        rs = [r for r in run["records"] if r["repeat"] == rep]
        vals.append(stat(rs, metric) if rs else None)
    return vals


def spread(baselines, metric):
    """S from the primary baseline's two repeats, widened by the gap to a second baseline."""
    a, b = per_repeat(baselines[0], metric)
    s = abs(a - b) if a is not None and b is not None else None
    if len(baselines) > 1 and s is not None:
        o = stat(baselines[1]["records"], metric)
        m = stat(baselines[0]["records"], metric)
        if o is not None and m is not None:
            # counts are per both repeats; compare per-repeat means so the units match S
            k0 = len({r["repeat"] for r in baselines[0]["records"]}) or 1
            k1 = len({r["repeat"] for r in baselines[1]["records"]}) or 1
            gap = abs(m / k0 - o / k1) if metric != "median_wall_s" else abs(m - o)
            s = max(s, gap)
    return s


def bootstrap(base, arm, metric):
    bc, ac = by_case(base), by_case(arm)
    cases = sorted(c for c in bc if c in ac and len(bc[c]) >= 1 and len(ac[c]) >= 1
                   and len(bc[c]) == len(ac[c]) == 2)
    if not cases:
        return None, 0

    def delta(sample):
        b = [r for c in sample for r in bc[c]]
        a = [r for c in sample for r in ac[c]]
        return stat(a, metric) - stat(b, metric)

    rng = random.Random(SEED)
    ds = sorted(delta([rng.choice(cases) for _ in cases]) for _ in range(DRAWS))
    return [round(ds[int(0.025 * DRAWS)], 3), round(ds[int(0.975 * DRAWS) - 1], 3)], len(cases)


def vs_baseline(base, arm, baselines):
    out = {}
    for m in METRICS:
        a, b = stat(arm["records"], m), stat(base["records"], m)
        ci, ncases = bootstrap(base, arm, m)
        d = None if a is None or b is None else round(a - b, 3)
        s = spread(baselines, m)
        beyond = bool(ci and d is not None and s is not None and (ci[0] > 0 or ci[1] < 0) and abs(d) > s)
        out[m] = {"arm": a, "baseline": b, "delta": d, "ci95": ci, "cases_in_bootstrap": ncases,
                  "spread": None if s is None else round(s, 3), "beyond_spread": beyond}
    return out


def manifest_warnings(runs):
    ref = runs[-1]["manifests"][-1] if runs[-1]["manifests"] else {}
    w1 = None
    for r in runs:
        for m in r["manifests"]:
            if r["records"] and r["records"][0].get("arm") == "bonsai-2026-10-12":
                w1 = m
    ref = w1 or ref
    warns = []
    for r in runs:
        for m in r["manifests"]:
            for k in ("model_sha256", "llama_swap_entry"):
                if k in ref and m.get(k) != ref.get(k):
                    warns.append(f"{r['dir']}: {k} differs from W1")
    return sorted(set(warns))


def render(report):
    L = ["# W2 comparison", ""]
    for w in report["warnings"]:
        L.append(f"WARNING: {w}")
    if report["warnings"]:
        L.append("")
    L += ["| arm | records | valid/44 | kind/44 | kind/valid | median wall s | median turns | run/infra/continue/done/stuck/none |",
          "|---|---|---|---|---|---|---|---|"]
    for name, s in report["arms"].items():
        k = s["replay_kind"]
        L.append(f"| {name} | {s['records']} | {s['valid']} | {s['kind_match']} | {s['kind_match_of_valid']} | "
                 f"{s['median_wall_s']} | {s['median_turns']} | {'/'.join(str(k[x]) for x in KINDS)} |")
    L += ["", "| arm | timeout | ctx overflow | output limit | no request | invalid | compactions | edit-like err rate |",
          "|---|---|---|---|---|---|---|---|"]
    for name, s in report["arms"].items():
        f = s["flags"]
        L.append(f"| {name} | {f['timeout']} | {f['context_overflow']} | {f['output_limit']} | {f['no_request']} | "
                 f"{f['invalid']} | {s['compaction_starts']} | {s['edit_like_error_rate']} |")
    L += ["", "| arm | decode s | prefill s | sum predicted_n | sum prompt_n | max prompt tokens |", "|---|---|---|---|---|---|"]
    for name, s in report["arms"].items():
        t = s["tap_median"]
        L.append(f"| {name} | {t['decode_s']} | {t['prefill_s']} | {t['predicted_n']} | {t['prompt_n']} | {t['max_prompt_tokens']} |")
    L += ["", "(tap columns are per-attempt medians)", "", "## Tool calls / errors", ""]
    for name, s in report["arms"].items():
        L.append(f"- {name}: " + ", ".join(f"{t} {s['tool_calls'][t]}/{s['tool_errors'].get(t, 0)} err" for t in s["tool_calls"]))
    L += ["", "## Extension actions", ""]
    for name, s in report["arms"].items():
        L.append(f"- {name}: {s['ext_actions'] or 'none'}")
    L += ["", "## Against the baseline", "",
          "| arm | metric | arm | baseline | delta | 95% CI | spread S | beyond spread |", "|---|---|---|---|---|---|---|---|"]
    for name, v in report["vs_baseline"].items():
        for m, x in v.items():
            L.append(f"| {name} | {m} | {x['arm']} | {x['baseline']} | {x['delta']} | {x['ci95']} | {x['spread']} | {x['beyond_spread']} |")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--baseline", action="append", required=True)
    ap.add_argument("--arm", action="append", default=[])
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    baselines = [load_dir(d) for d in args.baseline]
    arms = [load_dir(d) for d in args.arm]
    report = {"baseline": baselines[0]["dir"], "bootstrap": {"draws": DRAWS, "seed": SEED},
              "warnings": manifest_warnings(baselines + arms), "arms": {}, "vs_baseline": {}}
    for run in baselines + arms:
        s = summarize(run)
        report["arms"][f"{s['arm'] or run['dir']}"] = s
    for run in arms:
        name = report["arms"][summarize(run)["arm"] or run["dir"]]["arm"] or run["dir"]
        report["vs_baseline"][name] = vs_baseline(baselines[0], run, baselines)
    pathlib.Path(args.out + ".json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    pathlib.Path(args.out + ".md").write_text(render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
