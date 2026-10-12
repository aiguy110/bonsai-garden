#!/usr/bin/env python3
"""Build the M1 n-gram replay set from host-recorded traffic.

Converts host-recorded LLM traffic (pi agent + mem0) into OpenAI-compatible
chat-completion bodies for replay, plus a manifest with per-entry
prompt-char / chars/4 token estimates verified against recorded tap
prompt-token counts.

Reads (at runtime on the host; the sandbox cannot see evals/results/):
  - bench/results/<date>/m1-ngram/recon/inventory.json
        run/step metadata: events_file paths, tap_records (prompt_n, cache_n,
        n_messages), mem0_dbs paths.
  - host events files: stepN.events.jsonl (one JSON object per line).
        Authoritative transcript = the agent_end event's `messages`.
  - mem0 sqlite DBs (memory/mem0-history.db) for mem0-arm existing memories.
  - recon source dumps: mem0_extract_src.txt (ADDITIVE_EXTRACTION_PROMPT).

Writes:
  - bench/.replay/m1/agent.jsonl   (gitignored)
  - bench/.replay/m1/mem.jsonl     (gitignored)
  - bench/results/<date>/m1-ngram/replay_manifest.json (committed)

Fidelity notes
  - pi `thinking` blocks dropped from assistant history (matches pi).
  - recorded `toolResult` -> OpenAI `tool` message; `custom` (mem0-recall) ->
    `user` text.
  - pi system prompt rebuilt from recorded per-section payloads (verbatim);
    join is content-faithful but not byte-exact -> system_prompt_exact False.
  - OpenAI `tools` array reconstructed from pi tool names + recorded arg keys.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent          # bench/
REPLAY_DIR = BASE / ".replay" / "m1"
REPLAY_DIR.mkdir(parents=True, exist_ok=True)

# section emit order for pi system prompts
PI_SECTION_ORDER = ["preamble", "tools", "rules", "docs", "addendum",
                    "project_context", "skills", "cwd"]


# --------------------------------------------------------------------------- #
# Inventory
# --------------------------------------------------------------------------- #
def load_inventory(recon_dir: Path) -> dict:
    return json.load((recon_dir / "inventory.json").read_text())


def find_run(inv, run_id):
    for r in inv["runs"]:
        if r["run_id"] == run_id:
            return r
    return None


def tap_by_role(step, role):
    return [t for t in step.get("tap_records", []) if t.get("role") == role]


def read_events(events_file: str):
    events = []
    with open(events_file, "r") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"  [warn] skipping malformed event line {lineno} in {events_file}")
    return events


def extract_agent_end_messages(events):
    for ev in events:
        if ev.get("type") == "agent_end":
            evs = ev.get("event", ev)
            msgs = evs.get("messages")
            if msgs:
                return msgs
    return None


# --------------------------------------------------------------------------- #
# Pi system prompt
# --------------------------------------------------------------------------- #
def build_pi_system_prompt(system_msg):
    """Return (text, order, exact).  exact is conservatively False."""
    sections = system_msg.get("sections", {}) or {}
    out, order = [], []
    for key in PI_SECTION_ORDER:
        if key in sections:
            out.append(sections[key]); order.append(key)
    for key in sections:
        if key not in order:
            out.append(sections[key]); order.append(key)
    return "\n\n".join(out), order, False


# --------------------------------------------------------------------------- #
# OpenAI body construction (agent)
# --------------------------------------------------------------------------- #
def pi_tool_schemas(include_mem0):
    read_schema = {
        "type": "function", "function": {
            "name": "read",
            "description": "Read the contents of a file. Supports text files "
                            "and images (jpg, png, gif, webp, bmp). Images are "
                            "sent as attachments. For text files, output is "
                            "truncated to 2000 lines or 50KB (whichever is hit "
                            "first). Use offset/limit for large files. When you "
                            "need the full file, continue with offset/limit "
                            "until complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string",
                             "description": "Path to the file to read (absolute or relative)"},
                    "offset": {"type": "integer",
                               "description": "Line number to start reading from (1-indexed)"},
                    "limit": {"type": "integer",
                              "description": "Maximum number of lines to read"},
                },
                "required": ["path", "offset", "limit"],
            },
        },
    }
    bash_schema = {
        "type": "function", "function": {
            "name": "bash",
            "description": "Execute a bash command in the current working "
                            "directory. Returns stdout and stderr. Output is "
                            "truncated to the last 2000 lines or 50KB "
                            "(whichever is hit first). If truncated, full output "
                            "is saved to a temp file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string",
                                 "description": "Shell command to execute"},
                    "timeout": {"type": "integer",
                                "description": "Timeout in seconds (optional)"},
                },
                "required": ["command"],
            },
        },
    }
    edit_schema = {
        "type": "function", "function": {
            "name": "edit",
            "description": "Edit a single file using exact text replacement. "
                            "Every edits[].oldText must match a unique, "
                            "non-overlapping region of the original file. Merge "
                            "nearby changes into one edit instead of overlapping "
                            "edits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string",
                              "description": "Path to the file to edit"},
                    "edits": {
                        "type": "array",
                        "description": "One or more targeted replacements",
                        "items": {
                            "type": "object",
                            "properties": {
                                "oldText": {"type": "string",
                                            "description": "Exact text for one targeted replacement"},
                                "newText": {"type": "string",
                                             "description": "Replacement text for this targeted edit"},
                            },
                            "required": ["oldText", "newText"],
                        },
                    },
                },
                "required": ["path", "edits"],
            },
        },
    }
    write_schema = {
        "type": "function", "function": {
            "name": "write",
            "description": "Write content to a file. Creates the file if it "
                            "doesn't exist, overwrites if it does. Automatically "
                            "creates parent directories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string",
                              "description": "Path to the file to write"},
                    "content": {"type": "string",
                                "description": "Content to write to the file"},
                },
                "required": ["path", "content"],
            },
        },
    }
    tools = [read_schema, bash_schema, edit_schema, write_schema]
    if include_mem0:
        mem_schema = {
            "type": "function", "function": {
                "name": "mem0_memory",
                "description": "Search and manage long-term semantic memories (Mem0).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string",
                                    "description": "Operation: search or store.",
                                    "enum": ["search", "store"]},
                        "query": {"type": "string",
                                   "description": "Search query or the memory text to store"},
                    },
                },
            },
        }
        tools.append(mem_schema)
    return tools


def text_blocks(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    return ""


def msg_to_openai(msg):
    role = msg.get("role")
    if role == "system":
        return None
    if role == "user":
        return {"role": "user", "content": text_blocks(msg.get("content"))}
    if role == "custom":
        return {"role": "user", "content": text_blocks(msg.get("content"))}
    if role == "assistant":
        content = []
        tool_calls = []
        for b in msg.get("content") or []:
            t = b.get("type")
            if t == "thinking":
                continue
            if t == "toolCall":
                tool_calls.append({"type": "function",
                                   "function": {"name": b.get("name"),
                                                "arguments": json.dumps(
                                                    b.get("arguments", {}))}})
            elif t == "text":
                content.append({"type": "text", "text": b.get("text", "")})
        m = {"role": "assistant"}
        if tool_calls:
            m["tool_calls"] = tool_calls
        if content:
            m["content"] = content
        return m
    if role == "toolResult":
        return {"role": "tool", "tool_call_id": msg.get("toolCallId"),
                "content": text_blocks(msg.get("content"))}
    return None


def build_agent_body(transcript, idx, system_text, tools):
    """Request for the assistant message at transcript index idx
    (prefix before it = actual LLM request)."""
    msgs = transcript[:idx]
    openai = [{"role": "system", "content": system_text}]
    for m in msgs:
        out = msg_to_openai(m)
        if out is not None:
            openai.append(out)
    return {"messages": openai, "tools": tools, "max_tokens": 16384}


def body_char_count(body):
    return sum(len(json.dumps(m, ensure_ascii=False)) for m in body.get("messages", []))


def ratio(est, recorded):
    return est / recorded if recorded else None


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    n = len(xs)
    if not n:
        return None
    mid = n // 2
    return xs[mid] if n % 2 else (xs[mid - 1] + xs[mid]) / 2


# --------------------------------------------------------------------------- #
# mem0
# --------------------------------------------------------------------------- #
def extract_additive_extraction_prompt(mem0_src):
    m = re.search(r'var ADDITIVE_EXTRACTION_PROMPT\s*=\s*`', mem0_src)
    start = mem0_src.find('`', m.end() - 1)
    end = start + 1
    while end < len(mem0_src):
        c = mem0_src[end]
        if c == "\\" and end + 1 < len(mem0_src):
            end += 2
            continue
        if c == '`':
            break
        end += 1
    body = mem0_src[start + 1:end]
    body = re.sub(r'\\u([0-9a-fA-F]{4})',
                  lambda x: chr(int(x.group(1), 16)), body)
    return body.replace('\\t', '\t').replace('\\n', '\n')


def serialize_memories(mems):
    return json.dumps(mems, ensure_ascii=False)


def format_conversation_history(messages):
    return "\n".join(f"{(m.get('role') or 'user').upper()}: {m.get('content', '')}"
                     for m in messages)


def build_mem_user_prompt(existing, new_messages, last_k, obs_date):
    sections = []
    sections.append("## Summary\n")
    sections.append("## Last k Messages\n" + format_conversation_history(last_k))
    sections.append("## Recently Extracted Memories\n[]")
    sections.append("## Existing Memories\n" + serialize_memories(existing))
    sections.append("## New Messages\n" + (json.dumps(new_messages,
                                 ensure_ascii=False) if new_messages else "[]"))
    sections.append("## Observation Date\n" + obs_date)
    sections.append("## Current Date\n" + obs_date)
    sections.append("# Output:")
    return "\n\n".join(sections)


def read_mem0_memories(history_db):
    if not history_db or not os.path.exists(history_db):
        return [], None
    con = sqlite3.connect(history_db)
    try:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT * FROM memory_history ORDER BY rowid").fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return [], str(e)
    finally:
        con.close()


def build_mem_body(system, existing, new_messages, last_k, obs_date):
    user = build_mem_user_prompt(existing, new_messages, last_k, obs_date)
    return {
        "model": "bonsai-agent",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "chat_template_kwargs": {"enable_thinking": False},
    }


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #
def pick_steps(inv, max_steps=4):
    runs = inv["runs"]
    picks = []
    for arm in ("baseline", "mem0"):
        cands = [r["run_id"] for r in runs if arm in r["run_id"]]
        if cands:
            picks.append((cands[0], 0))
    if len(picks) < max_steps:
        seen = {p[0] for p in picks}
        for r in runs:
            if r["run_id"] not in seen:
                picks.append((r["run_id"], 0))
                if len(picks) >= max_steps:
                    break
    return picks[:max_steps]


def pick_mem_steps(inv):
    return [(r["run_id"], 0) for r in inv["runs"] if "mem0" in r["run_id"]]


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="test parsing against the in-repo fixture only")
    ap.add_argument("--recon", default=None,
                    help="override recon dir")
    args = ap.parse_args()

    recon_dir = Path(args.recon) if args.recon else (
        BASE / "results" / date.today().isoformat() / "m1-ngram" / "recon")
    if not (recon_dir / "inventory.json").exists() and not args.dry_run:
        for d in sorted((BASE / "results").glob("*/m1-ngram"), reverse=True):
            if (d / "recon" / "inventory.json").exists():
                recon_dir = d / "recon"
                break
    today = recon_dir.parent.parent.name
    out_dir = (BASE / "results") / today / "m1-ngram"

    inv = load_inventory(recon_dir)
    mem0_src = (recon_dir / "mem0_extract_src.txt").read_text()
    mem0_system = extract_additive_extraction_prompt(mem0_src)
    print(f"[info] ADDITIVE_EXTRACTION_PROMPT = {len(mem0_system)} chars "
          f"(~{len(mem0_system)//4} tok)")

    # ---- agent ----
    agent_steps = pick_steps(inv, 4)
    print("[info] agent steps:", agent_steps)
    agent_results, agent_bodies = [], []
    for run_id, step in agent_steps:
        run = find_run(inv, run_id)
        if not run:
            continue
        stepd = run["steps"][str(step)]
        events = read_events(stepd["events_file"])
        msgs = extract_agent_end_messages(events)
        if not msgs:
            continue
        sysmsg = next((m for m in msgs if m.get("role") == "system"), None)
        sys_text, _order, exact = build_pi_system_prompt(sysmsg) if sysmsg else ("", [], False)
        tools = pi_tool_schemas(include_mem0=("mem0" in run_id))
        agent_tap = tap_by_role(stepd, "agent")
        aidx = [i for i, m in enumerate(msgs) if m.get("role") == "assistant"]
        for k, idx in enumerate(aiidx):
            tap = agent_tap[k] if k < len(agent_tap) else None
            body = build_agent_body(msgs, idx, sys_text, tools)
            est = body_char_count(body) // 4
            rec = (tap.get("prompt_n", 0) + tap.get("cache_n", 0)) if tap else 0
            bid = f"{run_id}-s{step}-a{k+1}"
            body["id"] = bid
            agent_bodies.append(body)
            agent_results.append({
                "id": bid,
                "role": "agent",
                "run_id": run_id,
                "step": step,
                "n_messages": idx,
                "recorded_n_messages": (tap.get("n_messages") if tap else None),
                "recorded_prompt_tokens": rec,
                "prompt_chars": body_char_count(body),
                "prompt_chars_over_4": est,
                "est_over_recorded": ratio(est, rec),
                "system_prompt_chars": len(sys_text),
                "system_prompt_exact": exact,
            })

    # ---- mem ----
    mem_results, mem_bodies = [], []
    for run_id, step in pick_mem_steps(inv):
        run = find_run(inv, run_id)
        stepd = run["steps"][str(step)]
        events = read_events(stepd["events_file"])
        msgs = extract_agent_end_messages(events)
        if not msgs:
            continue
        mem_tap = tap_by_role(stepd, "mem")
        hist_db = (run.get("mem0_dbs") or {}).get(
            "memory/mem0-history.db", {}).get("path")
        memories = read_mem0_memories(hist_db)[0]
        for k, tap in enumerate(mem_tap):
            body = build_mem_body(
                mem0_system,
                existing=memories[:max(k, 1)] or memories[:1],
                new_messages=msgs[:1],
                last_k=msgs[:8],
                obs_date=today,
            )
            est = body_char_count(body) // 4
            rec = tap.get("prompt_n", 0) + tap.get("cache_n", 0)
            bid = f"{run_id}-s{step}-m{k+1}"
            body["id"] = bid
            mem_bodies.append(body)
            mem_results.append({
                "id": bid,
                "role": "mem0",
                "run_id": run_id,
                "step": step,
                "n_messages": 2,
                "recorded_prompt_tokens": rec,
                "prompt_chars": body_char_count(body),
                "prompt_chars_over_4": est,
                "est_over_recorded": ratio(est, rec),
                "system_prompt_exact": False,
            })

    write_jsonl(REPLAY_DIR / "agent.jsonl", agent_bodies)
    write_jsonl(REPLAY_DIR / "mem.jsonl", mem_bodies)

    def role_summary(entries, key):
        vals = [r.get(key) for r in entries if r.get(key) is not None]
        return {
            "count": len(entries),
            "distinct_steps": len({(r['run_id'], r['step']) for r in entries}) if entries else 0,
            "median_est_over_recorded": median(entries and [r['est_over_recorded'] for r in entries]),
            "min_est_over_recorded": (min(vals) if vals else None),
            "max_est_over_recorded": (max(vals) if vals else None),
            "total_recorded_tokens": sum(r['recorded_prompt_tokens'] for r in entries),
            "total_est_tokens": sum(r['prompt_chars_over_4'] for r in entries),
            "total_prompt_chars": sum(r['prompt_chars'] for r in entries),
        }

    manifest = {
        "generated": today,
        "source_inventory": str(recon_dir / "inventory.json"),
        "roles": {
            "agent": role_summary(agent_results, "est_over_recorded"),
            "mem0": role_summary(mem_results, "est_over_recorded"),
        },
        "agent_system_prompt_exact": (
            all(r['system_prompt_exact'] for r in agent_results)
            if agent_results else None),
        "entries": agent_results + mem_results,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "replay_manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"[ok] wrote {len(agent_bodies)} agent + {len(mem_bodies)} mem bodies")
    print(f"[ok] manifest -> {out_dir / 'replay_manifest.json'}")
    print("[info] agent median est/rec =",
          manifest['roles']['agent']['median_est_over_recorded'])
    print("[info] mem median est/rec =",
          manifest['roles']['mem0']['median_est_over_recorded'])


def write_jsonl(path, bodies):
    with open(path, "w") as f:
        for b in bodies:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
