"""Summarize replay runs: python3 bench/spec_analyze.py REPLAY_DIR LABEL-SAMPLING [...]

Per phase and arm: fg tok/s (sum predicted_n / sum predicted_ms) with and without
finish_reason=length rows, bg tokens, draft counts, length rows, and the share of
out_sha256 equal to the first arm's (same phase, same id). Prints markdown.
"""
import json
import sys

PHASES = ["single-agent", "single-mem", "dual-agent", "dual-mem"]


def rows(d, arm):
    return [json.loads(l) for l in open(f"{d}/{arm}/requests.jsonl") if l.strip()]


def rate(rs):
    ms = sum((r.get("predicted_ms") or 0) for r in rs)
    return 1000 * sum((r.get("predicted_n") or 0) for r in rs) / ms if ms else float("nan")


def main():
    d, arms = sys.argv[1], sys.argv[2:]
    data = {a: rows(d, a) for a in arms}
    ref = {(r["phase"], r["id"]): r.get("out_sha256") for r in data[arms[0]] if r["fg_bg"] == "fg"}
    print("| phase | arm | fg tok/s | fg tok/s no-length | n fg | length rows (ids) | draft_n | accepted | bg tok | same sha as", arms[0], "|")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for ph in PHASES:
        for a in arms:
            fg = [r for r in data[a] if r["phase"] == ph and r["fg_bg"] == "fg"]
            bg = [r for r in data[a] if r["phase"] == ph and r["fg_bg"] == "bg"]
            ln = [r for r in fg if r.get("finish_reason") == "length"]
            nl = [r for r in fg if r.get("finish_reason") != "length"]
            same = sum(1 for r in fg if ref.get((ph, r["id"])) == r.get("out_sha256"))
            print(f"| {ph} | {a} | {rate(fg):.1f} | {rate(nl):.1f} | {len(fg)} | "
                  f"{len(ln)} ({', '.join(r['id'].split('inventory-')[-1] for r in ln)}) | "
                  f"{sum((r.get('draft_n') or 0) for r in fg)} | {sum((r.get('draft_n_accepted') or 0) for r in fg)} | "
                  f"{sum((r.get('predicted_n') or 0) for r in bg)} | {same}/{len(fg)} |")


main()
