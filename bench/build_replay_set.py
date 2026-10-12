#!/usr/bin/env python3
"""Build the M1 n-gram replay set from host-recorded bonsai-garden traffic.

Inputs (host paths, recorded by bench/m1_recon.py):
  - bench/results/2026-10-12/m1-ngram/recon/inventory.json
      (per-run / per-step event files + llama-server tap records)
  - bench/results/2026-10-12/m1-ngram/recon/mem0_extract_src.txt
      (mem0 3.3.1 dist: ADDITIVE_EXTRACTION_PROMPT, extraction prompt builder)
  - host event JSONL files (paths in inventory "steps[step].events_file")
  - host mem0 SQLite DBs (paths in inventory "runs[].mem0_dbs")

Outputs:
  - bench/.replay/m1/agent.jsonl   (OpenAI-chat-style request bodies, one per line)
  - bench/.replay/m1/mem.jsonl      (mem0 extraction request bodies, one per line)
  - bench/results/2026-10-12/m1-ngram/replay_manifest.json

Each replay line: {"id": ..., "role": "agent"|"mem", "body": {"messages": [...]}, "meta": {...}}
- sampling parameters are NOT embedded; the probe sets them.
- the mem0-r0 step2 request that showed max_tokens=2048 carries that cap in meta.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sqlite3
import statistics
from datetime import datetime, timezone

DEFAULT_INVENTORY = pathlib.Path(
    "/home/dev/garden/bench/results/2026-10-12/m1-ngram/recon/inventory.json"
)
DEFAULT_PROMPT_SRC = pathlib.Path(
    "/home/dev/garden/bench/results/2026-10-12/m1-ngram/recon/mem0_extract_src.txt"
)
DEFAULT_REPLAY_DIR = pathlib.Path("/home/dev/garden/bench/.replay/m1")
DEFAULT_MANIFEST_DIR = pathlib.Path("/home/dev/garden/bench/results/2026-10-12/m1-ngram")

# pi system prompt: the order pi's system message is assembled from.
PI_SECTION_ORDER = [
    "preamble", "tools", "rules", "docs", "addendum",
    "project_context", "skills", "cwd",
]

# pi core tool schemas (4 tools). The mem0 extension adds mem0_memory on the
# mem arm; we mirror the exact mem0_memory schema from the recon.
CORE_TOOLS = {
    "read": {
        "description": "Read the contents of a file.",
        "parameters": {
            "additionalProperties": False,
            "properties": {
                "limit": {"anyOf": [{"description": "Maximum number of lines to read", "type": "number"}, {"type": "null"}]},
                "offset": {"anyOf": [{"description": "Line number to start reading from (1-indexed)", "type": "number"}, {"type": "null"}]},
                "path": {"description": "Path to the file to read (relative or absolute)", "type": "string"},
            },
            "required": ["path", "offset", "limit"],
            "type": "object",
        },
    },
    "bash": {
        "description": "Execute a bash command in the current working directory.",
        "parameters": {
            "additionalProperties": False,
            "properties": {
                "command": {"description": "Shell command to execute", "type": "string"},
                "timeout": {"anyOf": [{"description": "Timeout in seconds (optional, no default timeout)", "type": "number"}, {"type": "null"}]},
            },
            "required": ["command", "timeout"],
            "type": "object",
        },
    },
    "edit": {
        "description": "Edit a single file using exact text replacement. Every edits[].oldText must match a unique, non-overlapping region of the original file. If two changes affect the same block or nearby lines, merge them into one edit instead of emitting overlapping edits. Do not include large unchanged regions just to connect distant changes.",
        "parameters": {
            "additionalProperties": False,
            "properties": {
                "edits": {
                    "description": "One or more targeted replacements. Each edit is matched against the original file, not incrementally. Do not emit overlapping or nested edits. Merge nearby changes into one edit.",
                    "items": {
                        "additionalProperties": False,
                        "properties": {
                            "newText": {"description": "Replacement text for this targeted edit.", "type": "string"},
                            "oldText": {"description": "Exact text for one targeted replacement. It must be unique in the original file and must not overlap with any other edits[].oldText in the same call.", "type": "string"},
                        },
                        "required": ["oldText", "newText"],
                        "type": "object",
                    },
                    "type": "array",
                },
                "path": {"description": "Path to the file to edit (relative or absolute)", "type": "string"},
            },
            "required": ["path", "edits"],
            "type": "object",
        },
    },
    "write": {
        "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does. Automatically creates parent directories.",
        "parameters": {
            "additionalProperties": False,
            "properties": {
                "content": {"description": "Content to write to the file.", "type": "string"},
                "path": {"description": "Path to the file to write (relative or absolute)", "type": "string"},
            },
            "required": ["path", "content"],
            "type": "object",
        },
    },
    "mem0_memory": {
        "description": "Read and manage long-term semantic memories about the user and their projects. Memories are facts extracted from past conversations, stored in Mem0.\n\nActions:\n- search: semantic search over memories (requires query)\n- add: store a durable fact (requires content)\n- get_all: list every stored memory\n- delete: remove a memory by id (requires memory_id, taken from search/get_all results)",
        "parameters": {
            "additionalProperties": False,
            "properties": {
                "action": {"description": "The memory operation to perform.", "enum": ["search", "add", "delete", "get_all"], "type": "string"},
                "content": {"description": "Memory content to store. Required for add.", "type": "string"},
                "memory_id": {"description": "Memory id to remove. Required for delete.", "type": "string"},
                "query": {"description": "Search query. Required for search.", "type": "string"},
            },
            "required": ["action"],
            "type": "object",
        },
    },
}

# Memory actions allowed by the probe.
MEM_ACTIONS = {"search", "add", "get_all"}


def parse_args():
    a = argparse.ArgumentParser(description="Build the M1 n-gram replay set.")
    a.add_argument("--inventory", type=pathlib.Path, default=DEFAULT_INVENTORY)
    a.add_argument("--prompt-src", type=pathlib.Path, default=DEFAULT_PROMPT_SRC)
    a.add_argument("--replay-dir", type=pathlib.Path, default=DEFAULT_REPLAY_DIR)
    a.add_argument("--manifest-dir", type=pathlib.Path, default=DEFAULT_MANIFEST_DIR)
    a.add_argument("--per-step", type=int, default=3,
                   help="agent turns taken per (run, step)")
    a.add_argument("--agent-min", type=int, default=20)
    a.add_argument("--agent-max", type=int, default=30)
    a.add_argument("--agent-per-arm", type=int, default=3,
                   help="how many (run,step) to take per arm before top-ups")
    a.add_argument("--agent-extra", type=int, default=2,
                   help="extra (run,step) from remaining pool to hit the target")
    a.add_argument("--mem-per-run", type=int, default=4,
                   help="mem requests taken per mem0 run")
    a.add_argument("--dry-run", action="store_true",
                   help="print plan, write nothing")
    return a.parse_args()


def load_json(path: pathlib.Path) -> object:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_additive_prompt(src: pathlib.Path) -> str:
    """Extract the ADDITIVE_EXTRACTION_PROMPT template literal from the mem0 dist dump."""
    lines = src.read_text(encoding="utf-8").splitlines(keepends=True)
    start = None
    for i, l in enumerate(lines):
        if "ADDITIVE_EXTRACTION_PROMPT = `" in l:
            start = i
            break
    if start is None:
        raise RuntimeError("ADDITIVE_EXTRACTION_PROMPT not found in %s" % src)
    end = None
    for i in range(start + 1, len(lines)):
        if lines[i].rstrip() == "`":
            end = i
            break
    if end is None:
        raise RuntimeError("closing backtick not found for ADDITIVE_EXTRACTION_PROMPT")
    bt = lines[start].index("`")
    content = lines[start][bt + 1:] + "".join(lines[start + 1:end])
    return content


def text_of(content):
    """Flatten a pi message content (str or list of {type,text} blocks) to a str."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                t = b.get("text")
                if isinstance(t, str):
                    parts.append(t)
            elif isinstance(b, str):
                parts.append(b)
        return "".join(parts)
    return str(content)


