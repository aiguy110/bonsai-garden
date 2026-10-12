# M1-ngram — recon notes (2026-10-12)

All 10 recon files are present and **non-empty** under
`bench/results/2026-10-12/m1-ngram/recon/`; `sources.txt` reports **no
"NOT FOUND"** entries. Recon ran on the host worktree; outputs land in the
sandbox via content sync. The recon re-run re-generates all of them and adds
`spec_lines_full.txt` (full spec/mmproj line listing of
`server-context.cpp`/`server-common.h`, no proximity requirement) and the
`generateAdditiveExtractionPrompt` body to `mem0_extract_src.txt`; §3 quotes
are cross-checked against that output, and the lines it can't reach (gating
`if(...)`, surrounding blocks) are cross-checked against the host window
`spec_ctx.txt` (see §3).

Files: `help.txt` (57 KB), `spec_flags.txt` (8.6 KB),
`spec_mmproj_grep.txt` (2.9 KB), `sources.txt` (3.3 KB),
`inventory.json` (99 KB), `mem0_extract_src.txt` (62 KB),
`pi_prompt_src.txt` (64 KB), `event_samples.json` (122 KB),
`spec_lines_full.txt` (17 KB), `spec_ctx.txt` (10.9 KB, host window of
`server-context.cpp`).

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

## 3. spec + mmproj verdict: **yes (static) — confirm with draft_n>0 on :8089**

Static inspection found no line that gates speculative decoding on the
presence of multimodal (mtmd/mctx) input. The gating logic in
`tools/server/server-context.cpp` is cross-checked against the recon's
`spec_lines_full.txt` (every line matching `speculative|spec`, numbered) and,
for lines that keyword-grep misses, against the host window `spec_ctx.txt`:
verified quotes below are literal.

- **`server-context.cpp:424-426`** — `can_speculate()` returns `!!spec`: the
  only gate is whether a spec backend object exists.
  ```
  424: bool can_speculate() const {
  425: return !!spec;
  426: }
  ```
- **`server-context.cpp:1123, 1128`** — the mmproj/multimodal block disables
  only `ctx_shift` and `cache_reuse`; it does **not** touch spec.
  ```
  1123: SRV_WRN("%s\n", "ctx_shift is not supported by multimodal, it will be disabled");
  1128: SRV_WRN("%s\n", "cache_reuse is not supported by multimodal, it will be disabled");
  ```
- **`server-context.cpp:~1168`** — the only spec-related log line in this
  region is the checkpoint-mode notice — a checkpoint-mode guard, **not** an
  mmproj guard.
  ```
  1168: SRV_WRN("%s", "speculative decoding not supported by this context\n");
  ```
- **`server-context.cpp:1184-1191`** — spec init is gated on the context
  sequence-removal type only, with **no** mctx/mmproj term. From the host
  window `spec_ctx.txt` (literal):
  ```
  1184:         // try speculative decoding
  1185:         if (ctx_tgt_seq_rm_type != COMMON_CONTEXT_SEQ_RM_TYPE_NO) {
  1186:             try {
  1187:                 spec.reset(common_speculative_init(params_base.speculative, params_base.n_parallel));
  1188:             } catch (const std::exception & e) {
  1189:                 SRV_ERR("failed to initialize speculative decoding context: %s\n", e.what());
  1190:             }
  1191:         }
  ```
  `ctx_tgt_seq_rm_type` is set at 1166 from
  `common_context_can_seq_rm(ctx_tgt)` — also no multimodal condition.
- **`server-context.cpp:1212`** — every slot gets `slot.spec = spec.get()`
  regardless of mctx.
  ```
  1212: slot.spec    = spec.get();
  ```

