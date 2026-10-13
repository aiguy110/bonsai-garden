#!/usr/bin/env python3
"""Checkpoint-spacing probe: replay an agent-shaped, tool-calling conversation
against a private llama-server and record how many prompt tokens each turn
re-processes. Run under a turnstile lease:

  turnstile_run.py -- python3 bench/checkpoint_replay.py OUTDIR CMS [extra server args...]

The conversation grows every turn (fake read_file tool returning real source
files), thinking is on, and the assistant's reasoning is NOT sent back, so the
chat template's handling of earlier <think> blocks is exercised exactly as an
OpenAI-style client (pi) would. Greedy sampling keeps runs comparable across
CMS values. Per-turn timings go to OUTDIR/replay_cms<CMS>.jsonl.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

OUT, CMS = sys.argv[1], sys.argv[2]
EXTRA = sys.argv[3:]
PORT = 8089
TURNS = int(os.environ.get("TURNS", "14"))
B = os.path.expanduser("~/Projects/llama.cpp-bonsai2/build/bin/llama-server")
M = os.path.expanduser("~/models")
SRC = os.path.expanduser("~/Projects/llama.cpp-bonsai2")
FILES = [
    "tools/server/server-task.cpp", "tools/server/server-queue.cpp",
    "common/sampling.cpp", "common/chat.cpp", "src/llama-batch.cpp",
    "src/llama-kv-cache.cpp", "src/llama-memory-recurrent.cpp",
    "tools/server/utils.hpp", "src/llama-context.cpp", "common/arg.cpp",
]
SYSTEM = ("You are a coding agent working in the llama.cpp repository. Use the "
          "read_file tool to inspect files before answering. Keep answers short.")
TOOLS = [{"type": "function", "function": {
    "name": "read_file",
    "description": "Read a file from the repository (first ~6000 chars).",
    "parameters": {"type": "object", "properties": {
        "path": {"type": "string", "description": "repo-relative path"}},
        "required": ["path"]}}}]


def read(path):
    try:
        with open(os.path.join(SRC, path), errors="replace") as f:
            return f.read(6000)
    except OSError as e:
        return f"error: {e}"


def post(body):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.load(r)


def main():
    os.makedirs(OUT, exist_ok=True)
    log = open(f"{OUT}/replay_cms{CMS}.server.log", "w")
    env = dict(os.environ, LLAMA_ATTN_ROT_DISABLE="1")
    srv = subprocess.Popen([
        B, "--model", f"{M}/Ternary-Bonsai-2-27B-PQ2_0.gguf",
        "--mmproj", f"{M}/Ternary-Bonsai-2-27B-mmproj-Q8_0.gguf", "--no-mmproj-offload",
        "--port", str(PORT), "-ngl", "99", "-c", "98304", "--threads", "8", "-fa", "on",
        "-ctk", "q4_0", "-ctv", "q4_0",
        "--kv-mean-center", f"{M}/Ternary-Bonsai-2-27B-PQ2_0-kv-bias.gguf",
        "--jinja", "-cms", CMS, *EXTRA], stdout=log, stderr=subprocess.STDOUT, env=env)
    try:
        for _ in range(180):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
                break
            except Exception:
                time.sleep(1)
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Walk me through how the server turns a chat "
                 "request into decoded tokens. Read the relevant files one at a time, "
                 f"starting with {FILES[0]}, and summarize each in two sentences."}]
        nxt = 1
        with open(f"{OUT}/replay_cms{CMS}.jsonl", "w") as out:
            for turn in range(TURNS):
                r = post({"messages": msgs, "tools": TOOLS, "max_tokens": 768,
                          "temperature": 0, "top_k": 1, "seed": 0})
                t = r["timings"]
                msg = r["choices"][0]["message"]
                calls = msg.get("tool_calls") or []
                rec = {"turn": turn, "n_msgs": len(msgs), "prompt_n": t["prompt_n"],
                       "cache_n": t.get("cache_n"), "prompt_ms": round(t["prompt_ms"]),
                       "predicted_n": t["predicted_n"],
                       "decode_tps": round(t["predicted_per_second"], 1),
                       "tool_calls": len(calls)}
                print(json.dumps(rec), flush=True)
                out.write(json.dumps(rec) + "\n")
                # send back content + tool calls only, never reasoning (OpenAI-client shape)
                back = {"role": "assistant", "content": msg.get("content") or ""}
                if calls:
                    back["tool_calls"] = calls
                msgs.append(back)
                if calls:
                    for c in calls:
                        try:
                            path = json.loads(c["function"]["arguments"]).get("path", "")
                        except Exception:
                            path = ""
                        msgs.append({"role": "tool", "tool_call_id": c.get("id", ""),
                                     "content": read(path)})
                else:
                    f = FILES[nxt % len(FILES)]
                    nxt += 1
                    msgs.append({"role": "user", "content": f"Now read {f} and summarize it."})
    finally:
        srv.terminate()
        srv.wait()
        log.close()


if __name__ == "__main__":
    main()