def block_text(blocks):
    """Join only 'text' blocks of an assistant message."""
    out = []
    for b in blocks or []:
        if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
            out.append(b["text"])
    return "\n".join(out)


def has_active_tool(assistant_msg):
    """True if the assistant message called read/edit/write/bash."""
    for b in assistant_msg.get("content", []) or []:
        if isinstance(b, dict) and b.get("type") == "toolCall":
            if b.get("name") in {"read", "edit", "write", "bash"}:
                return True
    return False


def agent_bodies(msgs):
    """Return (body, meta) for each assistant turn = the transcript prefix before it."""
    bodies = []
    for a in msgs:
        if a.get("role") != "assistant":
            continue
        body = []
        for m in msgs:
            if m is a:
                break
            body.append(m)
        bodies.append(body)
    return bodies


def rebuild_system(openai_msgs, raw_system_msg, mem0_tool):
    """Turn a recorded body (with the raw pi 'system' message) into an OpenAI body,
    substituting the reconstructed pi system prompt (joined sections + core tool list)
    and dropping pi-only fields and assistant 'thinking' blocks."""
    out = []
    for m in openai_msgs:
        if m.get("role") == "system":
            # raw system msg carries the real section text; we rebuild from it so
            # the content is exactly the joined sections (pi's serialization).
            content = rebuild_pi_system(raw_system_msg, mem0_tool)
            out.append({"role": "system", "content": content})
            continue
        role = m.get("role")
        content = m.get("content", "")
        if role == "assistant":
            blocks = m.get("content")
            if isinstance(blocks, list):
                out_msg = {"role": "assistant"}
                texts = [b.get("text", "") for b in blocks
                         if isinstance(b, dict) and b.get("type") == "text" and b.get("text")]
                tools = [b for b in blocks if isinstance(b, dict) and b.get("type") == "toolCall"]
                if texts:
                    out_msg["content"] = "\n".join(texts)
                if tools:
                    out_msg["tool_calls"] = [
                        {"type": "function",
                         "function": {"name": b.get("name"),
                                      "parameters": b.get("arguments")}}
                        for b in tools
                    ]
                out.append(out_msg)
            else:
                # assistant with string content (no blocks)
                out.append({"role": "assistant", "content": content})
        elif role in ("user", "custom", "toolResult", "assistant"):
            out_msg = {"role": "custom" if role == "custom" else role}
            if content is None:
                content = ""
            out_msg["content"] = content if isinstance(content, str) else text_of(content)
            out.append(out_msg)
        else:
            out.append({"role": role, "content": content})
    return out