**Verdict: yes (static)** — nothing in the source refuses or disables
speculation when `--mmproj` is loaded. The complete set of spec gates is:
(a) `can_speculate() == !!spec` (424-426); (b) the init gate at 1185 on
`ctx_tgt_seq_rm_type != COMMON_CONTEXT_SEQ_RM_TYPE_NO` (no mctx/mmproj term);
and (c) the slot assignment `slot.spec = spec.get()` (1212). The mmproj block
disables only `ctx_shift` (1123) and `cache_reuse` (1128), never spec. This
static verdict is confirmed **empirically** on the live server only when the
replay probe reports **`draft_n > 0`** and **`draft_n_accepted > 0`** in the
tap records on :8089 (draft fields appear only when speculation is on;
`predicted_n` is just the generated-token count — §2, §7). If those are zero,
check the server log for the checkpoint-mode line (1168) before concluding spec
is disabled.

## 4. Message-reconstruction mapping (from `event_samples.json`)

The event schema is the canonical source for rebuilding the transcript.
Chosen step is `inventory-mem0-r2/step1` (8942 events, `n_distinct_types:
12`): `session, agent_start, turn_start, message_start, message_end,
message_update, tool_execution_start, tool_execution_update, tool_execution_end,
turn_end, agent_end, agent_settled`.

Confirmed from `event_samples.json` (this round):
- **The system prompt comes from a `role == "system"` message.** Both the
  `message_start.message` and `agent_end.messages[0]` entries have
  `role == "system"` and carry a `sections` map
  (`{preamble, tools, rules, docs, cwd}`). The `content` field is empty; the
  `sections` map *is* the payload. Sampled values:
    - `preamble` = `"You are an expert coding assistant operating insid..."`
    - `tools` = `"<tools>\n- read: Read file contents\n- bash: Execute..."`
    - `rules` = `"<rules>\n- Use bash for file operations like ls, rg..."`
    - `docs` = `"<docs>\nP i documentation (read only when the user a..."`
    - `cwd` = `"<cwd>\n/home/dev/inventory\n</cwd>"`
  Each non-`preamble` section is wrapped in a `<name>...</name>` tag
  (`preamble` is raw). This matches `buildSystemPromptSections(input)` in
  `dist/core/system-prompt.js`; `buildSystemPromptState` returns
  `{content: "", sections}` and `getSystemMessageText` (from
  `@earendil-works/pi-ai`) renders the sections into the final system-prompt
  text sent to the model.
- **`message_start.message.toolsAdded` exists.** It is a list of 5 tool
  schemas for the mem0 run: `read`, `bash`, `edit`, `write`, `mem0_memory`.
  Each tool has keys `name`, `description`, `parameters`
  (`{type, required, properties}`), and `constrainedSampling`
  (`{"type": "json_schema", "strict": "prefer"}`). These built-in pi tool
  schemas are dumped in full in `pi_prompt_src.txt` (from the chosen step in
  `event_samples.json`) — that is the exact tool list the agent prompt is
  built from.

Key mappings for reconstruction:
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

The full, untruncated `ADDITIVE_EXTRACTION_PROMPT` constant **and** the
`generateAdditiveExtractionPrompt` body are reproduced in
`mem0_extract_src.txt`. The exact user-prompt template is now captured
(`mem0_extract_src.txt` lines 1137-1165), so the old "Gap" is closed.

**System prompt (`ADDITIVE_EXTRACTION_PROMPT`) — section headers in order**
(`mem0_extract_src.txt`): `# ROLE` → `# INPUTS`
(`## New Messages`, `## Summary`, `## Recently Extracted Memories`,
`## Existing Memories`, `## Last k Messages`, `## Observation Date`,
`## Current Date`, `## Optional Inputs`, `## What to Extract`, …) →
`## Memory Quality Standards` → `## Integrity Rules` → `## Memory Linking`
→ examples (Example 1..12) → `## Structure` → `## Fields` → `## Rules`. The
`## Existing Memories` section documents the dedupe input format
`["{\"id\": \"uuid-string\", \"text\": \"...\"}", ...]`.

**User prompt (`generateAdditiveExtractionPrompt`) — sections in order**,
pushed into an array and `sections.join("\\n\\n")`'d:

