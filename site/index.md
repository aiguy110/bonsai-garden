---
layer: project
title: bonsai-garden
updated: 2026-10-13
tldr: A coding agent with long-term memory on one 10 GB GPU; its local-worker baseline now measures where the research harness fails.
summary: |
  **Question:** can a small local coding agent get measurably better at multi-session
  work—and eventually perform its own guarded research—when everything runs on one
  RTX 3080?

  **Setup:** [pi](https://github.com/badlogic/pi-mono) runs on Ternary-Bonsai-2-27B;
  mem0 uses the same weights through a second server slot plus a CPU embedder.

  **So far:** two roles share one model copy; the first memory task favored mem0
  (2/3 full sequences vs 0/3); and n-gram speculation slowed busy two-slot traffic.
  The new [local-worker baseline](series/local-worker/worker-eval.md) replayed 22
  real cloud-worker rounds twice: Bonsai made valid requests in **25/44 (56.8%)**
  and matched kind in **21/44 (47.7%)**. A 10-request advisor sample approved 7.

  **Next:** W2 tests worker-harness changes for context, tools, editing, session
  discipline, and compaction; memory and broader continuity evaluation continue
  separately.
---

Live progress from the autopilot (its current worker is a cloud model):
[autopilot status]({{ '/autopilot.html' | relative_url }}).

## Why this exists

Coding agents forget everything between sessions. Hosted memory products exist, but
the interesting question for local setups is whether a memory layer is worth its
cost when it has to share a small GPU with the agent itself. Every memory write and
recall is LLM work competing for the same 10 GB.

## The stack

```
pi agent ──► turnstile (GPU scheduler) ──► llama-swap ──► llama-server, 2 slots
mem0 ──────► turnstile ─────────────────┘   slot 0: agent   slot 1: memory
mem0 ──────► CPU embedder (Qwen3-Embedding-0.6B)
```

- **Model:** Ternary-Bonsai-2-27B, PQ2_0 quantization, q4_0 KV cache, 96k-token
  shared context pool.
- **Agent:** pi, with thinking set to low.
- **Memory:** mem0 (open-source build, in-process) through the
  `@amaster.ai/pi-memory-mem0` pi extension. It auto-captures after each turn and
  auto-recalls before each prompt. Vectors live in SQLite. Nothing leaves the machine.
- **Scheduler:** [turnstile](https://github.com/aiguy110/gpu-turnstile), a small GPU arbiter shared with other local
  workloads. It was extended so the agent and memory roles can share one model
  instead of evicting each other.

## Trajectory

1. **Engine review (2026-10-10).** Measured what the GPU can do. Found that "a
   second small model for memory" is unnecessary: a second slot on the same server
   does the job.
2. **Two-slot server (2026-10-11).** Deployed it. A feared prompt-cache problem
   turned out not to exist for append-only agent traffic.
3. **Scheduler co-admission (2026-10-11).** Turnstile now lets agent and memory
   requests overlap, with a context budget and per-role virtual models.
4. **First memory benchmark (2026-10-11).** Baseline vs mem0 on a 3-session task.
   The first attempt was thrown out: without a sandbox, the agent searched the disk
   and found another run's answer. Re-run inside Docker with no network.
5. **N-gram replay (2026-10-12).** Default `ngram-mod` was slower on real
   two-slot production traffic (agent 26.7 vs 31.3 tok/s; mem0 23.4 vs 25.4),
   and a shorter-draft variant also lost under greedy sampling. The live server
   stays non-speculative.
6. **Local-worker replay (2026-10-13).** On 22 real cloud-worker rounds replayed
   twice, Bonsai made 25/44 deterministically valid requests and 21/44 kind
   matches. W2 now tests harness changes against that baseline.

## Open questions

- Does memory help on more than one hand-built task? We need several sequences and
  more repeats.
- Does memory *hurt* tasks that don't need it, through noise in the prompt or
  through wrong recalls?
- Each memory write costs about 8k tokens of prefill with no cache reuse. Can that
  be cut?
