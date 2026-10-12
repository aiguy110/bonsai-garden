---
layer: experiment
series: serving
title: GPU scheduler co-admission and virtual models
status: done
date: 2026-10-11
updated: 2026-10-12
tldr: Turnstile now lets agent and memory requests run together on one model, with a context budget and per-role limits; all 9 live checks pass.
summary: |
  **Problem:** [turnstile](https://github.com/aiguy110/gpu-turnstile), the GPU scheduler shared by everything on this machine,
  admitted one LLM request at a time. It also evicted models by name. So memory
  calls had to wait behind the agent, and the two-slot speedup could never happen.

  **Change:** three features.
  1. **Co-admission:** a queued request can join running ones for the same model,
     up to its slot count. It never jumps ahead of higher-priority work.
  2. **Context budget:** concurrent requests must fit together in the server's
     shared 96k-token pool.
  3. **Virtual models:** `bonsai-agent` and `bonsai-mem` map to the real model.
     Each pins a slot, caps context, and can inject request settings, e.g.
     thinking off and temperature 0.2 for memory.

  **Validation (live, 9/9 pass):** agent and memory overlapped with **0 ms** wait,
  decoding at 44–45 tok/s each. Slot pinning held. Oversized requests got a clean
  400. Two 50k-token requests correctly took turns. GPU leases waited for both LLM
  requests to finish.
---

## Live configuration

```yaml
models:
  bonsai-2-27b: { slots: 2, ctxPool: 98304 }
virtual:
  bonsai-agent: { backend: bonsai-2-27b, maxCtx: 81920, inject: { id_slot: 0 } }
  bonsai-mem:
    backend: bonsai-2-27b
    maxCtx: 32768
    defaultMaxTokens: 1024
    inject: { id_slot: 1, chat_template_kwargs: { enable_thinking: false },
              temperature: 0.2, max_tokens: 2048 }
```

`bonsai-mem` started at a 12k cap. It was raised to 32k after mem0's extraction
prompts, about 8k real tokens and ~11k by turnstile's deliberately pessimistic
estimate, were rejected.

## Validation output

```
[PASS] agent+mem co-admitted -- mem waited 0 ms, overlap 6.1s
[PASS] both decode at the 2-slot rate (~45 tok/s) -- tok/s [43.9, 44.9]
[PASS] alias logged
[PASS] agent pinned to slot 0, mem to slot 1
[PASS] bonsai-mem returns no reasoning -- reasoning chars 0
[PASS] bonsai-agent still reasons -- reasoning chars 998
[PASS] over-maxCtx request gets 400 context_length_exceeded
[PASS] over-budget pair serializes -- second waited 28814 ms
[PASS] lease waits for both LLM holders -- lease waited 6.2s
```

Turnstile source: [aiguy110/gpu-turnstile](https://github.com/aiguy110/gpu-turnstile) (`internal/queue`, `internal/proxy/route.go`).
Script: [`bench/phase_b_validate.py`](https://github.com/aiguy110/bonsai-garden/blob/main/bench/phase_b_validate.py).

## Token estimate

Turnstile estimates prompt size as `ceil(chars / 3) + 8` per message, without
calling a tokenizer. In practice that overestimates by about 1.4x. That is safe
for the budget but tight for small caps.
