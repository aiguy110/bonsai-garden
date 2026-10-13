---
layer: experiment
series: memory-layers
title: How mem0 plugs into pi
status: done
date: 2026-10-11
updated: 2026-10-11
tldr: A walk through the pi-memory-mem0 extension and mem0's write and search paths, with what our eval runs actually stored.
summary: |
  **What it is:** `@amaster.ai/pi-memory-mem0` 0.1.24, a pi extension that runs
  mem0 OSS 3.3.1 *inside* pi's process. All its LLM calls go to Bonsai's second
  slot (`bonsai-mem`), and embeddings come from a CPU server.

  **How it hooks in:** four pi events.
  - `input` remembers the prompt and starts a memory search in the background.
  - `before_agent_start` waits up to 3 s for the results and injects them as a
    user-channel message.
  - `turn_end` sends the prompt plus the **first** assistant reply with text to
    mem0.
  - `session_shutdown` waits for pending writes.

  The agent also gets a `mem0_memory` tool (search, add, list, delete).

  **What a write costs:** one LLM call with a ~36 KB system prompt, plus the 10
  nearest existing memories, plus the new messages. mem0 3.x only **adds**
  memories and skips exact duplicates. It never updates or deletes.

  **What we saw:** in the eval runs Bonsai used the tool on its own to save the
  conventions and the staging host. One run saved the same fact 4 times in
  different words, and the store kept 2 copies. The ~8k-token prompt was reused
  from cache in only 4 of 22 writes.
---

