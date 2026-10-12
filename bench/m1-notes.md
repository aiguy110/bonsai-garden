# M1-ngram — recon notes (2026-10-12)

All 8 recon files are present and **non-empty** under
`bench/results/2026-10-12/m1-ngram/recon/`; `sources.txt` reports **no
"NOT FOUND"** entries. Recon ran on the host worktree; outputs land in the
sandbox via content sync. The round 7/12 re-run re-generates all of them and
adds `spec_lines_full.txt` (full spec/mmproj line listing of
`server-context.cpp`/`server-common.h`, no proximity requirement) and the
`generateAdditiveExtractionPrompt` body to `mem0_extract_src.txt`; §3 quotes
below are cross-checked against that output.

Files: `help.txt` (57 KB), `spec_flags.txt` (8.8 KB),
`spec_mmproj_grep.txt` (2.9 KB), `sources.txt`, `inventory.json` (99 KB),
`mem0_extract_src.txt` (61 KB), `pi_prompt_src.txt` (59 KB),
`event_samples.json` (124 KB).

## 1. `--spec-type` — available values (from `help.txt`)

`--spec-type` selects the speculative-decoding backend. The value list:

```
--spec-type none,draft-simple,draft-eagle3,draft-mtp,draft-dflash,draft-dspark,ngram-simple,ngram-map-k,ngram-map-k4v,ngram-mod,ngram-cache
```

The **default is `none`** (no speculation). The **ngram family** is what M1
targets (self-speculation over n-grams of the current prompt, no separate
draft weights):

- `ngram-simple` — self-speculation over simple n-gram matches.
- `ngram-map-k`, `ngram-map-k4v` — n-gram map variants (k=1 vs k=4v).
- `ngram-mod` — the "mod" n-gram variant (probed in `docs/engine-review.md`; **not** present in the live entry, §1/§3).
- `ngram-cache` — n-gram with caching.

The **draft family** (`draft-simple`, `draft-eagle3`, `draft-mtp`,
`draft-dflash`, `draft-dspark`) requires a separate draft weights
file via `--spec-draft-model`. The current live entry (`serving/llama-swap.bonsai-2-27b.yaml`) carries **no** `--spec-*` flag, so it runs with the default `--spec-type none` (no speculation, §3).

## 2. ngram / draft flags and defaults (from `help.txt`)

### ngram flags (defaults)
| Flag | Default |
|---|---|
| `--spec-ngram-mod-n-min` | 48 |
| `--spec-ngram-mod-n-max` | 64 |
| `--spec-ngram-mod-n-match` | 24 |
| `--spec-ngram-simple-size-n` | 12 |
| `--spec-ngram-simple-size-m` | 48 |
| `--spec-ngram-simple-min-hits` | 1 |
| `--spec-ngram-map-k-size-n` | 12 |
| `--spec-ngram-map-k-size-m` | 48 |
| `--spec-ngram-map-k-min-hits` | 1 |
| `--spec-ngram-map-k4v-size-n` | 12 |
| `--spec-ngram-map-k4v-size-m` | 48 |
| `--spec-ngram-map-k4v-min-hits` | 1 |

### draft flags (draft model only)
| Flag | Default |
|---|---|
| `--spec-draft-n-max` | 3 |
| `--spec-draft-n-min` | 0 |
| `--spec-draft-p-split` | 0.10 |
| `--spec-draft-p-min` | 0.00 |
| `--spec-draft-backend-sampling` | enabled |
| `--spec-draft-device` | auto |
| `--spec-draft-ngl` | auto |
| `--spec-draft-model` | none (required to use a draft) |

### Removed flags (no longer exist)
- `--draft*` (`--draft-n`, `--draft-max`, `--draft-min`, `--draft-n-min`, ...)
  are removed aliases of the `--spec-draft-*` flags above.
- `--spec-ngram-size-n`, `--spec-ngram-size-m`, `--spec-ngram-min-hits`
  (renamed to the per-variant flags, e.g. `--spec-ngram-mod-*`).

**Note:** 48/64/24 are only the documented defaults. The live entry has no
ngram-mod flags at all (no `--spec-*` flag, §1), so they describe what the
replay probe will use on :8089, not what is live. Draft stats
(`timings.draft_n` / `timings.draft_n_accepted`) only appear when
speculation is on (see §3, §7).

## 3. spec + mmproj verdict: **likely yes (not refused/disabled by mmproj)**

