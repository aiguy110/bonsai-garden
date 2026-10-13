#!/usr/bin/env python3
"""Summarize completed W1 worker-eval replay records.

Usage:
  python3 bench/worker_eval/summarize.py RESULT_DIR [--cases PATH]
  python3 bench/worker_eval/summarize.py --check RESULT_DIR [--cases PATH]

The normal form rewrites summary.json and summary.md from results.jsonl.  --check
requires exactly --repeat (default two) completed records for each case, no duplicate
(case_id, repeat) keys, an arm/bench-route manifest, and byte-for-byte reproducible
summary files.
"""
import argparse
import json
import math
import pathlib
import statistics
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KNOWN_FLAGS = ("timeout", "context_overflow", "output_limit")
ALL_FLAGS = KNOWN_FLAGS + ("rate_limit", "pi_exit_nonzero")


def read_jsonl(path):
    rows = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: invalid JSON: {exc.msg}") from exc
    return rows


def median(values):
    return statistics.median(values) if values else None


def display_stop(value):
    return value if value is not None else "(none)"


def metric(records):
    attempts = len(records)
    valid = [r for r in records if r.get("valid_request") is True]
    matched = [r for r in records if r.get("kind_match") is True]
    valid_matched = [r for r in valid if r.get("kind_match") is True]
    tools, tool_errors, stops = Counter(), Counter(), Counter()
    for row in records:
        tools.update(row.get("tools") or {})
        tool_errors.update(row.get("tool_errors") or {})
        stops[display_stop(row.get("last_stop"))] += 1
    def rate(n, d):
        return n / d if d else None
    return {
        "attempts": attempts,
        "valid_requests": len(valid),
        "valid_request_rate": rate(len(valid), attempts),
        "kind_matches": len(matched),
        "kind_match_rate_all_attempts": rate(len(matched), attempts),
        "kind_matches_among_valid_requests": len(valid_matched),
        "kind_match_rate_valid_requests": rate(len(valid_matched), len(valid)),
        "median_wall_s": median([r["wall_s"] for r in records if isinstance(r.get("wall_s"), (int, float))]),
        "median_turns": median([r["turns"] for r in records if isinstance(r.get("turns"), (int, float))]),
        "tool_calls_total": sum(int(r.get("tool_calls", 0) or 0) for r in records),
        "tool_calls_by_tool": dict(sorted(tools.items())),
        "tool_errors_total": sum(tool_errors.values()),
        "tool_errors_by_tool": dict(sorted(tool_errors.items())),
        "compactions": {
            "start_total": sum(int(r.get("compaction_start", 0) or 0) for r in records),
            "end_total": sum(int(r.get("compaction_end", 0) or 0) for r in records),
        },
        "last_stop_reasons": dict(sorted(stops.items())),
    }


def failure_data(records):
    """Flags overlap. Unclassified means no runner/error flag, not merely no primary flag."""
    counts = {name: sum(bool(r.get(name)) for r in records) for name in ALL_FLAGS}
    failures = [r for r in records if not r.get("valid_request")]
    no_request = [r for r in failures if r.get("request") is None]
    invalid_request = [r for r in failures if r.get("request") is not None]
    unclassified = lambda row: not any(row.get(flag) for flag in ALL_FLAGS)
    table = []
    for row in failures:
        table.append({
            "case_id": row.get("case_id"), "repeat": row.get("repeat"),
            "request_source": row.get("request_source"),
            "failure_type": "no_request" if row.get("request") is None else "invalid_request",
            "validation_errors": row.get("validation_errors") or [],
            "flags": {name: bool(row.get(name)) for name in ALL_FLAGS},
            "last_stop": row.get("last_stop"), "errors": row.get("errors") or [],
            "flag_triggers": row.get("flag_triggers") or {},
            "pi_exit_code": row.get("pi_exit_code"),
        })
    return {
        "flag_denominator": "all attempts; flags may overlap",
        "flags": counts,
        "failed_attempts": len(failures),
        "no_request_failures": len(no_request),
        "invalid_request_failures": len(invalid_request),
        "unclassified_no_request_failures": sum(unclassified(r) for r in no_request),
        "unclassified_invalid_request_failures": sum(unclassified(r) for r in invalid_request),
        "table": table,
    }


def manifests(out):
    """Return parseable manifests. Interrupted historical smoke runs can leave a
    zero-byte manifest that no completed result refers to, so it is not evidence
    against a later completed replay."""
    result = []
    for path in sorted(out.glob("manifest-*.json")):
        try:
            result.append((path.name, json.loads(path.read_text())))
        except json.JSONDecodeError:
            continue
    return result


def validation_errors(out, cases, records, repeat):
    errors = []
    expected_ids = {c["case_id"] for c in cases}
    keys = Counter((r.get("case_id"), r.get("repeat")) for r in records if r.get("complete") is True)
    unknown = sorted({case_id for case_id, _ in keys if case_id not in expected_ids})
    if unknown:
        errors.append("completed records for unknown cases: " + ", ".join(unknown))
    duplicates = sorted(key for key, count in keys.items() if count != 1)
    if duplicates:
        errors.append("duplicate completed keys: " + repr(duplicates))
    missing = [(case_id, rep) for case_id in sorted(expected_ids) for rep in range(1, repeat + 1)
               if (case_id, rep) not in keys]
    if missing:
        errors.append("missing completed keys: " + repr(missing))
    bad_repeats = sorted(key for key in keys if not isinstance(key[1], int) or key[1] < 1 or key[1] > repeat)
    if bad_repeats:
        errors.append("completed keys outside repeat range: " + repr(bad_repeats))
    arm_names = {r.get("arm") for r in records if r.get("complete") is True}
    if len(arm_names) != 1:
        errors.append("completed records must name one arm, got " + repr(sorted(arm_names, key=str)))
    used = {r.get("manifest") for r in records if r.get("complete") is True}
    available = dict(manifests(out))
    if not available:
        errors.append("no run manifests")
    for name in sorted(used, key=str):
        manifest = available.get(name)
        if manifest is None:
            errors.append(f"record refers to missing manifest {name!r}")
            continue
        if manifest.get("priority_key") != "local-llm-bench":
            errors.append(f"{name}: priority_key is not local-llm-bench")
        route = str(manifest.get("route", ""))
        if "turnstile" not in route or "bench key" not in route or "bonsai-agent" not in route:
            errors.append(f"{name}: route does not prove bench-key Bonsai route")
        if arm_names and manifest.get("arm", {}).get("name") not in arm_names:
            errors.append(f"{name}: manifest arm disagrees with records")
    return errors