Versions: extension
[0.1.24](https://cdn.jsdelivr.net/npm/@amaster.ai/pi-memory-mem0@0.1.24/dist/index.js)
(TypeScript source:
[TGYD-helige/pi](https://github.com/TGYD-helige/pi/tree/master/packages/pi-memory-mem0/src)),
mem0 [3.3.1](https://cdn.jsdelivr.net/npm/mem0ai@3.3.1/dist/oss/index.mjs). Line
numbers below refer to these published builds. Our configuration is
[`evals/arms/mem0.json`](https://github.com/aiguy110/bonsai-garden/blob/main/evals/arms/mem0.json).

## The pieces

```
pi process
 ├─ pi-memory-mem0 extension      (index.js: event hooks, /mem0 command)
 │    ├─ Prefetch                  (prefetch.js: background search, 3 s timeout)
 │    ├─ mem0_memory tool          (tools.js)
 │    └─ OSSProvider               (provider.js: wraps mem0's Memory class)
 │         └─ mem0 Memory          (mem0ai/oss)
 │              ├─ LLM      → bonsai-mem   (turnstile → llama-server slot 1)
 │              ├─ embedder → Qwen3-Embedding-0.6B on CPU (:8095)
 │              └─ store    → SQLite: vectors + history, one file per run
```

## Session start: wiring

`session_start` (index.js L79–202) reads the `pi-memory-mem0` block from
`settings.json` and builds the provider. Three details matter for the evals:

- **Memory is per workspace.** The user id becomes
  `garden:project:<sha256(cwd)[:12]>` (`scopeMemoryUserId`, privacy.js L4–9). A
  different directory gets a different memory pool, even with the same store.
- **The tool is registered before the backend finishes loading** (L123–140). The
  tool's usage guidelines are part of pi's system prompt. Adding the tool later
  would change the prompt mid-session and throw away the prompt cache.
- In `embedded` mode, an explicit `apiKey`/`baseURL` in the config bypasses pi's
  model registry (provider.js L441–463). That is how mem0's LLM is pointed at
  `bonsai-mem` while pi itself uses `bonsai-agent`.

## Recall: before the agent starts

1. On `input` (index.js L203–220), the user's text has credentials stripped
   (`redactMemoryText`). It is then handed to `Prefetch.queue`, which starts
   `provider.search()` without waiting for it.
2. On `before_agent_start` (L252–265), `Prefetch.consume` waits **at most 3 s**
   (prefetch.js L37–46). If the search is slower, the turn simply goes ahead with
   no memories.
3. Hits are formatted as a block. Each line is wrapped as quoted, untrusted data
   (`formatRecalledMemory`, privacy.js L16–22). Lines that match prompt-injection
   patterns are replaced with a `[BLOCKED …]` marker. The block is capped at 50
   lines and 8 KB:

   ```
   ## Recalled Memories (Mem0)
   - (2026-10-11) [UNTRUSTED MEMORY DATA] "The staging API is served over HTTPS at staging.internal on port 8443"
   ```
4. It goes in as a custom **message**, not as part of the system prompt. The
   system prompt stays byte-identical across turns, so llama-server's prompt
   cache keeps working.

mem0's search (mem0 index.mjs L17875 onward) does more than plain vector
similarity:
- It embeds the query and fetches max(4×topK, 60) candidates by vector.
- It also runs a BM25 keyword search. The SQLite store supports this
  (`keywordSearch`, L981).
- It extracts entities from the query.
- It combines the scores, keeps results above a 0.1 threshold, and returns the
  top `topK` (5 for us).

## Capture: after the first reply

`turn_end` (index.js L221–251) fires after every model turn, but capture only
happens **once per user input**:
- The first assistant message containing text is paired with the user prompt.
- That pair is sent to `provider.add()`.
- `lastUserText` is cleared, so nothing more is captured for that prompt.

Writes are chained on a single promise, `pendingWrite`. `session_shutdown`
(L266–279) awaits it, so a `pi -p` run doesn't exit with a write still pending.

One consequence depends on the model. Bonsai at thinking level `low` usually
calls tools silently and writes text only at the end. So for us, "first reply
with text" is usually the **final summary**. That is a better thing to capture
than "I'll start by reading the file", but only by accident.

## What `add()` does inside mem0

`addToVectorStore` (mem0 index.mjs L17479 onward), with `infer` on:

1. Embed the new messages and fetch the **10 nearest existing memories**.
2. Load the last 10 messages of this session scope from the history DB.
3. **One LLM call.** The system prompt is `ADDITIVE_EXTRACTION_PROMPT` (L5415–5933,
   ~36 KB, about 8k tokens). The user prompt holds the existing memories, the
   recent messages and the new messages. The model must return JSON:
   `{"memory": [{"text": …}]}`.
4. Embed each extracted fact. Drop any whose **md5 hash** matches an existing or
   just-extracted memory. Insert the rest and log `ADD` in history.

There is no UPDATE or DELETE step. Earlier mem0 versions made a second LLM call
to reconcile new facts with old ones; 3.x does not. Two consequences:

- A **paraphrased** fact is stored again. In run r0, the agent saved the staging
  host 4 times in different words. The store ended up with 2 differently worded
  copies of it, and the conventions both as one combined entry and as four
  separate ones.
- A **changed** fact sits next to the old one. Recall then returns both, and the
  model has to guess which is current. Our existing task never tests this. The
  next tasks will.

The ~8k-token prompt comes first and never changes, so llama-server should be able
to reuse it from cache. Our tap log shows that this happened only for writes that
came back to back: 4 of 22 calls reused about 8.1k tokens. Every other call
prefilled the full ~8.5k. We don't yet know why slot 1's cache doesn't survive
between writes. Making writes cheaper is roadmap item M5.

## The agent-callable tool

`mem0_memory` (tools.js) has one `action` parameter: `search | add | get_all |
delete`. Its prompt guidelines tell the model to search before answering anything
that depends on past work, and to "save durable facts proactively". Bonsai
followed that. In every mem0 run it saved the step 1 conventions or the staging
host itself, in addition to what auto-capture stored:

| run | step 1 tool calls | later tool calls |
|---|---|---|
| r0 | 6 × `add` (conventions twice, staging host 4×), 1 × `get_all` | none |
| r1 | 1 × `add` (staging host) | none |
| r2 | 2 × `add` (conventions, staging host) | 1 × `search` in step 3 |

The store after run r1, in full (11 memories):

```
The staging API is served over HTTPS at staging.internal on port 8443
User's project conventions: public function docstrings start with 'Inventory:', tests live in ...
User implemented parse_qty(text) in inventory/units.py that converts quantity strings ...
User created tests/test_units.py with plain-assert pytest tests covering ...
User added a CHANGELOG.md entry under '## Unreleased' reading '- units: add parse_qty ...'
User added format_qty(grams) to inventory/units.py that renders gram counts ...
User added test_kg_formatting, test_gram_formatting, and test_format_qty_invalid ...
User added a CHANGELOG.md entry under '## Unreleased' reading '- units: add format_qty ...'
User's format_qty implementation uses f"{kg:.3f}" rather than Decimal.normalize() ...
User requested a new file inventory/config.py containing a staging_url() function ...
User asked the assistant to clean up a convoluted line in the last test ...
```

Only the first two entries are what the later steps needed. Most of the rest is a
work log, attributed to "User" even though the agent did the work. That costs
nothing at this size. Over a long-lived store it is noise that recall has to rank
past.

## What this means for the experiments

- **Recall** is cheap: one embedding plus SQLite. It is also bounded: a 3 s
  timeout, 8 KB, and it never touches the system prompt.
- **Writes** are the expensive part. Each one is a full LLM call on the shared GPU
  and runs at most once per prompt.
- **Add-only** storage is the main design risk. It is why the
  [series](./) compares mem0 with a layer that can replace facts (Graphiti) and
  one where the agent edits its own memory (memory blocks).
