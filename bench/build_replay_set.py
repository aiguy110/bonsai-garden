#!/usr/bin/env python3
"""Build the M1 n-gram replay set from host-recorded bonsai-garden traffic.

Inputs (host paths named in recon/inventory.json):
  - per-step pi event streams (agent_end carries the full message history)
  - per-run mem0 SQLite stores (memory_history, messages)
  - recon/mem0_extract_src.txt (ADDITIVE_EXTRACTION_PROMPT + user-prompt template)

Outputs:
  - bench/.replay/m1/agent.jsonl, mem.jsonl   (gitignored; recorded content)
  - bench/results/2026-10-12/m1-ngram/replay_manifest.json   (committed, no content)

Each line: {"id", "role", "body", "meta"}. Bodies carry no sampling params; the probe
sets them. Mem bodies carry no tools and chat_template_kwargs {enable_thinking:false}.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sqlite3
import statistics
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
RECON = ROOT / "bench/results/2026-10-12/m1-ngram/recon"
OUT_DIR = ROOT / "bench/.replay/m1"
MANIFEST = ROOT / "bench/results/2026-10-12/m1-ngram/replay_manifest.json"


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-step", type=int, default=5, help="agent turns per chosen step")
    ap.add_argument("--agent-max", type=int, default=30)
    ap.add_argument("--mem-max", type=int, default=12)
    ap.add_argument("--dry-run", action="store_true", help="print summary, write nothing")
    return ap.parse_args()


def log(*a):
    print(*a, file=sys.stderr)


# ---------- event streams ----------

def read_events(path):
    """Return (first system message_start event message, session ts, agent_end messages)."""
    sysmsg = None
    session_ts = None
    msgs = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "message_update" in line[:60]:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            t = e.get("type")
            if t == "session":
                session_ts = e.get("timestamp")
            elif t == "message_start" and sysmsg is None and e["message"].get("role") == "system":
                sysmsg = e["message"]
            elif t == "agent_end":
                msgs = e["messages"]
    return sysmsg, session_ts, msgs


def blocks_text(content):
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content if b.get("type") == "text")


def system_text(m):
    secs = m.get("sections")
    if secs:
        # pi: sections rendered in order, joined with a blank line (pi_prompt_src.txt)
        return "\n\n".join(secs.values()), True
    return m.get("content", ""), False


def to_openai(m):
    r = m["role"]
    if r == "system":
        return {"role": "system", "content": system_text(m)[0]}
    if r == "user":
        return {"role": "user", "content": blocks_text(m["content"])}
    if r == "custom":  # pi's mem0-recall message reaches the model as a user message
        return {"role": "user", "content": blocks_text(m["content"])}
    if r == "toolResult":
        return {"role": "tool", "tool_call_id": m["toolCallId"], "content": blocks_text(m["content"])}
    if r == "assistant":  # reasoning dropped, as pi does
        out = {"role": "assistant", "content": "".join(
            b.get("text", "") for b in m["content"] if b.get("type") == "text")}
        calls = [b for b in m["content"] if b.get("type") == "toolCall"]
        if calls:
            out["tool_calls"] = [{"id": c["id"], "type": "function",
                                  "function": {"name": c["name"],
                                               "arguments": c["arguments"] if isinstance(c["arguments"], str)
                                               else json.dumps(c["arguments"])}}
                                 for c in calls]
        return out
    raise ValueError("unknown role " + r)


def tool_list(sysmsg):
    return [{"type": "function",
             "function": {"name": t["name"], "description": t["description"],
                          "parameters": t["parameters"]}}
            for t in sysmsg.get("toolsAdded", [])]


def est_chars(messages, tools=None):
    n = 0
    for m in messages:
        n += len(m.get("content") or "")
        for c in m.get("tool_calls", []):
            n += len(c["function"]["name"]) + len(c["function"]["arguments"])
    if tools:
        n += len(json.dumps(tools, separators=(",", ":")))
    return n


def chars_by_role(messages, tools):
    d = {"tools": len(json.dumps(tools, separators=(",", ":")))}
    for m in messages:
        n = len(m.get("content") or "") + sum(len(c["function"]["arguments"]) for c in m.get("tool_calls", []))
        d[m["role"]] = d.get(m["role"], 0) + n
    return d


def step_score(msgs):
    names, tested = set(), False
    for m in msgs:
        if m["role"] == "assistant":
            names |= {b["name"] for b in m["content"] if b.get("type") == "toolCall"}
        if m["role"] == "toolResult" and re.search(r"\d+ (passed|failed)", blocks_text(m["content"])):
            tested = True
    return len({"read", "edit", "write"} & names) * 2 + (3 if tested else 0) + len(names)


def spread(n, k):
    if n <= k:
        return list(range(n))
    return sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})


# ---------- mem0 ----------

def load_additive(path):
    txt = path.read_text(encoding="utf-8")
    a = txt.index("var ADDITIVE_EXTRACTION_PROMPT = `") + len("var ADDITIVE_EXTRACTION_PROMPT = `")
    b = txt.index("\n`\n", a) + 1
    raw = txt[a:b]
    # raw JS template-literal source: decode escapes in one pass, as JS would
    def dec(m):
        t = m.group(1)
        if t[0] == "u" and len(t) == 5:
            return chr(int(t[1:], 16))
        return {"n": "\n", "t": "\t", "r": "\r"}.get(t, t)
    return re.sub(r"\\(u[0-9a-fA-F]{4}|.)", dec, raw, flags=re.S)


def parse_ts(s):
    if isinstance(s, (int, float)) or (isinstance(s, str) and re.fullmatch(r"\d+(\.\d+)?", s)):
        v = float(s)
        return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, timezone.utc)
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def db_tables(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    info = {}
    for t in ("memory_history", "messages"):
        info[t] = [r["name"] for r in con.execute(f"PRAGMA table_info({t})")]
    return con, info


def existing_memories(con, cols, cutoff, limit=10):
    """Latest text per memory id, created before cutoff; ids whose latest action is DELETE dropped."""
    tcol = next((c for c in ("new_value", "new_memory", "text", "memory") if c in cols), None)
    acol = next((c for c in ("action", "event") if c in cols), None)
    if not tcol:
        return [], False
    latest, filtered = {}, False
    for r in (dict(r) for r in con.execute("SELECT * FROM memory_history ORDER BY rowid")):
        ts = parse_ts(r.get("created_at"))
        if cutoff and ts:
            filtered = True
            if ts >= cutoff:
                continue
        act = str(r.get(acol) or "").upper() if acol else "ADD"
        key = r.get("memory_id") or r.get("id")
        if act == "DELETE":
            latest.pop(key, None)
        elif act in ("ADD", "UPDATE") and r.get(tcol):
            latest[key] = r[tcol]
    texts = list(latest.values())[-limit:]
    return [{"id": str(i), "text": t} for i, t in enumerate(texts)], filtered


def last_k(con, cols, cutoff, k=10):
    if not {"role", "content"} <= set(cols):
        return []
    rows = [dict(r) for r in con.execute("SELECT * FROM messages ORDER BY rowid")]
    out = []
    for r in rows:
        ts = parse_ts(r.get("created_at")) if "created_at" in cols else None
        if cutoff and ts and ts >= cutoff:
            continue
        out.append(f"{r['role']}: {r['content']}")
    return out[-k:]


def mem_user_prompt(existing, lastk, new_msgs, date):
    # generateAdditiveExtractionPrompt (mem0_extract_src.txt:1137). serializeMemories and
    # formatConversationHistory are not in the dump: assumed JSON list / "role: content" lines.
    sections = [
        "## Summary\n",
        "## Last k Messages\n" + "\n".join(lastk),
        "## Recently Extracted Memories\n[]",
        "## Existing Memories\n" + json.dumps(existing),
        "## New Messages\n" + new_msgs,
        "## Observation Date\n" + date,
        "## Current Date\n" + date,
        "# Output:",
    ]
    return "\n\n".join(sections)


# ---------- main ----------

def median(xs):
    return round(statistics.median(xs), 3) if xs else None


def main():
    args = parse_args()
    inv = json.loads((RECON / "inventory.json").read_text())
    additive = load_additive(RECON / "mem0_extract_src.txt")
    log("ADDITIVE prompt chars:", len(additive))

    steps = []  # one record per (run, step)
    for run in inv["runs"]:
        arm = "mem0" if "mem0" in run["run_id"] else "baseline"
        for sk in sorted(run["steps"], key=int):
            st = run["steps"][sk]
            sysmsg, sess_ts, msgs = read_events(st["events_file"])
            if not msgs or not sysmsg:
                log("SKIP (no agent_end/system)", run["run_id"], sk)
                continue
            steps.append(dict(run=run["run_id"], arm=arm, step=int(sk), st=st, sysmsg=sysmsg,
                              sess_ts=sess_ts, msgs=msgs, run_rec=run))
    log("steps loaded:", len(steps))

    # ---- agent set: 3 best steps per arm, --per-step turns each, spread over the step
    chosen = []
    for arm in ("baseline", "mem0"):
        cand = [s for s in steps if s["arm"] == arm
                and sum(m["role"] == "assistant" for m in s["msgs"]) >= args.per_step]
        cand.sort(key=lambda s: -step_score(s["msgs"]))
        chosen += cand[: max(1, args.agent_max // args.per_step // 2)]
    agent, mismatches, exact_all = [], [], True
    for s in chosen:
        recs = [r for r in s["st"]["tap_records"] if r["role"] == "agent"]
        asst_idx = [i for i, m in enumerate(s["msgs"]) if m["role"] == "assistant"]
        _, exact = system_text(s["msgs"][0])
        exact_all &= exact
        tools = tool_list(s["sysmsg"])
        for t in spread(len(asst_idx), args.per_step):
            if t >= len(recs):
                continue
            hist = [to_openai(m) for m in s["msgs"][: asst_idx[t]]]
            rec = recs[t]
            if len(hist) != rec["n_messages"]:
                mismatches.append(dict(id=f"{s['run']}/{s['step']}/{t}", built=len(hist),
                                       recorded=rec["n_messages"]))
            body = {"messages": hist, "tools": tools}
            agent.append(dict(id=f"{s['run']}/{s['step']}/{t}", role="agent", body=body,
                              recorded_prompt_tokens=rec["prompt_n"] + rec["cache_n"],
                              meta=dict(arm=s["arm"], step=s["step"], turn=t,
                                        predicted_n=rec["predicted_n"],
                                        recorded_n_messages=rec["n_messages"],
                                        chars=est_chars(hist, tools),
                                        chars_by_role=chars_by_role(hist, tools))))
    agent = agent[: args.agent_max]

    # ---- mem set: one request per mem tap record in the mem0 arm, up to --mem-max.
    # Events per step: one per mem0_memory add toolCall (new msgs = "user: <content>", cutoff = its
    # toolResult time) + the auto-capture (user prompt + first assistant text, cutoff = that
    # message's time), in cutoff order, matched to the step's mem tap records in order.
    mem, dbinfo = [], {}
    for s in steps:
        if s["arm"] != "mem0":
            continue
        recs = [r for r in s["st"]["tap_records"] if r["role"] == "mem"]
        dbs = s["run_rec"]["mem0_dbs"]
        hist_db = next((v["path"] for k, v in dbs.items() if k.endswith("mem0-history.db")), None)
        if not recs or not hist_db:
            log("no mem records/db for", s["run"], s["step"])
            continue
        con, cols = db_tables(hist_db)
        dbinfo[s["run"]] = cols
        date = (s["sess_ts"] or "")[:10] or "2026-10-11"
        tr_ts = {m["toolCallId"]: m.get("timestamp") for m in s["msgs"] if m["role"] == "toolResult"}
        events = []
        user = next(m for m in s["msgs"] if m["role"] == "user")
        for m in s["msgs"]:
            if m["role"] != "assistant":
                continue
            for b in m["content"]:
                if b.get("type") == "toolCall" and b["name"] == "mem0_memory":
                    a = b["arguments"] if isinstance(b["arguments"], dict) else json.loads(b["arguments"])
                    if a.get("action") != "add":
                        continue
                    txt = next((a[k] for k in ("content", "text", "memory", "fact", "data")
                                if isinstance(a.get(k), str)), None)
                    if txt is None:
                        log("tool add without known content key:", s["run"], s["step"], list(a))
                        txt = json.dumps(a)
                    events.append(dict(kind="tool_add", ts=tr_ts.get(b["id"]) or m.get("timestamp"),
                                       new=f"user: {txt}"))
        cap = next((m for m in s["msgs"] if m["role"] == "assistant"
                    and any(b.get("type") == "text" and b.get("text", "").strip() for b in m["content"])), None)
        if cap:
            events.append(dict(kind="capture", ts=cap.get("timestamp"),
                               new=f"user: {blocks_text(user['content'])}\nassistant: {blocks_text(cap['content'])}"))
        events.sort(key=lambda e: e["ts"] or 0)
        if len(events) != len(recs):
            log("MEM COUNT MISMATCH", s["run"], s["step"], "events", len(events), "tap", len(recs))
        for j, rec in enumerate(recs):
            e = events[j] if j < len(events) else dict(kind="unmatched", ts=events[-1]["ts"] if events else None,
                                                       new=events[-1]["new"] if events else "")
            cutoff = parse_ts(e["ts"])
            ex, filtered = existing_memories(con, cols["memory_history"], cutoff)
            lk = last_k(con, cols["messages"], cutoff)
            up = mem_user_prompt(ex, lk, e["new"], date)
            msgs_ = [{"role": "system", "content": additive}, {"role": "user", "content": up}]
            mem.append(dict(id=f"{s['run']}/{s['step']}/{j}", role="mem",
                            body={"messages": msgs_, "response_format": {"type": "json_object"},
                                  "chat_template_kwargs": {"enable_thinking": False}},
                            recorded_prompt_tokens=rec["prompt_n"] + rec["cache_n"],
                            meta=dict(arm="mem0", step=s["step"], ordinal=j, kind=e["kind"],
                                      predicted_n=rec["predicted_n"],
                                      cap_hit_2048=rec["predicted_n"] == 2048,
                                      recorded_n_messages=rec["n_messages"],
                                      n_existing=len(ex), n_last_k=len(lk),
                                      existing_time_filtered=filtered,
                                      chars=est_chars(msgs_))))
    mem = mem[: args.mem_max]

    # ---- manifest
    def entry(r):
        c = r["meta"]["chars"]
        rp = r["recorded_prompt_tokens"]
        return dict(id=r["id"], role=r["role"], n_messages=len(r["body"]["messages"]),
                    prompt_chars=c, est_tokens_chars4=round(c / 4),
                    recorded_prompt_tokens=rp, est_over_recorded=round(c / 4 / rp, 3),
                    predicted_n=r["meta"]["predicted_n"], kind=r["meta"].get("kind"),
                    chars_by_role=r["meta"].get("chars_by_role"))
    ents = [entry(r) for r in agent + mem]
    by = lambda role: [e for e in ents if e["role"] == role]
    manifest = dict(
        system_prompt_exact=exact_all,
        system_prompt_note="agent system prompt = recorded sections joined by blank lines; the join is INFERRED "
                           "(getSystemMessageText is not in pi_prompt_src.txt); exactness is supported only by "
                           "the est/recorded ratios of requests with n_messages<=3",
        mem_prompt_assumptions="serializeMemories=JSON list; formatConversationHistory='role: content' lines; "
                               "existing = latest 10 live memories (ADD/UPDATE, DELETE removed) created before the per-call cutoff "
                               "(not the 10 nearest by embedding); newMessages 'role: content' per mem0_extract_src.txt:838; "
                               "tool-add content key guessed from toolCall arguments",
        totals={role: dict(requests=len(by(role)),
                           distinct_steps=len({e["id"].rsplit("/", 1)[0] for e in by(role)}),
                           prompt_chars=sum(e["prompt_chars"] for e in by(role)),
                           recorded_prompt_tokens=sum(e["recorded_prompt_tokens"] for e in by(role)),
                           median_est_over_recorded=median([e["est_over_recorded"] for e in by(role)]))
                for role in ("agent", "mem")},
        n_messages_mismatches=mismatches,
        mem0_db_columns=dbinfo,
        requests=ents,
    )
    print(json.dumps({k: manifest[k] for k in ("system_prompt_exact", "totals")}, indent=1))
    short = [e["est_over_recorded"] for e in by("agent") if e["n_messages"] <= 3]
    print("agent ratio n_messages<=3:", short)
    print("agent chars_by_role (id, ratio, breakdown):")
    for e in by("agent"):
        print("  ", e["id"], e["est_over_recorded"], e["chars_by_role"])
    print("mem kinds:", [(e["id"], e["kind"], e["est_over_recorded"]) for e in by("mem")])
    manifest["agent_ratio_n_messages_le3"] = short
    print("n_messages mismatches:", len(mismatches), mismatches[:10])
    print("mem0 db columns:", json.dumps(dbinfo))
    print("outliers (ratio outside 0.75-1.33):",
          [(e["id"], e["est_over_recorded"]) for e in ents if not 0.75 <= e["est_over_recorded"] <= 1.33])
    if args.dry_run:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, rows in (("agent", agent), ("mem", mem)):
        with open(OUT_DIR / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=1))
    print("wrote", OUT_DIR, MANIFEST)


if __name__ == "__main__":
    main()
