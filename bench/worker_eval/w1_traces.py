#!/usr/bin/env python3
"""Offline analysis of the 44 committed W1 attempts (events.jsonl, tap.jsonl, record.json).

Writes trace_analysis.json and trace_analysis.md next to the W1 summary.json. Every
section states its method under "method". Estimates use chars/4 for tokens.

  python3 bench/worker_eval/w1_traces.py [W1_DIR]
"""
import json
import pathlib
import re
import statistics
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
W1 = ROOT / "bench/results/2026-10-13/worker-eval/bonsai-2026-10-12"
CONTEXT_OVERFLOW = re.compile(r"context_length_exceeded|exceeds? the (available )?context|context (length|window|size)"
                              r"|maximum context|n_ctx|prompt is too long|too many tokens|exceed_context_size", re.I)
BIG_CHARS, BIG_LINES = 16 * 1024, 400


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def dist(xs):
    return {"n": len(xs), "p50": pct(xs, .5), "p75": pct(xs, .75), "p90": pct(xs, .9), "max": max(xs) if xs else None}


def text_of(content):
    return "".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def jsonl(path):
    out = []
    for line in pathlib.Path(path).read_text(errors="replace").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def reply_chars(msg):
    think = sum(len(b.get("thinking", "")) for b in msg.get("content", []) if b.get("type") == "thinking")
    text = sum(len(b.get("text", "")) for b in msg.get("content", []) if b.get("type") == "text")
    calls = sum(len(json.dumps(b.get("arguments", {}))) + len(b.get("name", ""))
                for b in msg.get("content", []) if b.get("type") == "toolCall")
    return think, text, calls


def load_attempt(d):
    rec = json.loads((d / "record.json").read_text())
    ev = jsonl(d / "events.jsonl")
    tap = jsonl(d / "tap.jsonl") if (d / "tap.jsonl").exists() else []
    start = None
    for e in ev:
        if e.get("type") == "session":
            from datetime import datetime
            start = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).timestamp()
            break
    # timeline: A = assistant reply, T = tool result, CS/CE = compaction start/end
    tl, tools = [], []
    for e in ev:
        t = e.get("type")
        if t == "message_end" and (e.get("message") or {}).get("role") == "assistant":
            tl.append(("A", e["message"]))
        elif t == "tool_execution_end":
            res = e.get("result") or {}
            txt = text_of(res.get("content"))
            item = {"tool": e.get("toolName", "?"), "chars": len(txt), "lines": txt.count("\n") + 1 if txt else 0,
                    "error": bool(e.get("isError") or res.get("isError")), "text": txt}
            tl.append(("T", item))
            tools.append(item)
        elif t == "compaction_start":
            tl.append(("CS", e))
        elif t == "compaction_end":
            tl.append(("CE", e))
    # tap: the first request and every request with n_messages > 2 is an agent reply;
    # a later 2-message request is pi's summarisation call (system + one user message).
    for i, r in enumerate(tap):
        r["_kind"] = "A" if (i == 0 or r.get("n_messages", 0) > 2) else "C"
        r["_t"] = r.get("timings") or {}
    return {"dir": d, "rec": rec, "ev": ev, "tap": tap, "start": start, "tl": tl, "tools": tools}


def attach_taps(a):
    """Pair assistant replies with agent-kind tap records by position; group summarisation
    records into runs and pair each run with the next compaction_start by position."""
    replies = [x for k, x in a["tl"] if k == "A"]
    ataps = [r for r in a["tap"] if r["_kind"] == "A"]
    runs, cur = [], []
    for r in a["tap"]:
        if r["_kind"] == "C":
            cur.append(r)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    a["replies"], a["ataps"], a["cruns"] = replies, ataps, runs
    a["align"] = {"events_replies": len(replies), "tap_agent": len(ataps), "tap_summary_requests": sum(map(len, runs)),
                  "summary_runs": len(runs), "compaction_start": sum(k == "CS" for k, _ in a["tl"]),
                  "compaction_end": sum(k == "CE" for k, _ in a["tl"])}