def render_md(summary):
    def pct(x): return "n/a" if x is None else f"{x * 100:.1f}%"
    def row(name, m):
        return (f"| {name} | {m['attempts']} | {m['valid_requests']} ({pct(m['valid_request_rate'])}) | "
                f"{m['kind_matches']} ({pct(m['kind_match_rate_all_attempts'])}) | "
                f"{m['kind_matches_among_valid_requests']} ({pct(m['kind_match_rate_valid_requests'])}) | "
                f"{m['median_wall_s']} | {m['median_turns']} |")
    lines = ["# Worker-eval deterministic summary", "",
             "Rates: valid requests and first kind-match rate use all attempts; the second kind-match rate uses valid requests. "
             "Failure flags use all attempts as their denominator and may overlap.", "",
             "| Case | Attempts | Valid requests | Kind matches / all | Kind matches / valid | Median wall s | Median turns |",
             "|---|---:|---:|---:|---:|---:|---:|", row("Pooled", summary["pooled"])]
    lines += [row(case["case_id"], case["metrics"]) for case in summary["cases"]]
    f = summary["failures"]
    lines += ["", "## Failure modes", "", f"Flag denominator: {f['flag_denominator']}.", "",
              "| Flag | Count |", "|---|---:|"]
    lines += [f"| {name} | {count} |" for name, count in f["flags"].items()]
    lines += [f"| unclassified no-request failures | {f['unclassified_no_request_failures']} |",
              f"| unclassified invalid-request failures | {f['unclassified_invalid_request_failures']} |", "",
              "## Invalid or absent requests", "", "| Case | Repeat | Type | Source | Flags | Validation errors | Last stop |",
              "|---|---:|---|---|---|---|---|"]
    for fail in f["table"]:
        flags = ", ".join(name for name, value in fail["flags"].items() if value) or "none"
        errs = "; ".join(fail["validation_errors"]) or "—"
        lines.append(f"| {fail['case_id']} | {fail['repeat']} | {fail['failure_type']} | {fail['request_source']} | {flags} | {errs} | {display_stop(fail['last_stop'])} |")
    if not f["table"]:
        lines.append("| — | — | — | — | — | — | — |")
    # Keep every required aggregate (including sparse tool names) visible in Markdown
    # as well as in the machine-readable JSON without maintaining two calculations.
    detail = {"pooled": summary["pooled"],
              "per_case": {case["case_id"]: case["metrics"] for case in summary["cases"]}}
    lines += ["", "## Detailed deterministic metrics", "", "```json",
              json.dumps(detail, indent=2, sort_keys=True), "```"]
    return "\n".join(lines) + "\n"


def build(out, cases_path, repeat):
    cases = read_jsonl(cases_path)
    records = read_jsonl(out / "results.jsonl") if (out / "results.jsonl").exists() else []
    completed = [r for r in records if r.get("complete") is True]
    by_case = {c["case_id"]: [] for c in cases}
    for row in completed:
        if row.get("case_id") in by_case:
            by_case[row["case_id"]].append(row)
    return {
        "format": "worker-eval-summary-v1", "arm": completed[0].get("arm") if completed else None,
        "cases_path": str(cases_path), "repeat_required": repeat,
        "records_total": len(records), "completed_records": len(completed),
        "completion_errors": validation_errors(out, cases, completed, repeat),
        "pooled": metric(completed),
        "cases": [{"case_id": c["case_id"], "metrics": metric(by_case[c["case_id"]])} for c in cases],
        "failures": failure_data(completed),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_dir", nargs="?")
    parser.add_argument("--check", dest="check_dir")
    parser.add_argument("--cases", default=str(HERE / "cases.jsonl"))
    parser.add_argument("--repeat", type=int, default=2)
    args = parser.parse_args(argv)
    if bool(args.result_dir) == bool(args.check_dir):
        parser.error("give RESULT_DIR to write, or --check RESULT_DIR")
    out, cases_path = pathlib.Path(args.check_dir or args.result_dir), pathlib.Path(args.cases)
    try:
        summary = build(out, cases_path, args.repeat)
    except (OSError, ValueError) as exc:
        print(f"summary error: {exc}", file=sys.stderr)
        return 2
    encoded = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    markdown = render_md(summary)
    if args.check_dir:
        errors = list(summary["completion_errors"])
        for path, wanted in ((out / "summary.json", encoded), (out / "summary.md", markdown)):
            if not path.exists(): errors.append(f"missing {path.name}")
            elif path.read_text() != wanted: errors.append(f"{path.name} is not reproducible from results.jsonl")
        if errors:
            print("check failed:\n- " + "\n- ".join(errors), file=sys.stderr)
            return 1
        print(f"check passed: {summary['pooled']['attempts']} attempts")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(encoded)
    (out / "summary.md").write_text(markdown)
    print(out / "summary.json")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
