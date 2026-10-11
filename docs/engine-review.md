# Inference engine review and proposal (2026-10-10)

Scope: the bifrost stack `turnstile (:8080) -> llama-swap (:11435) -> llama-server`
on one RTX 3080 (10 GB), focused on `bonsai-2-27b` (Ternary-Bonsai-2-27B PQ2_0,
PrismML fork `~/Projects/llama.cpp-bonsai2` @ 9a9394a).

Raw numbers: `../bench/results/2026-10-10/`. Reproduce with `../bench/engine_probe.sh`
and `../bench/server_probe.sh`, run under a turnstile lease.

## 1. Measured throughput

Single stream, `llama-bench -fa 1`, pp512 / tg128:

| KV type | prefill @0 | decode @0 | prefill @32k depth | decode @32k depth |
|---|---|---|---|---|
| q4_0 | 1171 tok/s | 64.0 tok/s | 871 tok/s | 45.3 tok/s |
| q8_0 | 1169 tok/s | 63.9 tok/s | 863 tok/s | 47.8 tok/s |

- At realistic agent depth, decode is **~45 tok/s, not 65**. Use that number when
  planning.
- q8_0 KV is slightly faster at depth, since there is less dequantization work in
  the attention kernels. It costs about 2x the KV bytes on 16 of the 64 layers.

Concurrent sequences sharing **one copy of the weights** (`llama-batched-bench`,
q4_0 KV, pp512/tg128):

| parallel seqs | 1 | 2 | 3 | 4 | 6 | 8 |
|---|---|---|---|---|---|---|
| aggregate decode tok/s | 63 | 95 | 114 | 116 | 137 | 152 |

The live server at the production setting (`-c 98304`, q4_0 + mean-center,
`--kv-unified`, 256-token greedy decode):

| slots | VRAM used | per-stream decode (all slots busy) | aggregate |
|---|---|---|---|
| 1 | 9349 MiB | 61.5 | 61.5 |
| 2 | 9503 MiB | 44.6 | 89 |
| 3 | 9653 MiB | 35.0 | 105 |
| 2 @ 131072 ctx | OOM (718 MiB compute buffer did not fit) | — | — |

Decode is memory-bandwidth-bound, so a second concurrent stream costs about
**+150 MiB of VRAM** and runs at roughly 70% of single-stream speed. Total
throughput rises by about 45%.

## 2. Shared weights across "instances"

| approach | one weights copy? | per-instance ctx | per-instance KV type | verdict |
|---|---|---|---|---|
| Separate llama-server processes | No. Each process allocates its own 6.7 GiB on the GPU, and mmap only shares host RAM | yes | yes | **Infeasible** on 10 GB |
| One llama-server, `-np N --kv-unified` | **Yes** | effectively yes: the pool is shared and each slot uses only what its prompt needs, so a short memory-LLM prompt costs only its own tokens | **No**, one type for the whole context | **Recommended, works today** |
| One process, one `llama_model` with 2 `llama_context`s | Yes, the llama.cpp API supports it | yes, fixed per context | **Yes** | Feasible but needs a custom server or fork patch. Each extra context costs its own compute buffer (~200–700 MiB depending on ubatch). Defer |
| llama-server router mode (`--models-dir`, `--models-max`) | No (one process per model) | — | — | Not useful here |

**Conclusion:** the goal of a "second small-context Bonsai for memory work" is
already met by a single 2-slot server. The memory slot's cost is its recurrent
state (~150 MiB) plus the tokens it actually holds (~18 KiB/token at q4_0, so a
4k-token mem0 prompt is about 72 MiB). Varying KV quantization per instance is the
only part that needs engineering. Do that only if the memory-quality evals show
sensitivity to KV quantization. At short memory contexts, q8 KV for that context
would be cheap.

## 3. Other tok/s levers