def time_split(att):
    def one(a):
        dec = sum(r["_t"].get("predicted_ms", 0) for r in a["tap"]) / 1000
        pre = sum(r["_t"].get("prompt_ms", 0) for r in a["tap"]) / 1000
        wall = a["rec"]["wall_s"]
        return {"decode_s": round(dec, 1), "prefill_s": round(pre, 1), "other_s": round(wall - dec - pre, 1), "wall_s": wall}
    per = {f"{a['rec']['case_id']}/r{a['rec']['repeat']}": one(a) for a in att}

    def pool(sel):
        v = [per[k] for k in sel]
        w = sum(x["wall_s"] for x in v) or 1
        return {"attempts": len(v), **{k: round(sum(x[k] for x in v), 1) for k in ("decode_s", "prefill_s", "other_s", "wall_s")},
                "decode_share": round(sum(x["decode_s"] for x in v) / w, 3),
                "prefill_share": round(sum(x["prefill_s"] for x in v) / w, 3),
                "other_share": round(sum(x["other_s"] for x in v) / w, 3)}
    to = [f"{a['rec']['case_id']}/r{a['rec']['repeat']}" for a in att if a["rec"].get("timeout")]
    return {"method": "decode = sum tap timings.predicted_ms, prefill = sum timings.prompt_ms over every tap record "
                      "(replies and summarisation calls); other = record wall_s minus both (tool time, pi overhead, "
                      "the in-flight request killed at timeout, which the tap never logs).",
            "pooled": pool(per), "timeouts_pooled": pool(to), "per_attempt": per}


def reply_tokens(att):
    pn, sh, est, rows = [], [], [], 0
    for a in att:
        for rep, tp in zip(a["replies"], a["ataps"]):
            n = tp["_t"].get("predicted_n")
            th, tx, ca = reply_chars(rep)
            if not n or th + tx + ca == 0:
                continue
            rows += 1
            s = th / (th + tx + ca)
            pn.append(n)
            sh.append(s)
            est.append(n * s)
    return {"method": "Replies paired with agent-kind tap records by position. predicted_n from the tap; thinking share = "
                      "thinking chars / (thinking + text + tool-call JSON chars); estimated reasoning tokens = predicted_n * share.",
            "replies": rows, "predicted_n": dist(pn), "thinking_share": {**dist(sh), "mean": round(statistics.mean(sh), 3)},
            "est_reasoning_tokens": dist(est)}


def thinking_resent(att):
    rows = []
    for a in att:
        # index of tap-agent record -> chars of tool results between this reply and the next
        tool_chars, ri, seen_c = defaultdict(int), -1, set()
        cs_before = {}
        n_c = 0
        for k, x in a["tl"]:
            if k == "A":
                ri += 1
            elif k == "T" and ri >= 0:
                tool_chars[ri] += x["chars"]
            elif k == "CS":
                n_c += 1
                cs_before[ri] = True
        n = min(len(a["replies"]), len(a["ataps"]))
        # a summarisation request sits between agent taps i and i+1 when tap order says so
        order = [r["_kind"] for r in a["tap"]]
        agent_pos = [i for i, k in enumerate(order) if k == "A"]
        for i in range(n - 1):
            if agent_pos[i + 1] - agent_pos[i] != 1 or ri < 0 or i in cs_before:
                continue
            ta, tb = a["ataps"][i], a["ataps"][i + 1]
            pa, pb = (ta.get("usage") or {}).get("prompt_tokens"), (tb.get("usage") or {}).get("prompt_tokens")
            pn = ta["_t"].get("predicted_n")
            th, tx, ca = reply_chars(a["replies"][i])
            if not (pa and pb and pn and th + tx + ca):
                continue
            share = th / (th + tx + ca)
            resid = pb - pa - tool_chars[i] / 4
            rows.append({"delta": pb - pa, "tool_tokens_est": tool_chars[i] / 4, "resid": resid, "predicted_n": pn, "share": share})
    useful = [r for r in rows if r["share"] >= 0.3 and r["predicted_n"] >= 100]
    closer_resent = sum(abs(r["resid"] - r["predicted_n"]) < abs(r["resid"] - r["predicted_n"] * (1 - r["share"])) for r in useful)
    ratio = [r["resid"] / r["predicted_n"] for r in useful]
    ratio_nothink = [r["resid"] / (r["predicted_n"] * (1 - r["share"])) for r in useful if r["share"] < 0.95]
    verdict = "confirmed" if useful and closer_resent / len(useful) > .5 and .7 <= statistics.median(ratio) <= 1.3 else \
              "refuted" if useful and closer_resent / len(useful) < .5 else "inconclusive"
    return {"method": "Consecutive agent requests with no compaction between. resid = prompt_tokens[i+1] - prompt_tokens[i] "
                      "- (tool-result chars between them)/4. If thinking is resent, resid ~ predicted_n[i]; if not, "
                      "resid ~ predicted_n[i] * (1 - thinking share). Discriminating pairs: share >= 0.3 and predicted_n >= 100.",
            "pairs": len(rows), "discriminating_pairs": len(useful),
            "median_resid_over_predicted_n": round(statistics.median(ratio), 3) if ratio else None,
            "median_resid_over_nonthinking_tokens": round(statistics.median(ratio_nothink), 3) if ratio_nothink else None,
            "pairs_closer_to_resent": closer_resent,
            "share_closer_to_resent": round(closer_resent / len(useful), 3) if useful else None,
            "verdict": verdict}