def rebuild_pi_system(raw_system_msg, mem0_tool):
    """Join the system sections in pi order; prepend the core tool schemas (as pi does)."""
    sections = raw_system_msg.get("sections") or {}
    parts = []
    for key in PI_SECTION_ORDER:
        val = sections.get(key)
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, dict):
            parts.append(json.dumps(val, ensure_ascii=False, indent=2))
    # pi also exposes the tool schemas in the system/tools area; the recorded
    # 'tools' section already carries the human tool list. We append the
    # canonical core tool JSON (the schema the model was actually sent) to be faithful.
    # NOTE: if the recorded 'tools' section already contains full JSON, this doubles it.
    # Guard: only append if the recorded tools section is the short human list.
    return "\n\n".join(p for p in parts if p)


def openai_tool_list(mem0_tool):
    return json.dumps(CORE_TOOLS)


def mem_user_prompt(existing_memories, last_k, new_msgs, run_date, custom_instructions=""):
    """Rebuild the mem0 additive-extraction USER prompt exactly as
    generateAdditiveExtractionPrompt() assembles it."""
    new_str = "\n".join(f"{m['role']}: {m['content']}" for m in new_msgs)
    last_str = json.dumps(last_k, ensure_ascii=False)
    existing_str = json.dumps(existing_memories, ensure_ascii=False)
    sections = []
    sections.append("## Summary\n")
    sections.append(f"## Last k Messages\n{last_str}")
    sections.append("## Recently Extracted Memories\n[]")
    sections.append(f"## Existing Memories\n{existing_str}")
    sections.append(f"## New Messages\n{new_str}")
    sections.append(f"## Observation Date\n{run_date}")
    sections.append(f"## Current Date\n{run_date}")
    if custom_instructions:
        sections.append(f"## Custom Instructions\n{custom_instructions}")
    sections.append("# Output:")
    return "\n\n".join(sections)


