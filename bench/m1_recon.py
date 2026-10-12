#!/usr/bin/env python3
"""Recon for M1 (n-gram self-speculation on real traffic) — host-only, no GPU.

Runs on the host worktree (cwd = repo worktree root). Populates:

    bench/results/<today>/m1-ngram/recon/
      help.txt              full `llama-server --help` output
      spec_flags.txt        only --spec* / --draft* flag lines (+ continuations)
      spec_mmproj_grep.txt  spec/speculative lines within 5 lines of
                            mtmd/multimodal/mctx (under tools/server/)
      inventory.json        per-run / per-step inventory + mem0 *.db tables+rows
      event_samples.json    one full example per distinct event type (one mem0 step)
      sources.txt           paths to installed pi package + mem0ai index.mjs
      mem0_extract_src.txt  ADDITIVE_EXTRACTION_PROMPT + extraction user-prompt
                            builder (windows around each occurrence)
      pi_prompt_src.txt     pi system-prompt builder + built-in tool schemas

Everything is discovered at runtime (host-only data is not visible from the
sandbox). No GPU, no network, no llama-swap: pure file reads + `llama-server
--help`.
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------- paths ----
CWD = pathlib.Path(os.getcwd()).resolve()

MAIN_REPO = pathlib.Path("/home/josiah/Projects/bonsai-garden")
PRIMARY_SRC = MAIN_REPO / "evals" / "results" / "2026-10-11-baseline-mem0"

# llama.cpp build tree (host ~ = /home/josiah)
LLAMA_BUILD = pathlib.Path(os.environ.get("HOME", "/home/dev")) / "Projects" / "llama.cpp-bonsai2"
LLAMA_SERVER_BIN = LLAMA_BUILD / "build" / "bin" / "llama-server"
LLAMA_SERVER_SRC = LLAMA_BUILD / "tools" / "server"

# Out dir (relative to the worktree cwd, which is the auto/<milestone> tree).
TODAY = datetime.date.today().isoformat()
OUT_DIR = CWD / "bench" / "results" / TODAY / "m1-ngram" / "recon"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def resolve_src() -> pathlib.Path:
    for p in (PRIMARY_SRC, CWD / "evals" / "results" / "2026-10-11-baseline-mem0"):
        if p.exists():
            return p
    raise SystemExit(f"source results dir not found (tried {PRIMARY_SRC} and "
                     f"{CWD / 'evals' / 'results' / '2026-10-11-baseline-mem0'})")


def write_text(path: pathlib.Path, text: str) -> None:
    text = text if text.endswith("\n") else text + "\n"
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- helpers --
def skip_string(text: str, i: int, q: str) -> int:
    """text[i] == q. Return index just past the end of the string."""
    n = len(text)
    i += 1
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c == q:
            return i + 1
        i += 1
    return i  # unterminated


def skip_template(text: str, i: int) -> int:
    """text[i] == `. Return index just past the end of the template literal,
    respecting nested ${...}."""
    n = len(text)
    i += 1
    depth = 0
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c == "`":
            if depth == 0:
                return i + 1
            depth -= 1
        elif c == "$" and i + 1 < n and text[i + 1] == "{":
            depth += 1
        elif c == "}" and depth > 0:
            depth -= 1
        i += 1
    return i