def prompt_composition(att):
    snaps = []
    for a in att:
        th = tool = out = 0.0
        ri, last_pt = -1, None
        for k, x in a["tl"]:
            if k == "A":
                ri += 1
                if ri < len(a["ataps"]):
                    last_pt = (a["ataps"][ri].get("usage") or {}).get("prompt_tokens") or last_pt
                c = reply_chars(x)
                th += c[0] / 4
                out += (c[1] + c[2]) / 4
                err = x.get("errorMessage") or ""
                if x.get("stopReason") == "error" and CONTEXT_OVERFLOW.search(err):
                    snaps.append(("overflow", a, th, tool, out, last_pt))
            elif k == "T":
                tool += x["chars"] / 4
            elif k == "CS":
                snaps.append(("compaction_start", a, th, tool, out, last_pt))
            elif k == "CE":
                th = tool = out = 0.0
    rows = []
    for kind, a, th, tool, out, pt in snaps:
        if not pt:
            continue
        rows.append({"at": kind, "attempt": f"{a['rec']['case_id']}/r{a['rec']['repeat']}", "last_prompt_tokens": pt,
                     "thinking_tokens_est": round(th), "tool_output_tokens_est": round(tool),
                     "thinking_share": round(th / pt, 3), "tool_output_share": round(tool / pt, 3)})
    def med(key, kind=None):
        v = [r[key] for r in rows if kind in (None, r["at"])]
        return round(statistics.median(v), 3) if v else None
    return {"method": "At each compaction_start and each context-overflow reply: thinking and tool-result chars/4 accumulated "
                      "since the previous compaction_end (or session start), divided by the last known prompt_tokens. "
                      "The rest (system prompt, summary, retained pre-compaction messages, user text, text and tool calls) is not split.",
            "events": len(rows), "median_thinking_share": med("thinking_share"), "median_tool_output_share": med("tool_output_share"),
            "by_kind": {k: {"n": sum(r["at"] == k for r in rows), "median_thinking_share": med("thinking_share", k),
                            "median_tool_output_share": med("tool_output_share", k)} for k in ("compaction_start", "overflow")},
            "rows": rows}


def tool_results(att):
    by = defaultdict(list)
    for a in att:
        for t in a["tools"]:
            by[t["tool"]].append(t)
    allt = [t for v in by.values() for t in v]
    total = sum(t["chars"] for t in allt) or 1
    big = [t for t in allt if t["chars"] > BIG_CHARS or t["lines"] > BIG_LINES]
    return {"method": "tool_execution_end results from events.jsonl (already truncated by pi): chars of text content, lines = newlines + 1. "
                      f"Big = more than {BIG_CHARS} chars (16 KB) or more than {BIG_LINES} lines.",
            "count": len(allt), "total_chars": total,
            "by_tool": {k: {"count": len(v), "chars": dist([t["chars"] for t in v]), "lines": dist([t["lines"] for t in v]),
                            "total_chars": sum(t["chars"] for t in v)} for k, v in sorted(by.items())},
            "over_16kb_or_400_lines": len(big), "over_16kb_or_400_lines_by_tool": dict(Counter(t["tool"] for t in big)),
            "big_chars": sum(t["chars"] for t in big), "big_share_of_chars": round(sum(t["chars"] for t in big) / total, 4)}


