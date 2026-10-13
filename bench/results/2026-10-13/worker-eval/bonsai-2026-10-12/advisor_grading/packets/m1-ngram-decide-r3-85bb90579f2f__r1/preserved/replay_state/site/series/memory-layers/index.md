---
layer: series
series: memory-layers
order: 3
title: Memory layers for a small local agent
status: active
updated: 2026-10-11
tldr: How the current memory layer (mem0) actually works inside pi, and which other designs it will be compared against.
summary: |
  **Goal:** understand the memory layer we're using, then find out whether a
  different design suits a 2-bit 27B model on one GPU better.

  **So far:**
  - A code-level walkthrough of mem0 in pi. The pi extension runs on four
    events, and memory reaches the model only as a quoted user-channel message.
  - mem0 OSS 3.x is a passive, **add-only** extractor. Each write is one large LLM
    call (the extraction prompt alone is ~36 KB, the source of the ~8k-token
    cost). Deduplication is by exact hash only, so a paraphrased fact is stored
    again, and a changed fact never replaces the old one.

  **Planned comparisons:**
  - **Agent-managed memory blocks** (Letta/MemGPT style). It makes no extra LLM
    calls, but the agent has to decide what to save.
  - **Graphiti**, a temporal knowledge graph. Facts have validity intervals, so
    updates replace old facts, at the cost of several LLM calls per write.

  Both run on the memory-evals tasks, plus new tasks where a fact changes.
---

Each candidate becomes an arm in `evals/arms/` and runs on the same tasks as
`baseline` and `mem0`. The comparison measures pass rate against memory-LLM tokens
per step. See the [roadmap](https://github.com/aiguy110/bonsai-garden/blob/main/docs/roadmap.md)
(M4).