def find_matching_brace(text: str, open_idx: int) -> Optional[int]:
    """text[open_idx] == '{'. Return index of matching '}' (None if not closed),
    respecting strings (\" , ' , `), line and block comments."""
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"':
            i = skip_string(text, i, '"')
            continue
        if c == "'":
            i = skip_string(text, i, "'")
            continue
        if c == "`":
            i = skip_template(text, i)
            continue
        if c == "/" and i + 1 < n:
            if text[i + 1] == "/":
                j = text.find("\n", i)
                i = n if j == -1 else j
                continue
            if text[i + 1] == "*":
                j = text.find("*/", i + 2)
                i = n if j == -1 else j + 2
                continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def find_matching_close(text: str, open_idx: int) -> Optional[int]:
    """text[open_idx] == '('. Return index of matching ')' (None if not closed),
    respecting strings/templates/comments."""
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"':
            i = skip_string(text, i, '"')
            continue
        if c == "'":
            i = skip_string(text, i, "'")
            continue
        if c == "`":
            i = skip_template(text, i)
            continue
        if c == "/" and i + 1 < n:
            if text[i + 1] == "/":
                j = text.find("\n", i)
                i = n if j == -1 else j
                continue
            if text[i + 1] == "*":
                j = text.find("*/", i + 2)
                i = n if j == -1 else j + 2
                continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def extract_function(text: str, func_name: str) -> Optional[str]:
    """Extract the full named function definition (optional `export`/`async`),
    including the `function` keyword. Returns source text or None."""
    pat = re.compile(r"(?:export\s+)?(?:async\s+)?function\s+"
                     + re.escape(func_name) + r"\s*\(")
    m = re.search(pat, text)
    if not m:
        return None
    close_paren = find_matching_close(text, m.end() - 1)  # the signature '('
    if close_paren is None:
        return None
    brace = text.find("{", close_paren + 1)
    if brace == -1:
        return None
    end = find_matching_brace(text, brace)
    if end is None:
        return None
    return text[m.start() : end + 1]


def extract_schema_block(text: str, name: str) -> Optional[str]:
    """Extract a `const <name> = Type.Object({ ... });` assignment from a tool
    file. Returns the raw source (including `const`), or None."""
    m = re.search(r"const\s+" + re.escape(name) + r"\s*=\s*Type\.Object\(", text)
    if not m:
        return None
    obj_open = text.find("{", m.end())
    if obj_open == -1:
        return None
    end_obj = find_matching_brace(text, obj_open)
    if end_obj is None:
        return None
    i = end_obj + 1
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    if i < n and text[i] == ")":
        i += 1
        while i < n and text[i].isspace():
            i += 1
    if i < n and text[i] == ";":
        i += 1
    return text[m.start() : i]


# ---------------------------------------------------------------- events --
def read_jsonl(path: pathlib.Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def parse_events(path: pathlib.Path) -> Dict[str, Any]:
    """Defensively summarise a pi `stepN.events.jsonl`.

    pi `--mode json` event types (docs/json.md):
      session header, agent_start, turn_start, message_start, message_update,
      message_end, turn_end, tool_execution_start, tool_execution_update,
      tool_execution_end, queue_update, compaction_start/end, agent_end.

    Assistant message -> `message_end` with message.role == "assistant".
    Tool call          -> `tool_execution_start` with toolName.
    """
    events = read_jsonl(path)
    event_types: Dict[str, int] = {}
    tool_calls: Dict[str, int] = {}
    assistant_msgs = 0
    for e in events:
        t = e.get("type")
        if t is None:
            t = "<no-type>"
        event_types[t] = event_types.get(t, 0) + 1
        if t == "message_end":
            msg = e.get("message") or {}
            if msg.get("role") == "assistant":
                assistant_msgs += 1
        if t == "tool_execution_start":
            name = e.get("toolName") or e.get("tool_name") or "unknown"
            tool_calls[name] = tool_calls.get(name, 0) + 1
    return {
        "n_events": len(events),
        "event_types": event_types,
        "n_assistant_messages": assistant_msgs,
        "tool_calls": tool_calls,
    }


def match_tap_records(tap: List[Dict[str, Any]], run_id: str, step_i: int) -> List[Dict[str, Any]]:
    """Tap records for this run+step (completions requests only)."""
    kept: List[Dict[str, Any]] = []
    target = str(step_i)
    for r in tap:
        if r.get("run") != run_id:
            continue
        s = r.get("step")
        if str(s) != target:
            continue
        if not (r.get("path") or "").endswith("/completions"):
            continue
        tm = r.get("timings") or {}
        kept.append({
            "role": r.get("role"),
            "path": r.get("path"),
            "model": r.get("model"),
            "status": r.get("status"),
            "n_messages": r.get("n_messages"),
            "prompt_n": tm.get("prompt_n"),
            "cache_n": tm.get("cache_n"),
            "predicted_n": tm.get("predicted_n"),
        })
    return kept


def inspect_sqlite(path: pathlib.Path) -> Dict[str, Any]:
    """Read-only: list tables/views/indices + row counts for a sqlite file."""
    out: Dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if not path.exists():
        out["error"] = "missing"
        return out
    try:
        conn = sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True, timeout=5)
        tables: List[Dict[str, Any]] = []
        try:
            cur = conn.execute(
                "SELECT name, type FROM sqlite_master "
                "WHERE type IN ('table','view','index') ORDER BY type DESC, name"
            )
            for name, typ in cur.fetchall():
                n = -1
                if typ == "table":
                    try:
                        n = conn.execute(
                            'SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"'
                        ).fetchone()[0]
                    except sqlite3.Error:
                        n = -1
                tables.append({"name": name, "type": typ, "rows": n})
        finally:
            conn.close()
        out["tables"] = tables
    except Exception as ex:
        out["error"] = f"sqlite open/scan failed: {ex!r}"
    return out