def compactions(att, split):
    rows, total_wall, timeouts_near = [], sum(a["rec"]["wall_s"] for a in att), []
    for a in att:
        key = f"{a['rec']['case_id']}/r{a['rec']['repeat']}"
        starts = [x for k, x in a["tl"] if k == "CS"]
        windows = []
        for i, run in enumerate(a["cruns"]):
            w0 = run[0]["ts"]
            w1 = run[-1]["ts"] + run[-1].get("wall_s", 0)
            windows.append((w0, w1))
            rows.append({"attempt": key, "index": i, "requests": len(run), "wall_s": round(w1 - w0, 1),
                         "request_wall_s": round(sum(r.get("wall_s", 0) for r in run), 1),
                         "output_tokens": sum(r["_t"].get("predicted_n", 0) for r in run)})
        if a["rec"].get("timeout") and a["start"]:
            end = a["start"] + a["rec"]["wall_s"]
            in_flight = a["align"]["compaction_start"] > a["align"]["compaction_end"] and \
                [k for k, _ in a["tl"] if k in ("CS", "CE")][-1] == "CS"
            near = any(w0 <= end <= w1 + 300 for w0, w1 in windows)
            if in_flight or near:
                timeouts_near.append({"attempt": key, "compaction_in_flight_at_kill": in_flight, "within_5min_of_logged_compaction": near})
    cw = sum(r["wall_s"] for r in rows)
    return {"method": "Summarisation calls are tap records after the first with n_messages <= 2; consecutive ones form a run paired "
                      "with a compaction by position. Duration = last request end (ts + wall_s) minus first request ts; "
                      "output tokens = sum predicted_n. A timeout counts if the kill falls inside a logged run or within 300 s after it, "
                      "or if the last compaction event is a compaction_start (summary in flight; no tap record exists for it).",
            "count_runs": len(rows), "compaction_start_events": sum(a["align"]["compaction_start"] for a in att),
            "compaction_end_events": sum(a["align"]["compaction_end"] for a in att),
            "total_wall_s": round(cw, 1), "share_of_total_wall": round(cw / total_wall, 4),
            "total_output_tokens": sum(r["output_tokens"] for r in rows),
            "duration_s": dist([r["wall_s"] for r in rows]),
            "timeouts_during_or_within_5min_after": len(timeouts_near), "timeouts_detail": timeouts_near, "runs": rows}


def length_stops(att):
    out = []
    for a in att:
        for rep in a["replies"]:
            if rep.get("stopReason") != "length":
                continue
            s = "".join(b.get("thinking", "") if b.get("type") == "thinking" else b.get("text", "")
                        for b in rep.get("content", []) if b.get("type") in ("thinking", "text"))
            tail = s[-4000:]
            loop, excerpt = False, None
            for i in range(0, max(1, len(tail) - 200 + 1), 10):
                w = tail[i:i + 200]
                if len(w) == 200 and tail.count(w) >= 3:
                    loop, excerpt = True, w
                    break
            out.append({"attempt": f"{a['rec']['case_id']}/r{a['rec']['repeat']}", "output_chars": len(s), "loop": loop,
                        "excerpt": excerpt, "tail_300": tail[-300:]})
    return {"method": "Replies with stopReason=length. Loop = some 200-char window (stride 10) of the last 4000 chars of "
                      "thinking+text occurs at least 3 times in those 4000 chars.",
            "count": len(out), "loops": sum(x["loop"] for x in out), "non_loops": sum(not x["loop"] for x in out), "items": out}


def edit_errors(att):
    msgs = [(f"{a['rec']['case_id']}/r{a['rec']['repeat']}", t["text"]) for a in att for t in a["tools"] if t["tool"] == "edit" and t["error"]]
    b = Counter()
    for _, m in msgs:
        if re.search(r"could not find|not found|did not match|old text must match", m, re.I):
            b["text not found"] += 1
        elif re.search(r"multiple|occurrences|not unique|appears \d+ times", m, re.I):
            b["multiple matches"] += 1
        else:
            b["other"] += 1
    other = Counter(m[:120] for _, m in msgs if not re.search(r"could not find|not found|did not match|old text must match|multiple|occurrences|not unique", m, re.I))
    return {"method": "isError tool results of the edit tool; bucket by message regex.", "count": len(msgs), "buckets": dict(b),
            "other_messages": dict(other), "messages": [{"attempt": k, "message": m[:300]} for k, m in msgs]}