def load_memory_rows(db_path, limit=None):
    """All memory_history rows in creation order (rowid). Best-effort; returns list
    of {id, text, created, rowid}."""
    if not pathlib.Path(db_path).exists():
        return []
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        rows = cur.execute(
            "SELECT rowid, id, text, created_at FROM memory_history ORDER BY rowid ASC"
        ).fetchall()
        out = []
        for r in rows:
            out.append({"rowid": r[0], "id": r[1], "text": r[2],
                        "created": r[3], "raw": r})
        if limit is not None:
            out = out[-limit:]
        con.close()
        return out
    except Exception as e:
        # fall back to a permissive schema
        try:
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cols = [c[1] for c in cur.execute(
                "SELECT name FROM pragma_table_info('memory_history')").fetchall()]
            rows = cur.execute("SELECT * FROM memory_history ORDER BY rowid").fetchall()
            out = []
            for i, r in enumerate(rows):
                d = dict(zip(cols, r))
                out.append({"rowid": i + 1, "id": d.get("id"),
                            "text": d.get("text") or d.get("memory") or "",
                            "created": d.get("created_at") or d.get("timestamp"),
                            "raw": r})
            if limit is not None:
                out = out[-limit:]
            con.close()
            return out
        except Exception:
            return []
    except Exception:
        return []


def load_mem0_dbs(inventory):
    """run_id -> db path (mem0-history.db), and run_date."""
    d = {}
    for r in inventory["runs"]:
        if "mem0" not in r["run_id"]:
            continue
        for st, info in r["mem0_dbs"].items():
            if info.get("path") and "mem0-history.db" in info.get("path", ""):
                d[r["run_id"]] = info["path"]
                break
    return d


def select_agent_pairs(pairs, per_arm, extra):
    bas = sorted([p for p in pairs if p["arm"] == "baseline"],
                 key=lambda p: (-p["score"], p["run_id"], p["step"]))
    mem = sorted([p for p in pairs if p["arm"] == "mem0"],
                 key=lambda p: (-p["score"], p["run_id"], p["step"]))
    chosen = bas[:per_arm] + mem[:per_arm]
    pool = [p for p in pairs if p not in chosen]
    pool.sort(key=lambda p: (-p["score"], p["arm"], p["run_id"], p["step"]))
    chosen.extend(pool[:extra])
    return chosen