def build_inventory(src: pathlib.Path) -> Dict[str, Any]:
    runs_dir = src / "runs"
    tap = read_jsonl(src / "tap.jsonl")
    inventory: Dict[str, Any] = {"runs": [], "tap_record_total": len(tap)}
    if not runs_dir.exists():
        return inventory
    for run_dir in sorted(runs_dir.iterdir(), key=lambda p: p.name):
        if not run_dir.is_dir():
            continue
        rid = run_dir.name
        steps: Dict[str, Dict[str, Any]] = {}
        ev_files = sorted(run_dir.glob("step*.events.jsonl"))
        step_keys = []
        for ef in ev_files:
            m = re.match(r"step(\d+)\.events\.jsonl$", ef.name)
            if m:
                step_keys.append(int(m.group(1)))
        for step_i in sorted(step_keys):
            ef = run_dir / f"step{step_i}.events.jsonl"
            inv = parse_events(ef)
            inv["events_file"] = str(ef)
            inv["events_size"] = ef.stat().st_size if ef.exists() else None
            inv["tap_records"] = match_tap_records(tap, rid, step_i)
            roles: Dict[str, Dict[str, int]] = {}
            for tr in inv["tap_records"]:
                role = tr.get("role", "unknown")
                a = roles.setdefault(role,
                    {"requests": 0, "prompt_n": 0, "cache_n": 0, "predicted_n": 0})
                a["requests"] += 1
                for k in ("prompt_n", "cache_n", "predicted_n"):
                    a[k] += tr.get(k) or 0
            inv["tap_role_totals"] = roles
            steps[str(step_i)] = inv
        mem0_dbs: Dict[str, Dict[str, Any]] = {}
        for db in sorted(run_dir.rglob("*.db")):
            rel = db.relative_to(run_dir)
            mem0_dbs[str(rel)] = inspect_sqlite(db)
        inventory["runs"].append({"run_id": rid, "steps": steps, "mem0_dbs": mem0_dbs})
    return inventory


def choose_mem0_step(src: pathlib.Path) -> Optional[Dict[str, Any]]:
    """Pick the mem0-arm step with the most distinct event types (richest sample)."""
    runs_dir = src / "runs"
    if not runs_dir.exists():
        return None
    best = None
    best_score = -1
    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        is_mem0 = (any((run_dir / "memory" / x).exists()
                       for x in ("mem0-vectors.db", "mem0-history.db"))
                   or "-mem0-" in run_dir.name)
        if not is_mem0:
            continue
        for ef in run_dir.glob("step*.events.jsonl"):
            evs = read_jsonl(ef)
            n_distinct = len({e.get("type") for e in evs})
            score = n_distinct * 1000 + len(evs)
            if score > best_score:
                best_score = score
                best = {
                    "run": run_dir.name,
                    "events_file": str(ef),
                    "n_events": len(evs),
                    "n_distinct_types": n_distinct,
                }
                best["_events"] = evs
    if best is None:
        return None
    evs = best.pop("_events")
    return {**best, "events": evs}