Static inspection found no line that gates speculative decoding on the
presence of multimodal (mtmd/mctx) input. The gating logic in
`tools/server/server-context.cpp` (read on the host; cross-checked against
`spec_lines_full.txt` produced by the recon re-run):

- **`server-context.cpp:424-426`** — `can_speculate()` returns `!!spec`:
  the only gate is whether a spec backend object exists.
- **`server-context.cpp:1121-1129`** — the mmproj path disables only
  `ctx_shift` and `cache_reuse`; it does not touch spec.
- **`server-context.cpp:~1168`** — the only spec-related log line in this
  region is the checkpoint-mode notice "speculative decoding not supported
  by this context" — a checkpoint-mode guard, **not** an mmproj guard.
- **`server-context.cpp:1182-1188`** — spec init depends only on
  `ctx_tgt_seq_rm_type != NO` (no multimodal condition).
- **`server-context.cpp:1212`** — every slot gets `slot.spec = spec.get()`
  regardless of mctx.

**Verdict: likely yes** — nothing in the source refuses or disables
speculation when `--mmproj` is loaded. The replay probe
(`bench/checkpoint_replay.py`) confirms on :8089 by checking the tap records
for **`draft_n > 0`** and **`draft_n_accepted > 0`** (draft fields appear
only when speculation is on; `predicted_n` is just the generated-token
count — §2, §7). If they are zero, check the server log for the
checkpoint-mode line above before concluding spec is disabled.

## 4. Message-reconstruction mapping (from `event_samples.json`)

The event schema is the canonical source for rebuilding the transcript.
12 distinct event types observed (`n_distinct_types: 12`):
`session, agent_start, turn_start, message_start, message_end,
message_update, tool_execution_start, tool_execution_update,
tool_execution_end, turn_end, agent_end, agent_settled`.

Key mappings for reconstruction:

- **System prompt** → the `message` in a `message_start` / `agent_end`
  entry where `role == "system"` carries a `sections` map
  (`{preamble, tools, rules, docs, ...}`). The message `content` is empty;
  the sections *are* the payload. Each non-`preamble` section is wrapped in
  a `<name>...</name>` tag (`preamble` is raw). This matches
  `buildSystemPromptSections(input)` in `dist/core/system-prompt.js`:
  - `preamble` = the "You are an expert coding assistant operating inside pi…"
    string (or a custom prompt).
  - `tools` = a `<tools>` list of visible tools with snippets, plus the
    "In addition to the tools above…" tail.
  - `rules` = a `<rules>` block (built from `buildRules(...)`).
  - `docs` = a `<docs>` block of pi doc paths (always present in default
    mode).
  - optional: `addendum`, `project_context`, `skills`, `cwd`.
  `buildSystemPromptState` returns `{content: "", sections}` and
  `getSystemMessageText` (from `@earendil-works/pi-ai`) renders the sections
  into the final system-prompt text sent to the model.
- **Transcript** → the `messages` array in `agent_end`
  (`{role, content, sections?}` per message). `agent_end.messages` reconstructs
  the whole conversation.
- **Assistant output** → `message_start`/`message_update` for
  `role == "assistant"`; `turn_end.message` carries the final assistant
  `content` (a list of `{type:"thinking", thinking, thinkingSignature}` and
  `{type:"toolCall", id, name, arguments}` blocks) plus per-message
  `usage`, `api` (`openai-completions`), `provider` (`garden`), `model`
  (`bonsai-agent`), `stopReason`, `responseId`, `responseModel`
  (the GGUF path), `rawStopReason`.
- **Tool calls** → `tool_execution_start` `{toolCallId, toolName, args}`;
  `tool_execution_update` / `tool_execution_end` carry progress/completion;
  `turn_end.toolResults` carries the per-call result
  (`{role:"toolResult", toolCallId, toolName, content, isError, timestamp}`),
  which is replayed as a tool-result message.
- **Usage/tokens** → `message_update.usage`
  (`{input, output, cacheRead, cacheWrite, totalTokens, cost}`), also
  present per message in `turn_end.message.usage`
  (`{input, output, cacheRead, cacheWrite, reasoning, totalTokens, cost}`).

Note: mem0 runs add a second role — the **`mem`** LLM (`model: bonsai-mem`,
the memory backend on the same weights) — see the `role` field in tap records
(§7).

- The full built-in tool schemas as seen on the wire are dumped in
  `pi_prompt_src.txt` (`message_start.message.toolsAdded`, from the chosen
  step in `event_samples.json`) — that is the exact tool list the agent
  prompt is built from.