1. **Hybrid prompt-cache reuse.** The 48 recurrent layers can't be truncated, so
   any divergence from the cached prefix rolls back to the nearest *context
   checkpoint*. The default `--checkpoint-min-step 8192` means one agent turn can
   re-prefill up to ~8k tokens (~8–9 s at depth). Divergence is common, for example
   when the chat template strips earlier `<think>` blocks. Proposal: test
   `-cms 1024..2048`. Checkpoints live in host RAM (`--cache-ram`, 8 GiB default).
   *Probably the single biggest agent-latency win; measure per-turn
   `prompt_n` on real pi traces.*
2. **N-gram self-speculation (`--spec-type ngram-mod`).** Needs no draft model and
   no extra VRAM (+4 MiB measured). On a fresh prompt it drafted nothing and ran at
   baseline speed (61.0 vs 61.5). On repeated text it hit 100% acceptance and
   reached 162 tok/s. Agents re-emit file contents and edits a lot. Validate on
   agent traces, including with `-np 2`.
3. **No MTP or EAGLE/DFlash draft for Bonsai 2.** The GGUF has no `nextn`
   tensors, and no published draft for its Qwen3.8-27B base was found. The fork can
   run `draft-dflash` if one appears.
4. **Context headroom.** At `-ub 512` the compute buffer is ~718 MiB. `-ub 256`
   should free ~350 MiB, either for more context or for a third slot, at some cost
   to prefill speed. Low priority.
5. **Housekeeping.** The v1 `bonsai-27b` entry runs `--batch-size 32`, which cripples
   its prefill. Retire it in favor of bonsai-2. Also, pi's `models.json` has
   **no `bonsai-2-27b` entry** yet.

## 4. Turnstile constraints (these block the concurrency win)

- **Turnstile admits one LLM request at a time.** Agent and memory calls never
  batch, so the measured +45% aggregate is unreachable through `:8080` today.
- **Eviction is by model name.** Two llama-swap entries (or aliases) for the same
  weights would be separate processes, or separate names to turnstile, and an
  equal-or-higher-tier waiter for the "other" name unloads the first. The two
  roles would thrash.

Proposed turnstile changes:

**4a. Co-admission.** Let a waiter join the current holder(s) when all of these
hold:
1. the waiter is an LLM request for the warm model;
2. no strictly higher-priority waiter is pending;
3. the number of in-flight requests is below that model's configured `slots`;
4. the token budget (4b) still fits.

Leases still require an empty GPU.

**4b. Context budget.** The server's pool (`-c`) is fixed, so VRAM can't grow, but
slots share it: a slot may use all of it, and two busy slots can exhaust it
mid-request. Turnstile accounts for it:
- estimate each request as `prompt_tokens + max_tokens` (prompt tokens from a
  tokenizer call or a chars/token estimate);
- admit a joiner only if the sum over in-flight requests plus the joiner is within
  `ctx_pool`, otherwise queue it;
- idle slots don't count, since llama-server moves idle caches to host RAM.

**4c. Virtual models.** Several names that map to one real model, each with its
own limits:

```yaml
models:
  bonsai-2-27b: { slots: 2, ctx_pool: 98304 }
virtual:
  bonsai-agent: { backend: bonsai-2-27b, max_ctx: 81920 }
  bonsai-mem:
    backend: bonsai-2-27b
    max_ctx: 12288
    inject: { chat_template_kwargs: { enable_thinking: false } }
```

Turnstile rewrites `model` to the real name before forwarding, evicts and counts by
the real name, rejects requests over `max_ctx`, and merges `inject` into the body.
This replaces the tagging shim in `architecture.md`. Pi's context window setting
should match `bonsai-agent`'s `max_ctx` so it compacts first. Per-name KV type is
still not possible (see §2).

All of this is a self-contained change in `internal/queue` and `internal/proxy`.

## 5. Proposal

**Phase A (config only, no code):**
- Change `bonsai-2-27b` to `--parallel 2 --kv-unified --checkpoint-min-step 2048`
  (draft in `../serving/llama-swap.bonsai-2-27b.proposed.yaml`). Expected VRAM is
  ~9.5 GB, leaving ~770 MiB of headroom. That's under the informal >=1 GB bar, so
  optionally pair it with `-ub 256`.
- Add `bonsai-2-27b` to pi's `models.json`.
- Re-measure on pi traces: per-turn prefill tokens and decode tok/s at depth.