def build_event_samples(src: pathlib.Path) -> Dict[str, Any]:
    """One complete, untruncated example per distinct event type from a single
    mem0-arm step (chosen by choose_mem0_step)."""
    chosen = choose_mem0_step(src)
    if not chosen:
        return {"error": "no mem0-arm step found", "steps_scanned": 0}
    samples: Dict[str, Dict[str, Any]] = {}
    for i, e in enumerate(chosen["events"]):
        t = e.get("type")
        if t is None:
            t = "<no-type>"
        if t not in samples:
            samples[t] = {"line": i, "event": e}
    chosen.pop("events", None)
    return {
        "chosen_step": chosen,
        "n_distinct_types": len(samples),
        "samples": samples,
    }


# ---------------------------------------------------------------- sources --
def find_pi() -> Optional[pathlib.Path]:
    """Locate the installed pi package. Same derivation as run.py
    (which(pi).resolve().parents), plus common global install dirs."""
    cands: List[pathlib.Path] = []
    try:
        pi = shutil.which("pi")
        if pi:
            cur = pathlib.Path(pi).resolve()
            while True:
                cands.append(cur / "lib" / "node_modules" /
                             "@earendil-works" / "pi-coding-agent")
                cur = cur.parent
                if cur == pathlib.PurePath("/"):
                    break
    except Exception:
        pass
    home = os.environ.get("HOME", "/root")
    cands += [
        pathlib.Path(home) / "node" / "lib" / "node_modules"
            / "@earendil-works" / "pi-coding-agent",
        pathlib.Path(home) / ".npm-global" / "node_modules"
            / "@earendil-works" / "pi-coding-agent",
        pathlib.Path("/opt/node/lib/node_modules") / "@earendil-works" / "pi-coding-agent",
        pathlib.Path("/usr/lib/node_modules") / "@earendil-works" / "pi-coding-agent",
    ]
    seen = set()
    for c in cands:
        try:
            rc = c.resolve()
        except Exception:
            continue
        if rc in seen:
            continue
        if (rc / "package.json").exists():
            seen.add(rc)
            return rc
    return None


def find_mem0ai(src: pathlib.Path) -> Optional[pathlib.Path]:
    """Return the mem0ai package directory (the one holding dist/oss/index.mjs).
    Search the evals cache, the results (symlinked agent dirs), and global
    node_modules."""
    roots: List[pathlib.Path] = []
    for base in (MAIN_REPO, CWD):
        if base.exists():
            roots.append(base / "evals" / ".cache")
            roots.append(base / "evals" / "results")
    home = pathlib.Path(os.environ.get("HOME", "/root"))
    roots.append(home / "node_modules")
    roots.append(home / ".npm-global" / "node_modules")
    roots.append(pathlib.Path("/opt/node/lib/node_modules"))

    hits: List[pathlib.Path] = []
    seen = set()

    def add(p: pathlib.Path) -> None:
        try:
            r = p.resolve()
        except Exception:
            return
        if r in seen:
            return
        if (r / "dist" / "oss" / "index.mjs").exists():
            seen.add(r)
            hits.append(r)

    # First pass: direct node_modules hits.
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("node_modules/mem0ai"):
            add(p)
        for p in root.rglob("mem0ai"):
            add(p)

    # Fallback: any index.mjs under dist/oss anywhere under the evals tree.
    if not hits:
        for base in (MAIN_REPO, CWD):
            if not base.exists():
                continue
            for idx in base.rglob("dist/oss/index.mjs"):
                add(idx.parent.parent)

    if not hits:
        return None
    return hits[0]


def _read_index(m0dir: Optional[pathlib.Path]) -> Optional[Dict[str, Any]]:
    if not m0dir:
        return None
    idx = m0dir / "dist" / "oss" / "index.mjs"
    if not idx.exists():
        return None
    try:
        return {"path": str(idx), "text": idx.read_text(encoding="utf-8", errors="replace")}
    except Exception:
        return None


