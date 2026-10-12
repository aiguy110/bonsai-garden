# M1-ngram — recon notes (2026-10-12)

Round 12/12 (of 12). All 8 recon files are present and **non-empty** under
`bench/results/2026-10-12/m1-ngram/recon/`; `sources.txt` reports **no
"NOT FOUND"** entries. Recon ran on the host worktree; outputs land in the
sandbox via content sync.

Files: `help.txt` (57 KB), `spec_flags.txt`, `spec_mmproj_grep.txt` (136 KB),
`sources.txt`, `inventory.json` (99 KB), `mem0_extract_src.txt`,
`pi_prompt_src.txt`, `event_samples.json` (124 KB).

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
- `ngram-mod` — the "mod" n-gram variant (this is the live-stack setting).
- `ngram-cache` — n-gram with caching.

The **draft family** (`draft-simple`, `draft-eagle3`, `draft-mtp`,
`draft-dflash`, `draft-dspark`) requires a separate draft weights
file via `--spec-draft-model`. The current live stack uses
**`--spec-type ngram-mod`**, i.e. the ngram-mod baseline.

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
- `--draft`, `--draft-n`, `--draft-max`, `--draft-min`, `--draft-n-min`
  (renamed to the `--spec-draft-*` family).
- `--spec-ngram-size-n`, `--spec-ngram-size-m`, `--spec-ngram-min-hits`
  (renamed to the per-variant flags, e.g. `--spec-ngram-mod-*`).

**Note:** the live stack's ngram-mod settings
(`--spec-ngram-mod-n-min 48 / n-max 64 / n-match 24`) match the documented
defaults exactly, so the current config is the "default ngram-mod" baseline.
The replay probe will confirm `predicted_n` / `draft_n` on the actual
session (see §3).

## 3. spec + mmproj verdict: **UNCLEAR**

Static inspection of the `llama.cpp` source (grep for `mtmd|mctx|multimodal`
within ±5 lines of spec-related lines — see `spec_mmproj_grep.txt`) found
**no line that gates or disables speculative decoding on the presence of
multimodal (mtmd/mctx) input.** The spec-related lines that *were* found,
quoted:

- `server-common.h:215` — `// for compatibility with speculative decoding`
  (a comment only; not conditional on multimodal).
- `server-context.cpp:206-210` — `// speculative decoding, common_speculative
  * spec;` (a comment only).
- `server-context.cpp:1212` — `slot.spec = spec.get();`
  (assigns the spec handle to the slot; no multimodal condition in the window).
- `server-context.cpp:707-710` — `if (!common_speculative_process(spec, batch))`
  (the spec-processing hook; no multimodal gate in the window).

The presence of `#include "speculative.h"` and the `slot.spec` assignment
confirms the server *carries* the spec machinery, but none of these lines
resolves whether it is actually **active** when `mtmd`/`mctx` is loaded.

**Verdict: UNCLEAR.** Resolve empirically in the replay probe
(`bench/checkpoint_replay.py`): run a mmproj session with
`--spec-type ngram-mod` and check the tap records for
`predicted_n`/`draft_n` (and the server log for `speculative decoding`
activity). If `predicted_n > 0` appears on a mmproj turn, spec is active;
if `draft_n == 0` / no spec activity on a mmproj turn, spec is disabled by
multimodal.

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
`generateAdditiveExtractionPrompt` — lives in a separate dist file and was
not captured by this recon window. Its call site and all four inputs are
captured; extract the template text in the probe round if the exact wording
is needed for replay fidelity.

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
  predicted_n}`. `predicted_n` is the speculative-draft token count for that
  request.
- Example (mem0-r0):
  - step0 — agent: (11 reqs, prompt_n=36127, cache_n=30196, predicted_n=6654);
    mem: (7 reqs, prompt_n=36181, cache_n=24464, predicted_n=419)
  - step1 — agent: (11, 3021, 90003, 8627); mem: (1, 8874, 0, 289)
  - step2 — agent: (14, 2645, 75700, 3691); mem: (1, 9183, 0, 2048)
- Both `agent` and `mem` roles show non-zero `predicted_n` where the live
  ngram-mod config is in effect; `cache_n` grows across turns (prefix-cache
  hit), consistent with the running context being reused.