**Phase A results (2026-10-11, applied).** Raw data in
`../bench/results/2026-10-11/`.
- Baseline unchanged from 10-10: 1 slot 61.5 tok/s / 9349 MiB, 2 slots 44.8 tok/s
  each / 9503 MiB.
- Live `bonsai-2-27b` now runs `--parallel 2 --kv-unified`
  (`../serving/llama-swap.bonsai-2-27b.yaml`). Through turnstile with the pi key it is
  tagged `name=pi priority=40`; VRAM 9503 MiB; two simultaneous requests sent
  directly to llama-swap each decode at 44.6 tok/s.
- **`--checkpoint-min-step 2048` is not needed and was not shipped.**
  `../bench/checkpoint_replay.py` replays a 14-turn tool-calling conversation
  (reasoning dropped from history, as an OpenAI client does) to ~17k tokens; at
  `-cms 8192` and `-cms 2048` the per-turn `prompt_n` is identical and equals only
  the new tokens (`cache_n` = the whole previous prompt). The fork checkpoints at
  the last user message and 4 tokens before the end of every prompt, so
  append-only agent traffic never rolls back. A real pi session via
  `../evals/tap.py` shows the same (`pi_smoke_tap.jsonl`: `cache_n` = previous
  prompt + previous generation every turn). §3.1's latency worry does not apply
  to pi as it is today; it may matter after compaction or history edits.
- `id_slot` **is honored** through llama-swap's `/v1/chat/completions` (checked via
  `/upstream/bonsai-2-27b/slots` `id_task`). `chat_template_kwargs:
  {enable_thinking: false}` works on this fork (no `reasoning_content`).
- pi has a `bonsai-2-27b` entry (`../agent/models.bonsai-2-27b.json`). pi needs
  stdin closed (`</dev/null`) in scripted `-p` runs with a fresh
  `PI_CODING_AGENT_DIR`, or it hangs.

**Phase B (turnstile):** co-admission, context budget and virtual models (§4a–c).

**Phase B results (2026-10-11, deployed).** Turnstile `main` 25474ca
(`~/Projects/gpu-turnstile`, branch `virtual-models`). Live config:
`bonsai-2-27b {slots: 2, ctxPool: 98304}`; `bonsai-agent` (maxCtx 81920, `id_slot: 0`);
`bonsai-mem` (maxCtx 12288, defaultMaxTokens 1024, `id_slot: 1`, thinking off); new
key `bonsai-garden-mem` (prio 40, `BONSAI_GARDEN_MEM_KEY` in turnstile's `.keys.env`).
`../bench/phase_b_validate.py` against the live stack, all pass
(`../bench/results/2026-10-11/phase_b_validate.txt`):
- agent + mem through `:8080` are co-admitted (`joined`, mem waited 0 ms) and decode
  at 43.9 / 44.9 tok/s, i.e. the +45% aggregate is now reachable through turnstile;
- `id_slot` pinning works through turnstile → llama-swap (slot 0 agent, slot 1 mem);
  `bonsai-mem` returns no reasoning, `bonsai-agent` still reasons;
- over-`maxCtx` → 400 `context_length_exceeded` without queueing; two ~50k-token
  requests serialize on the budget (`deferring: context budget`);
- a lease arriving mid-stream waits for both LLM holders.
Deviations from the runbook: none in behaviour. Additions: a `deferring: slots
full` log for multi-slot models; `HoldRecord.Alias`; a joiner never lowers
`warm_tier`. Separately fixed a turnstile activity test that had a fixed date
and aged out of retention, and gitignored `config.yaml.bak*` (it holds keys).
pi: `bonsai-agent` is the default model. pi's `llama-swap-discover.ts` extension
replaced the provider's model list with llama-swap's `/v1/models`, which hid
virtual names; it now appends models.json entries discovery doesn't return.

**Phase C (experiments):** `ngram-mod` on agent traces; q8_0 KV for the agent at
lower ctx; a two-context single-process server for per-role KV types, only if
memory evals call for it.