def extract_additive_extraction_prompt(m0dir: Optional[pathlib.Path]) -> Optional[str]:
    """Extract the full ADDITIVE_EXTRACTION_PROMPT constant from mem0ai."""
    data = _read_index(m0dir)
    if not data:
        return None
    txt = data["text"]
    m = re.search(r"(?:const|let|var)\s+ADDITIVE_EXTRACTION_PROMPT\s*=\s*", txt)
    if not m:
        return None
    start = m.start()
    # Find the end of the template literal (backticks, possibly multi-line).
    i = txt.find("`", m.end() - 1)
    if i == -1:
        # Fallback: grab to the next semicolon on a sane line.
        j = txt.find(";", m.end())
        return txt[start : (j + 1 if j != -1 else len(txt))]
    # Skip to the closing backtick, handling escaped backticks + nested templates.
    end = i + 1
    n = len(txt)
    while end < n:
        c = txt[end]
        if c == "\\" and end + 1 < n:
            end += 2
            continue
        if c == "`":
            break
        end += 1
    return txt[start : end + 1]


def _named_function_defs(text: str):
    """Yield (start, end, name) for `export? async? function NAME(args) { ... }`."""
    for m in re.finditer(
        r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", text):
        close = find_matching_close(text, m.end() - 1)
        if close is None:
            continue
        brace = text.find("{", close + 1)
        if brace == -1:
            continue
        end = find_matching_brace(text, brace)
        if end is None:
            continue
        yield m.start(), end, m.group(1)


def _arrow_function_defs(text: str):
    """Yield (start, end, name) for `const/let/var NAME = (async)?(params) => { ...}`."""
    for m in re.finditer(
        r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\(", text):
        close = find_matching_close(text, m.end() - 1)
        if close is None:
            continue
        j = close + 1
        while j < len(text) and text[j].isspace():
            j += 1
        if not text.startswith("=>", j):
            continue
        j += 2
        while j < len(text) and text[j].isspace():
            j += 1
        if j >= len(text) or text[j] != "{":
            continue
        end = find_matching_brace(text, j)
        if end is None:
            continue
        yield m.start(), end, m.group(1)


def extract_functions_referencing(text, needle):
    """Extract full function definitions whose body references `needle`."""
    blocks = []
    seen = set()
    defs = list(_named_function_defs(text)) + list(_arrow_function_defs(text))
    for start, end, name in defs:
        if start in seen:
            continue
        if needle not in text[start:end + 1]:
            continue
        seen.add(start)
        line = text[:start].count("\n")
        blocks.append(
            f"===== function {name} (starts line {line + 1}) "
            f"references {needle} =====\n" + text[start:end + 1])
    return blocks


def extract_extraction_user_prompt(m0dir: Optional[pathlib.Path]) -> Optional[str]:
    """Labelled windows around every occurrence of ADDITIVE_EXTRACTION_PROMPT in
    the mem0ai source — the definition plus the functions that build the
    extraction user prompt and call the LLM."""
    data = _read_index(m0dir)
    if not data:
        return None
    txt = data["text"]
    needle = "ADDITIVE_EXTRACTION_PROMPT"
    occurrences = [m.start() for m in re.finditer(re.escape(needle), txt)]
    blocks = []
    for idx, occ in enumerate(occurrences):
        lines = txt[:occ].count("\n")
        before = max(0, occ - 30 * 130)
        after = min(len(txt), occ + 70 * 130)
        label = "definition" if idx == 0 else f"usage#{idx}"
        blocks.append(
            f"===== {label} @ line {lines + 1} ({data['path']}) =====\n" +
            txt[before:after])
    blocks.extend(extract_functions_referencing(txt, needle))
    if not blocks:
        return None
    return "\n\n".join(blocks)


def extract_named_function_anywhere(m0dir: Optional[pathlib.Path],
                                    func_name: str) -> Optional[Dict[str, Any]]:
    """Search every JS/TS file under m0dir/dist/ for a function definition
    named func_name (classic declaration or const/let/var arrow). Returns
    {"path": str, "src": str} or None. Used for generateAdditiveExtractionPrompt
    (the extraction user-prompt builder), which may live in a dist file other
    than dist/oss/index.mjs."""
    if not m0dir or not (m0dir / "dist").exists():
        return None
    patterns = ("*.js", "*.mjs", "*.ts", "*.tsx")
    files: List[pathlib.Path] = []
    for pat in patterns:
        try:
            files.extend((m0dir / "dist").rglob(pat))
        except Exception:
            continue
    for f in sorted(set(files), key=lambda p: str(p)):
        if not f.is_file():
            continue
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        fn = extract_function(txt, func_name)
        if fn:
            return {"path": str(f), "src": fn}
        for start, end, name in (list(_named_function_defs(txt))
                                  + list(_arrow_function_defs(txt))):
            if name == func_name:
                return {"path": str(f), "src": txt[start:end + 1]}
    return None


def extract_pi_src() -> Dict[str, Any]:
    """Extract the pi system-prompt builder and built-in tool schemas."""
    pi = find_pi()
    out: Dict[str, Any] = {"pi_package": str(pi) if pi else None}
    if not pi:
        return out
    sysprompt = pi / "dist" / "core" / "system-prompt.js"
    out["system_prompt_file"] = str(sysprompt) if sysprompt.exists() else None
    if sysprompt.exists():
        out["system_prompt_src"] = sysprompt.read_text(encoding="utf-8", errors="replace")

    tools_dir = pi / "dist" / "core" / "tools"
    out["tools_dir"] = str(tools_dir)
    registry = tools_dir / "index.js"
    if registry.exists():
        out["tools_index_src"] = registry.read_text(encoding="utf-8", errors="replace")

    tool_schemas: List[Dict[str, Any]] = []
    skip_names = {"index", "path-utils", "truncate", "tool-definition-wrapper",
                  "renderers", "path-utils.d"}
    if tools_dir.exists():
        for tf in sorted(tools_dir.glob("*.js")):
            if tf.stem in skip_names:
                continue
            name = tf.stem  # e.g. read, bash, edit
            src = tf.read_text(encoding="utf-8", errors="replace")
            fn_name = "create" + name[0].upper() + name[1:] + "ToolDefinition"
            rec: Dict[str, Any] = {"tool": name, "file": str(tf)}
            func = extract_function(src, fn_name)
            if func:
                rec["function"] = fn_name
                rec["function_src"] = func
            schema_const = re.search(
                r"const\s+([a-zA-Z_][a-zA-Z0-9_]*)Schema\s*=\s*Type\.Object\(", src)
            if schema_const:
                schema_block = extract_schema_block(src, schema_const.group(1))
                if schema_block:
                    rec["schema_const"] = schema_const.group(1)
                    rec["schema_src"] = schema_block
            tool_schemas.append(rec)
    out["tool_schemas"] = tool_schemas
    return out


# ---------------------------------------------------------------- main ----
def main() -> None:
    print(f"[recon] out dir: {OUT_DIR}", file=sys.stderr)
    src = resolve_src()
    print(f"[recon] src dir: {src}", file=sys.stderr)

    # ---- llama-server help + spec flags ----
    help_text = None
    if not LLAMA_SERVER_BIN.exists():
        print(f"[recon] WARNING: {LLAMA_SERVER_BIN} missing; skipping --help",
              file=sys.stderr)
    else:
        try:
            p = subprocess.run([str(LLAMA_SERVER_BIN), "--help"],
                               capture_output=True, text=True, timeout=60,
                               cwd=str(LLAMA_BUILD))
            help_text = p.stdout
            if p.stderr and not p.stdout:
                help_text = "\n---stderr---\n" + p.stderr
        except Exception as ex:
            help_text = f"llama-server --help failed: {ex!r}\n"
    if help_text:
        write_text(OUT_DIR / "help.txt", help_text)
        spec_lines: List[str] = []
        in_block = False
        spec_draft_re = re.compile(r"--(spec|draft)")
        for line in help_text.splitlines():
            s = line.strip()
            if s.startswith("-"):
                if spec_draft_re.search(s):
                    spec_lines.append(line)
                    in_block = True
                else:
                    in_block = False
            else:
                if in_block:
                    if s == "":
                        in_block = False
                    else:
                        spec_lines.append(line)
        if spec_lines:
            write_text(OUT_DIR / "spec_flags.txt", "\n".join(spec_lines) + "\n")
        else:
            write_text(OUT_DIR / "spec_flags.txt",
                       f"NOTE: no --spec* / --draft* flags found in help text.\n"
                       f"(help text is {len(help_text)} bytes; see help.txt)\n")

    # ---- spec/mmproj proximity grep ----
    uniq: List[str] = []
    if LLAMA_SERVER_SRC.exists():
        spec_pat = re.compile(r"(?i)speculative|spec")
        mm_pat = re.compile(r"(?i)mtmd|multimodal|mctx")
        patterns = ("*.js", "*.mjs", "*.ts", "*.tsx",
                    "*.cpp", "*.cxx", "*.cc", "*.h", "*.hh", "*.hpp", "*.py", "*.md")
        files: set = set()
        for pat in patterns:
            try:
                files.update(LLAMA_SERVER_SRC.rglob(pat))
            except Exception:
                continue
        for root in sorted(files, key=lambda p: str(p)):
            try:
                lines = root.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            mm_i = [i for i, ln in enumerate(lines, 1) if mm_pat.search(ln)]
            for i, ln in enumerate(lines, 1):
                if spec_pat.search(ln) and any(abs(i - m) <= 5 for m in mm_i):
                    uniq.append(f"{root.relative_to(LLAMA_SERVER_SRC)}:{i}: {ln.strip()}")
    if uniq:
        write_text(OUT_DIR / "spec_mmproj_grep.txt", "\n".join(uniq) + "\n")
    else:
        write_text(OUT_DIR / "spec_mmproj_grep.txt",
                   "NOTE: no spec/speculative lines within 5 lines of "
                   "mtmd/multimodal/mctx found under tools/server/\n")

    # ---- auxiliary: full listing of spec/mmproj-related lines in the server
    # context files (no mmproj-proximity requirement) — used to cross-check the
    # spec+mmproj gating lines quoted in bench/m1-notes.md §3.
    full_lines: List[str] = []
    if LLAMA_SERVER_SRC.exists():
        for name in ("server-context.cpp", "server-common.h"):
            p = LLAMA_SERVER_SRC / name
            if not p.exists():
                continue
            try:
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, ln in enumerate(lines, 1):
                if re.search(r"(?i)spec|speculative|mctx|multimodal|mmproj", ln):
                    full_lines.append(f"{name}:{i}: {ln.strip()}")
    if full_lines:
        write_text(OUT_DIR / "spec_lines_full.txt",
                   "\n".join(full_lines) + "\n")

    # ---- inventory + event samples ----
    inv = build_inventory(src)
    (OUT_DIR / "inventory.json").write_text(
        json.dumps(inv, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    es = build_event_samples(src)
    (OUT_DIR / "event_samples.json").write_text(
        json.dumps(es, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # ---- sources + extracted source text ----
    pi_src = extract_pi_src()
    m0dir = find_mem0ai(src)
    add = extract_additive_extraction_prompt(m0dir)
    user = extract_extraction_user_prompt(m0dir)
    index = (m0dir / "dist" / "oss" / "index.mjs") if m0dir else None
    # Full body of the extraction user-prompt builder (may live in a dist file
    # other than dist/oss/index.mjs).
    upb = extract_named_function_anywhere(
        m0dir, "generateAdditiveExtractionPrompt")
    # Built-in tool schemas as seen on the wire (message_start.message.toolsAdded).
    tools_added = None
    if isinstance(es, dict):
        ms = (es.get("samples") or {}).get("message_start")
        if isinstance(ms, dict):
            e = ms.get("event") or {}
            tools_added = (e.get("message") or {}).get("toolsAdded")

    sources_lines = [
        f"pi_package_dir: {pi_src['pi_package'] or 'NOT FOUND'}",
        f"mem0ai_pkg_dir: {str(m0dir) if m0dir else 'NOT FOUND'}",
        f"mem0ai_dist_oss_index_mjs: {str(index) if index else 'NOT FOUND'}",
        "",
        f"pi_system_prompt_file: {pi_src.get('system_prompt_file') or 'NOT FOUND'}",
        f"pi_tools_dir: {pi_src.get('tools_dir') or 'NOT FOUND'}",
        f"pi_tools_index.js: {'found' if pi_src.get('tools_index_src') else 'NOT FOUND'}",
        f"mem0_additive_extraction_prompt: "
            f"{'found' if add else 'NOT FOUND / empty'}",
        f"mem0_extraction_user_prompt_windows: "
            f"{'found' if user else 'NOT FOUND / empty'}",
        (f"mem0_generateAdditiveExtractionPrompt: found @ {upb['path']}"
         if upb else "mem0_generateAdditiveExtractionPrompt: NOT FOUND (searched dist/)"),
        f"built_in_tool_schemas_extracted: {len(pi_src.get('tool_schemas', []))}",
    ]
    for rec in pi_src.get("tool_schemas", []):
        extra = f" (function={rec.get('function')}, schema={rec.get('schema_const')})" if rec.get("function_src") else ""
        sources_lines.append(f"  - {rec['tool']} {rec['file']}{extra}")
    write_text(OUT_DIR / "sources.txt", "\n".join(sources_lines) + "\n")

    # mem0_extract_src.txt
    mem0_src = [
        "# mem0_extract_src.txt",
        f"# source: {str(m0dir) if m0dir else 'mem0ai not found'}",
        f"# index: {str(index) if index else 'NOT FOUND'}",
        "",
        "# ADDITIVE_EXTRACTION_PROMPT (full, untruncated)",
        add or "(not found)",
        "",
        "# Windows around ADDITIVE_EXTRACTION_PROMPT",
        "# (definition + the functions building the extraction user prompt)",
        user or "(not found)",
    ]
    if upb:
        mem0_src += [
            "",
            "# generateAdditiveExtractionPrompt (full body — extraction user prompt template)",
            f"# source: {upb['path']}",
            upb["src"],
        ]
    else:
        mem0_src += [
            "",
            "# generateAdditiveExtractionPrompt: NOT FOUND under dist/ (searched all JS/TS files)",
        ]
    write_text(OUT_DIR / "mem0_extract_src.txt", "\n\n".join(mem0_src) + "\n")

    # pi_prompt_src.txt
    ps = [
        "# pi_prompt_src.txt",
        f"# pi package: {pi_src['pi_package'] or 'NOT FOUND'}",
        "",
        "# --- dist/core/system-prompt.js ---",
        (pi_src.get("system_prompt_src") or "(not found)") + "\n",
        "# --- dist/core/tools/index.js ---",
        (pi_src.get("tools_index_src") or "(not found)") + "\n",
        "# --- built-in tool definitions + schemas ---",
    ]
    for rec in pi_src.get("tool_schemas", []):
        ps.append(f"\n# tool: {rec['tool']}  file: {rec['file']}")
        if rec.get("schema_src"):
            ps.append(rec["schema_src"])
        if rec.get("function_src"):
            ps.append(rec["function_src"])
    # Built-in tool schemas as seen on the wire, from the chosen step's
    # message_start event (event_samples.json).
    if tools_added is not None:
        ps.append("")
        ps.append("# --- message_start.message.toolsAdded (full built-in tool schemas, from event_samples) ---")
        ps.append(json.dumps(tools_added, indent=2, ensure_ascii=False))
    elif isinstance(es, dict) and es.get("n_distinct_types", 0) > 0:
        ps.append("")
        ps.append("# --- message_start.message.toolsAdded: not present in the chosen step's sample ---")
    write_text(OUT_DIR / "pi_prompt_src.txt", "\n".join(ps) + "\n")

    written: Dict[str, Any] = {}
    for f in sorted(OUT_DIR.iterdir()):
        written[f.name] = f.stat().st_size if f.is_file() else "-"
    print(f"[recon] done -> {OUT_DIR}")
    print(json.dumps({"out_dir": str(OUT_DIR), "files": written}, indent=2))


if __name__ == "__main__":
    main()
