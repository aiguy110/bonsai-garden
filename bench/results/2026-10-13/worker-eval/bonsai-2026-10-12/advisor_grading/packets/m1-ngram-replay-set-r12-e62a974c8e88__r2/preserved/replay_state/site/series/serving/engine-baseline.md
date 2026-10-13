---
layer: experiment
series: serving
title: Engine baseline and shared-weights options
status: done
date: 2026-10-10
updated: 2026-10-11
tldr: Measured decode at depth (~45 tok/s at 32k) and found that a second server slot, not a second model, is the way to give memory its own LLM.
summary: |
  **Question:** how fast is Bonsai-2-27B on an RTX 3080? And how can a memory
  layer get its "own" LLM without loading the weights twice?

  **Results:**
  - Single stream: prefill ~1170 tok/s and decode **64 tok/s** on an empty
    context. At 32k tokens of context, that falls to **~45 tok/s**. Use the
    second number when planning for agents.
  - q8_0 and q4_0 KV cache run at the same speed. q4_0 halves KV memory.
  - Batching several sequences on **one copy of the weights** scales well: 2
    sequences give 95 tok/s aggregate, 8 give 152.
  - Separate server processes would each load 6.7 GB onto the GPU, so that option
    is out. **One server with two slots** shares the weights, and each slot only
    uses the context its prompt needs.

  **Conclusion:** the memory LLM should be slot 1 of the agent's server. The GPU
  scheduler then becomes the bottleneck, because it admitted one request at a
  time. That set up the next two experiments.
---

## Method

`llama-bench` and `llama-batched-bench` from the PrismML llama.cpp fork, plus a
probe that starts a private llama-server at the production settings and measures
VRAM and per-stream decode with all slots busy. Probes ran under a turnstile lease
so they never disturbed the live server.
Raw data: [`bench/results/2026-10-10/`](https://github.com/aiguy110/bonsai-garden/tree/main/bench/results/2026-10-10).

## Single stream (pp512 / tg128)

| KV type | prefill @0 | decode @0 | prefill @32k | decode @32k |
|---|---|---|---|---|
| q4_0 | 1171 | 64.0 | 871 | 45.3 |
| q8_0 | 1169 | 63.9 | 863 | 47.8 |

## Concurrent sequences on one copy of the weights

| parallel seqs | 1 | 2 | 3 | 4 | 6 | 8 |
|---|---|---|---|---|---|---|
| aggregate decode tok/s | 63 | 95 | 114 | 116 | 137 | 152 |

## Production server (`-c 98304`, q4_0 KV)

| slots | VRAM | per-stream decode | aggregate |
|---|---|---|---|
| 1 | 9349 MiB | 61.5 | 61.5 |
| 2 | 9503 MiB | 44.6 | 89 |
| 3 | 9653 MiB | 35.0 | 105 |
| 2 @ 128k ctx | OOM | — | — |

Decode is memory-bandwidth-bound, so a second stream is nearly free in VRAM and
gives about 45% more total throughput.

## Options for a "second instance"

| approach | one weights copy? | verdict |
|---|---|---|
| Separate llama-server processes | no | infeasible on 10 GB |
| One server, `-np 2 --kv-unified` | yes | **chosen** |
| One process, two `llama_context`s | yes | possible but needs custom code; only useful for per-role KV precision |

Full write-up: [`docs/engine-review.md`](https://github.com/aiguy110/bonsai-garden/blob/main/docs/engine-review.md).