def bash_cause(m):
    tail = m.strip()
    exc = re.findall(r"^(\w*(?:Error|Exception)\w*)[:\s]", tail, re.M)
    if "Traceback (most recent call last)" in tail and exc:
        return f"python traceback: {exc[-1]}"
    if re.search(r"SyntaxError", tail):
        return "python traceback: SyntaxError"
    if re.search(r"No such file or directory", tail):
        return "no such file or directory"
    if re.search(r"command not found", tail):
        return "command not found"
    if re.search(r"No module named", tail):
        return "python: module not found"
    if re.search(r"^fatal:|^error:", tail, re.M):
        return "git/tool fatal error"
    if re.search(r"timed out|Command timed out", tail, re.I):
        return "command timeout"
    if re.search(r"Permission denied", tail):
        return "permission denied"
    if re.match(r"\(no output\)\s*\n+Command exited with code 1", tail):
        return "silent exit 1 (grep/test with no match)"
    if re.search(r"Command exited with code 1\s*$", tail):
        return "exit 1 with output (checker / diff / grep)"
    m2 = re.search(r"Command exited with code (\d+)", tail)
    return f"exit code {m2.group(1)} other" if m2 else "other"


def bash_errors(att):
    errs = [(f"{a['rec']['case_id']}/r{a['rec']['repeat']}", t["text"]) for a in att for t in a["tools"] if t["tool"] == "bash" and t["error"]]
    c = Counter(bash_cause(m) for _, m in errs)
    top = c.most_common(10)
    rest = sum(c.values()) - sum(n for _, n in top)
    return {"method": "isError bash results; cause assigned by first matching regex (python exception name, missing file/module, "
                      "git fatal, timeout, silent exit 1, ...). Top 10 causes listed; remainder under rest.",
            "count": len(errs), "top_causes": [{"cause": k, "count": n} for k, n in top], "rest": rest,
            "all_causes": dict(c), "examples": {k: next(m for _, m in errs if bash_cause(m) == k)[-200:] for k, _ in top}}


def timeout_tail(att):
    rows = []
    for a in att:
        if not a["rec"].get("timeout") or not a["start"]:
            continue
        end = a["start"] + a["rec"]["wall_s"]
        lo = end - 300
        gen = comp = 0.0
        for r in a["tap"]:
            s, e = r["ts"], r["ts"] + r.get("wall_s", 0)
            ov = max(0.0, min(e, end) - max(s, lo))
            if r["_kind"] == "C":
                comp += ov
            else:
                gen += ov
        last_end = max((r["ts"] + r.get("wall_s", 0) for r in a["tap"]), default=a["start"])
        unlogged = max(0.0, end - max(last_end, lo))
        kinds = [k for k, _ in a["tl"] if k in ("CS", "CE")]
        if kinds and kinds[-1] == "CS":
            label = "compaction in flight at kill"
            comp += unlogged
        else:
            label = None
        parts = {"logged_generation_s": gen, "logged_compaction_s": comp, "unlogged_tail_s": unlogged}
        # unlogged tail after a tool result = a request in flight (generation); after a request with no result yet = tool
        last = [k for k, _ in a["tl"] if k in ("A", "T")]
        if label is None:
            label = "generation in flight at kill (unlogged request)" if unlogged > 0 and last and last[-1] == "T" else \
                    "tool running at kill" if unlogged > 0 and last and last[-1] == "A" else \
                    "long generation" if gen >= comp else "compaction"
        rows.append({"attempt": f"{a['rec']['case_id']}/r{a['rec']['repeat']}", "label": label,
                     **{k: round(v, 1) for k, v in parts.items()}, "last_event": last[-1] if last else None,
                     "last_stop": a["rec"].get("last_stop")})
    return {"method": "For each timed-out attempt (session start from the session event, end = start + wall_s), tap requests "
                      "overlapping the last 300 s: generation vs summarisation seconds. The request running at the kill has no tap "
                      "record (unlogged tail): it is generation if the last event was a tool result, a tool run if it was a reply.",
            "count": len(rows), "labels": dict(Counter(r["label"] for r in rows)), "items": rows}