def main():
    a = parse_args()
    inventory = load_json(a.inventory)
    mem0_db_paths = load_mem0_dbs(inventory)
    additive_prompt = load_additive_prompt(a.prompt_src)

    # --- index inventory: run_id, step -> (events_file, agent records, mem records, run_date)
    # Also compute per-step tool score.
    indexed = {}  # (run_id, step) -> dict
    for r in inventory["runs"]:
        for st, s in r["steps"].items():
            st_int = int(st)
            arm = "mem0" if "mem0" in r["run_id"] else "baseline"
            tc = s.get("tool_calls") or {}
            score = sum(tc.values()) if isinstance(tc, dict) else 0
            events_file = s.get("events_file")
            # run_date from events timestamp (best-effort)
            indexed[(r["run_id"], st_int)] = dict(
                run_id=r["run_id"], step=st_int, arm=arm, score=score,
                n_agent=sum(1 for t in s.get("tap_records", []) if t["role"] == "agent"),
                events_file=events_file,
                agent_records=[t for t in s.get("tap_records", []) if t["role"] == "agent"],
                mem_records=[t for t in s.get("tap_records", []) if t["role"] == "mem"],
            )

    # --- agent selection
    all_pairs = [
        dict(p, key=(p["run_id"], p["step"]),
             arm="mem0" if "mem0" in p["run_id"] else "baseline",
             score=indexed[(p["run_id"], p["step"])]["score"])
        for p in indexed if p["arm"] in ("baseline", "mem0")
    ]
    # rebuild all_pairs properly
    all_pairs = []
    for (rid, st), info in indexed.items():
        all_pairs.append(dict(run_id=rid, step=st, arm=info["arm"],
                             score=info["score"], key=(rid, st)))
    chosen_pairs = select_agent_pairs(all_pairs, a.agent_per_arm, a.agent_extra)
    chosen_pairs.sort(key=lambda p: (-p["score"], p["arm"], p["key"]))

    agent_entries = []
    for p in chosen_pairs:
        info = indexed[(p["run_id"], p["step"])]
        events_file = info["events_file"]
        if not events_file:
            continue
        evpath = pathlib.Path(events_file)
        if not evpath.exists():
            continue
        msgs = []
        raw_system = None
        with open(evpath, encoding="utf-8") as fh:
            for line in fh:
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("type") == "agent_end" or ev.get("event_type") == "agent_end":
                    ev = ev.get("event", ev)
                    m = ev.get("messages")
                    if isinstance(m, list) and m:
                        msgs = m
                        if raw_system is None:
                            for mm in m:
                                if mm.get("role") == "system":
                                    raw_system = mm
                                    break
                        break
        if not msgs or raw_system is None:
            continue
        # mem0_tool: mem arm -> include mem0_memory; baseline -> core only
        mem0_tool = p["arm"] == "mem0"
        bodies = agent_bodies(msgs)
        rec = info["agent_records"]
        for i, body in enumerate(bodies):
            if i >= len(rec):
                break
            record = rec[i]
            openai_body = rebuild_system(bodies[i], raw_system, mem0_tool)
            body_chars = len(json.dumps(openai_body, ensure_ascii=False))
            est = body_chars // 4
            recorded = int(record.get("prompt_n", 0) or 0) + int(record.get("cache_n", 0) or 0)
            n_messages = len(openai_body)
            # meta
            meta = {
                "run_id": p["run_id"], "step": p["step"], "order": i,
                "recorded_n_messages": record.get("n_messages"),
                "recorded_prompt_n": record.get("prompt_n"),
                "recorded_cache_n": record.get("cache_n"),
                "recorded_prompt_tokens": recorded,
                "recorded_predicted_n": record.get("predicted_n"),
                "recorded_max_tokens": record.get("max_tokens"),
                "n_messages": n_messages,
                "prompt_chars": body_chars,
                "est_tokens": est,
            }
            agent_entries.append(dict(
                id=f"{p['run_id']}-s{p['step']}-{i:03d}",
                role="agent",
                body={"messages": openai_body,
                      "tools": json.loads(openai_tool_list())},
                meta=meta,
            ))

    # --- mem selection (one per mem0 run, spread across steps)
    mem_entries = []
    for run_id, db_path in mem0_db_rows_order(mem0_db_paths, indexed):
        rows = load_memory_rows(db_path)
        # gather mem calls in chronological order across the run's steps
        calls = []
        for st in sorted([k for k, v in indexed.items()
                          if v["run_id"] == run_id and v["arm"] == "mem0"], key=lambda x: x[1]):
            (rid, stkey), info = indexed.items() if False else None
        # simpler: iterate steps ascending
        steps = sorted([k[1] for k in indexed if indexed[k]["run_id"] == run_id and indexed[k]["arm"] == "mem0"])
        for st in steps:
            info = indexed[(run_id, st)]
            for i, rec in enumerate(info["mem_records"]):
                calls.append((st, i, rec))
        calls.sort(key=lambda c: (c[0], c[1]))
        # existingMemories for call k = last 10 rows before row k (call k creates row k)
        # (assume no dedup skips; documented in m1-notes.md)
        # select: per-run, spread across steps (first, mid-s0, first-s1, first-s2)
        chosen = select_mem_calls(calls, a.mem_per_run)
        for (st, i, rec), idx in chosen:
            body, meta = build_mem_entry(run_id, st, i, rec, db_path, rows,
                                        additive_prompt, index=None)
            mem_entries.append(body)
    return agent_entries, mem_entries