1. `## Summary` (empty body)
2. `## Last k Messages` + `formatConversationHistory(options.lastKMessages)`
3. `## Recently Extracted Memories` + `[]` (hard-coded empty array)
4. `## Existing Memories` + `serializeMemories(options.existingMemories)`
5. `## New Messages` + `options.newMessages` (or `"[]"` if null/undefined)
6. `## Observation Date` + `options.observationDate` (defaults to
   `options.currentDate`, which defaults to today's date
   `(new Date()).toISOString().split("T")[0]`)
7. `## Current Date` + `options.currentDate` (same default)
8. `## Custom Instructions` + `options.customInstructions` — **only** when
   `options.customInstructions` is truthy
9. `# Output:` (no body — the output schema lives in the system prompt's
   `## Structure` / `## Fields` / `## Rules` sections)

**How the four inputs are filled (from the call site, `mem0_extract_src.txt`):**
- `lastKMessages` = `db.getLastMessages(sessionScope, 10)` (bounded by
  `mem0.maxRetrievalHistory`) → rendered by `formatConversationHistory()` into
  `## Last k Messages`.
- `newMessages` = `parsedMessages = messages.map((m) => \`${m.role}: ${m.content}\`).join("\n")` → `## New Messages`.
- `existingMemories` = top-10 vector-store hits, each mapped to
  `{ id: String(idx), text: mem.payload.data }` → `## Existing Memories` via
  `serializeMemories(...)`.
- `customInstructions = this.customInstructions` → `## Custom Instructions`
  (included only when truthy).

**Honest note:** `formatConversationHistory()` and `serializeMemories()` are
only *called* in the captured source — their function **bodies are not** in
`mem0_extract_src.txt`, so their exact formatting is not quoted here. The
system prompt's `## Existing Memories` section documents the expected
serialization:
```
[{"id": "uuid-string", "text": "..."}, ...]
```
which `serializeMemories` is responsible for producing.

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

## 8. Replay-set size check (round 11, from replay_manifest.json and autopilot/replay-set-r10.log)

Estimator: chars/4 over the rebuilt body, against recorded prompt_n+cache_n.

- Agent: 30 requests, 6 steps, median est/recorded **0.833** (inside 0.75–1.33). Mem: 12 requests, 5 steps, median **1.027**.
- Agent bodies keep assistant thinking as `reasoning_content` (pi's thinkingSignature). Without it the median is 0.457. Evidence that recorded prompts include earlier reasoning in full: in baseline-r0 step 0, agent turns 2-4 generated 8565+576+1024=10165 tokens (inventory.json), and the recorded prompt grows 2761->13032 (+10271) from turn 2 to turn 5, i.e. growth ≈ generated tokens. The probe server needs `--jinja`.
- The "reasoning after last user only" ratio equals the "all reasoning" ratio. Every step is a fresh session with one user message, so this says nothing about the chat template.
- Not confirmed from source: the pi-ai `openai-completions.js` search found no file (empty list), so that pi sends `reasoning_content` back is inferred from the token counts only.
- Outliers below 0.75: baseline-r0/0/5 (0.740), /0/8 (0.743), /0/10 (0.742), 1% under the bound, all late turns of baseline-r0 step 0, which is dominated by one long reasoning output. Cause: over turns 2-5 the rebuilt body grows 8502->38559 chars (+30057), of which tool output is only +219 (baseline-r0/0/5 chars_by_role: tool=2154, reasoning=25717), while the recorded prompt grows +10271 tokens. So the model's own reasoning/assistant text tokenizes at ~2.96 chars/token and chars/4 under-counts it. Estimator not changed.
- Mem requests are all 1.02–1.04: the prompt is mostly the fixed ADDITIVE prompt, so they pass easily. They do not test the tokenizer on conversation content.
- Replays still lack sampling params and per-request max_tokens (not recorded); the probe must set them.