def turns(att):
    t = [a["rec"]["turns"] for a in att]
    return {"method": "record.json turns (count of turn_end events) per attempt.", "per_attempt": dist(t),
            "timeouts": dist([a["rec"]["turns"] for a in att if a["rec"].get("timeout")]),
            "non_timeouts": dist([a["rec"]["turns"] for a in att if not a["rec"].get("timeout")]),
            "histogram": dict(sorted(Counter((x // 10) * 10 for x in t).items()))}


def main():
    w1 = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else W1
    dirs = sorted(p for p in w1.glob("*/r[0-9]*") if (p / "record.json").exists())
    att = [load_attempt(d) for d in dirs]
    for a in att:
        attach_taps(a)
    res = {"source": str(w1.relative_to(ROOT)) if w1.is_relative_to(ROOT) else str(w1), "attempts": len(att),
           "timeouts": sum(bool(a["rec"].get("timeout")) for a in att),
           "alignment": {f"{a['rec']['case_id']}/r{a['rec']['repeat']}": a["align"] for a in att}}
    res["time_split"] = time_split(att)
    res["reply_tokens"] = reply_tokens(att)
    res["thinking_resent"] = thinking_resent(att)
    res["prompt_composition_at_pressure"] = prompt_composition(att)
    res["tool_results"] = tool_results(att)
    res["compactions"] = compactions(att, res["time_split"])
    res["length_stops"] = length_stops(att)
    res["edit_errors"] = edit_errors(att)
    res["bash_errors"] = bash_errors(att)
    res["timeout_tail"] = timeout_tail(att)
    res["turns"] = turns(att)
    (w1 / "trace_analysis.json").write_text(json.dumps(res, indent=2) + "\n")
    (w1 / "trace_analysis.md").write_text(render(res))
    print(f"wrote {w1}/trace_analysis.json ({len(att)} attempts)")


def render(r):
    ts, rt, tr = r["time_split"], r["reply_tokens"], r["thinking_resent"]
    pc, tl, cp, ls = r["prompt_composition_at_pressure"], r["tool_results"], r["compactions"], r["length_stops"]
    L = [f"# W1 trace analysis ({r['attempts']} attempts, {r['timeouts']} timeouts)", "",
         "Generated by `bench/worker_eval/w1_traces.py`. Method per section is in trace_analysis.json.", "",
         "## Time split", "",
         f"- pooled: decode {ts['pooled']['decode_s']} s ({ts['pooled']['decode_share']:.1%}), prefill {ts['pooled']['prefill_s']} s "
         f"({ts['pooled']['prefill_share']:.1%}), other {ts['pooled']['other_s']} s ({ts['pooled']['other_share']:.1%}) of {ts['pooled']['wall_s']} s",
         f"- timeouts only: decode {ts['timeouts_pooled']['decode_share']:.1%}, prefill {ts['timeouts_pooled']['prefill_share']:.1%}, other {ts['timeouts_pooled']['other_share']:.1%}", "",
         "## Reply tokens", "",
         f"- predicted_n p50/p75/p90/max: {rt['predicted_n']['p50']}/{rt['predicted_n']['p75']}/{rt['predicted_n']['p90']}/{rt['predicted_n']['max']}",
         f"- thinking share mean {rt['thinking_share']['mean']}",
         f"- estimated reasoning tokens p50/p75/p90: {rt['est_reasoning_tokens']['p50']:.0f}/{rt['est_reasoning_tokens']['p75']:.0f}/{rt['est_reasoning_tokens']['p90']:.0f}", "",
         "## Thinking resent", "",
         f"- verdict **{tr['verdict']}**: {tr['discriminating_pairs']} discriminating pairs, {tr['share_closer_to_resent']} closer to 'resent', "
         f"median resid/predicted_n {tr['median_resid_over_predicted_n']}, resid/non-thinking {tr['median_resid_over_nonthinking_tokens']}", "",
         "## Prompt composition at pressure", "",
         f"- {pc['events']} events; median thinking share {pc['median_thinking_share']}, tool-output share {pc['median_tool_output_share']}", "",
         "## Tool results", "",
         f"- {tl['count']} results; {tl['over_16kb_or_400_lines']} over 16 KB/400 lines ({tl['big_share_of_chars']:.1%} of chars)", "",
         "## Compactions", "",
         f"- {cp['count_runs']} logged runs, {cp['total_wall_s']} s = {cp['share_of_total_wall']:.1%} of wall; "
         f"{cp['timeouts_during_or_within_5min_after']} timeouts during/within 5 min after", "",
         "## Length stops", "",
         f"- {ls['count']} stops, {ls['loops']} loops, {ls['non_loops']} non-loops", "",
         "## Errors", "",
         f"- edit: {r['edit_errors']['count']} {r['edit_errors']['buckets']}",
         f"- bash: {r['bash_errors']['count']}; top: " + ", ".join(f"{x['cause']} ({x['count']})" for x in r['bash_errors']['top_causes']), "",
         "## Timeout tail", "", f"- {r['timeout_tail']['count']} timeouts: {r['timeout_tail']['labels']}", "",
         "## Turns", "", f"- p50 {r['turns']['per_attempt']['p50']}, p90 {r['turns']['per_attempt']['p90']}, max {r['turns']['per_attempt']['max']}", ""]
    return "\n".join(L)


if __name__ == "__main__":
    main()