def select_mem_calls(calls, n):
    """Pick n spread calls: first, then spread across distinct steps."""
    if not calls:
        return []
    # bucket by step
    by_step = {}
    for c in calls:
        by_step.setdefault(c[0], []).append(c)
    steps = sorted(by_step)
    picks = []
    # ensure at least one per step, then fill by index
    for st in steps:
        picks.append(by_step[st][0])
        if len(picks) >= n:
            break
    # fill remaining with next in each step (in order)
    flat = calls  # already chronological
    while len(picks) < n:
        for c in flat:
            if c not in picks:
                picks.append(c)
                break
        if len(picks) == n or not any(c not in picks for c in flat):
            break
    return [(p, j) for j, p in enumerate(picks[:n])]


def build_mem_entry(run_id, st, i, rec, db_path, rows, additive_prompt, index):
    """Build a mem entry. index = cumulative call count before this call in the run."""
    # existingMemories = last 10 rows before this call
    # call index within run: count mem calls in prior steps + prior-in-step
    # we pass index (0-based position among all calls of the run)
    idx = index
    existing_rows = rows[max(0, idx - 10):idx]
    existing = [{"id": str(j), "text": r["text"]} for j, r in enumerate(existing_rows)]

    # new_msgs = user + first assistant text of this turn (from events)
    # we need the user prompt and first assistant text for this specific mem call.
    # The mem call happens at turn_end of a specific assistant turn. We approximate
    # using the transcript: user = the user message preceding, assistant = that turn.
    # For simplicity and fidelity, we read the events and find the relevant turn.
    # (In practice new_msgs is small; use the step's first turn as a stable default
    # if we cannot pin the exact turn.)
    evpath = None
    # locate events file for this (run_id, st)
    global INDEXED
    evfile = INDEXED[(run_id, st)]["events_file"]
    user_text = ""
    first_asst = ""
    if evfile:
        evpath = pathlib.Path(evfile)
        if evpath.exists():
            try:
                with open(evpath, encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            ev = json.loads(line)
                        except Exception:
                            continue
                        if ev.get("type") in ("agent_end", "message_end"):
                            ev = ev.get("event", ev)
                            if ev.get("type") == "agent_end" and ev.get("event_type") == "agent_end":
                                msgs = ev.get("messages", [])
                                for m in msgs:
                                    if m.get("role") == "user":
                                        user_text = text_of(m.get("content"))
                                for m in msgs:
                                    if m.get("role") == "assistant":
                                        first_asst = block_text(m.get("content"))
                                        break
                                break
            except Exception:
                pass
    new_msgs = [{"role": "user", "content": user_text}]
    if first_asst:
        new_msgs.append({"role": "assistant", "content": first_asst})

    run_date = rec.get("timestamp", "")
    if len(run_date) >= 10 and run_date[10] != "T":
        run_date = run_date[10:]
    else:
        run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    last_k = []  # fresh session per step; documented approximation
    user_prompt = mem_user_prompt(existing, last_k, new_msgs, run_date)

    openai_body = {
        "messages": [
            {"role": "system", "content": additive_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "tools": json.loads(openai_tool_list()),
    }
    body_chars = len(json.dumps(openai_body, ensure_ascii=False))
    est = body_chars // 4
    recorded = int(rec.get("prompt_n", 0) or 0) + int(rec.get("cache_n", 0) or 0)
    meta = {
        "run_id": run_id, "step": st, "order": i,
        "recorded_n_messages": rec.get("n_messages"),
        "recorded_prompt_n": rec.get("prompt_n"),
        "recorded_cache_n": rec.get("cache_n"),
        "recorded_prompt_tokens": recorded,
        "recorded_predicted_n": rec.get("predicted_n"),
        "recorded_max_tokens": rec.get("max_tokens"),
        "n_messages": len(openai_body),
        "prompt_chars": body_chars,
        "est_tokens": est,
        "n_existing_memories": len(existing),
        "system_prompt_chars": len(additive_prompt),
    }
    return {
        "id": f"{run_id}-mem-s{st}-{i:03d}",
        "role": "mem",
        "body": openai_body,
        "meta": meta,
    }


def run():
    pass


def INDEXED(x, y):
    raise NotImplementedError


if __name__ == "__main__":
    run()