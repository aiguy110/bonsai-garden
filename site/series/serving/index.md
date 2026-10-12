---
layer: series
series: serving
order: 1
title: Serving two roles from one model on 10 GB
status: done
updated: 2026-10-11
tldr: One server with two slots runs the agent and the memory layer on a single copy of the weights; the GPU scheduler now lets them overlap.
summary: |
  **Goal:** run the agent and the memory layer's LLM on the same 27B model without
  a second copy of the weights. A second copy would need another 6.7 GB, and the GPU
  only has 10.

  **Findings:**
  - A single llama-server with **two parallel slots** shares one copy of the
    weights. The second slot costs about **+150 MiB**. Each stream drops from 61 to
    45 tok/s, but total throughput rises about **45%**.
  - At realistic agent context depth (32k tokens), decode is **~45 tok/s**, not the
    headline 64.
  - The prompt cache handles append-only agent conversations perfectly. Each turn
    prefills only the new tokens, so no tuning was needed.
  - The GPU scheduler (turnstile) used to admit one request at a time, which
    erased the gain. It now co-admits up to `slots` requests for the same model,
    keeps a shared context budget, and exposes per-role virtual models
    (`bonsai-agent`, `bonsai-mem`). All 9 live validation checks pass.

  **Status:** deployed. Per-role KV-cache precision and n-gram speculation are
  deferred until the memory evals show a need.
---

This series answers a feasibility question that comes before any memory
experiment: can both roles fit, and can they run at the same time?

## What carried forward

- The production config: `bonsai-2-27b` with `--parallel 2 --kv-unified -c 98304`,
  plus q4_0 KV.
- Two virtual model names in turnstile: `bonsai-agent` (pinned to slot 0, 80k
  context cap) and `bonsai-mem` (slot 1, 32k cap, thinking off, temperature 0.2).
- Planning number: ~45 tok/s decode per stream when both slots are busy or the
  context is deep.

## Deferred ideas

- **N-gram self-speculation.** It reached 162 tok/s on repeated text and showed
  no slowdown on fresh text. Agents re-emit a lot of code, so this is worth testing
  on real traces.
- **Different KV precision per role.** This needs a custom server. Only worth it
  if memory quality turns out to be sensitive to KV quantization.