## 5. mem0 user-prompt assembly (from `mem0_extract_src.txt`)

The `mem0_memory` tool invokes mem0's `add()` /
`addToVectorStore(messages, metadata, filters, infer)`. For each turn, the
agent passes recent messages and mem0:

1. **Serializes the new messages**:
   `parsedMessages = messages.map((m) => \`${m.role}: ${m.content}\`).join("\n")`.
2. **Fetches up to 10 prior messages**:
   `lastKMessages = db.getLastMessages(sessionScope, 10)` (bounded by
   `mem0.maxRetrievalHistory`).
3. **Searches the vector store for ~10 near-matches** (`existingMemories`)
   keyed on the embedding of `parsedMessages`.
4. **Builds the system prompt** = `ADDITIVE_EXTRACTION_PROMPT`
   (+ `AGENT_CONTEXT_SUFFIX` only when agent-scoped).
5. **Builds the user prompt**:
   ```js
   const userPrompt = generateAdditiveExtractionPrompt({
     existingMemories,
     newMessages: parsedMessages,
     lastKMessages: lastMessages,
     customInstructions: this.customInstructions
   });
   ```
6. **Calls the LLM in `json_object` mode**:
   `generateResponse([{role:"system",content:systemPrompt},
   {role:"user",content:userPrompt}], {type:"json_object"})`.
7. **Post-processes**: parses the response against `AdditiveExtractionSchema`,
   extracts each memory, dedupes via md5 hash of the memory text
   (skips hashes already in the vector store or seen this turn), then
   `embedBatch` (with per-text fallback) → `vectorStore.insert`, writes
   `memory_history` (action `ADD`) rows, and extracts/inserts entities into
   `mem0-vectors_entities.db`.

The full, untruncated `ADDITIVE_EXTRACTION_PROMPT` constant is reproduced in
`mem0_extract_src.txt`.

*Gap:* the exact user-prompt template text — the body of
`generateAdditiveExtractionPrompt` — was not captured by this window. The
recon script now extracts it by name, falling back to any other file under
`m0dist/dist/` (re-run, round 7/12). The re-run output
(`mem0_extract_src.txt`) is the authoritative template text for replay
fidelity.

## 6. mem0 DB row counts per run (from `inventory.json`)

Baseline runs have **no** mem0 DBs (`mem0_dbs: {}`). Mem0 runs each own
three SQLite files:

| run | `mem0-history.db` | `mem0-vectors.db` | `mem0-vectors_entities.db` |
|---|---|---|---|
| inventory-mem0-r0 | memory_history=9, messages=10 | vectors=9 | vectors=59 |
| inventory-mem0-r1 | memory_history=11, messages=7 | vectors=11 | vectors=97 |
| inventory-mem0-r2 | memory_history=3, messages=8 | vectors=3 | vectors=38 |

(`memory_migrations` / `sqlite_sequence` are ~1 row each in the vectors DBs and
are omitted; index row counts are `-1` and omitted.)

## 7. Tap / inventory summary (from `inventory.json`)

- `tap_record_total = 286`; 6 runs × 3 steps (0/1/2); `n_distinct_types = 12`.
- Per-role totals are in `tap_role_totals`; per-role detail in `tap_records`.
  Baseline runs have only an `agent` role. Mem0 runs add a **`mem`** role
  (the memory LLM, `model: bonsai-mem`).
- Each tap record: `{role, path: /v1/chat/completions, model
  (bonsai-agent | bonsai-mem), status (200), n_messages, prompt_n, cache_n,
  predicted_n}`. `predicted_n` is the **generated-token count** for that
  request (normal completion length — *not* a draft count). Draft stats are
  `timings.draft_n` / `timings.draft_n_accepted`; both are **absent** from
  these recordings (the live entry has no `--spec-*` flags, §1).
- Example (mem0-r0):
  - step0 — agent: (11 reqs, prompt_n=36127, cache_n=30196, predicted_n=6654);
    mem: (7 reqs, prompt_n=36181, cache_n=24464, predicted_n=419)
  - step1 — agent: (11, 3021, 90003, 8627); mem: (1, 8874, 0, 289)
  - step2 — agent: (14, 2645, 75700, 3691); mem: (1, 9183, 0, 2048)
- Both `agent` and `mem` roles show non-zero `predicted_n` (generated tokens
  only — no speculation, §1); `cache_n` grows across turns (prefix-cache
  hits), consistent with the running context being reused.
