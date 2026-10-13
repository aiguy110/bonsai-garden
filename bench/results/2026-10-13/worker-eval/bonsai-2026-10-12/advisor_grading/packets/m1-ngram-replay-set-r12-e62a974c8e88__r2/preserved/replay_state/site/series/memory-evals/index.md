---
layer: series
series: memory-evals
order: 2
title: Does memory help across sessions?
status: active
updated: 2026-10-11
tldr: Baseline vs mem0 on multi-session coding tasks; first result favors memory (2/3 vs 0/3 full sequences) on one task.
summary: |
  **Goal:** measure whether a memory layer makes the local agent better at work
  that spans several sessions, and what it costs on a shared 10 GB GPU.

  **Design:** each task is a sequence of coding steps in one repo. Every step runs
  as a **fresh agent session** inside a no-network Docker sandbox, so memory is the
  only thing that carries over. A script checks correctness and each project
  convention separately. Each arm runs 3+ times.

  **Results so far:**
  - **inventory** (3 steps): mem0 completed the whole sequence **2/3** times,
    baseline **0/3**. Both arms followed conventions they could see in the repo.
    Only mem0 kept rules and facts that were stated in conversation and never
    written down.
  - Memory added no measurable wall-time. Its cost is ~8k tokens of prefill per
    memory write, which runs on the second GPU slot.

  **Next:** more task sequences, a regression set where memory isn't needed,
  ≥5 repeats, and memory variants (prompts, top-k, write cost).
---

## Arms

| arm | memory | notes |
|---|---|---|
| `baseline` | none | pi, `bonsai-agent`, thinking low |
| `mem0` | mem0 auto-capture + auto-recall | memory LLM is `bonsai-mem` (slot 1); CPU embedder |

Arm configs are immutable once run. New variants become new arms.

## Harness rules

- Every agent step runs in Docker: host `/usr` read-only, `--network none`, empty
  home and `/tmp`, neutral paths (`/home/dev/inventory`). Its only exit is a
  metering proxy that forwards `/v1/` API calls.
- **Why the sandbox:** the first, unsandboxed run was contaminated. Asked to do
  something "as discussed before", the baseline agent searched the disk, found
  another run's workspace and a reference solution, and copied the answer. It
  also read "baseline-mem0" in its working-directory name and deduced it was in a
  memory eval. Those results were discarded.
- Each step records success, every check, wall time, turns, and tokens split by
  role (agent vs memory). It also records queue wait and the final memory store.
- Runs use a low-priority scheduler key, so interactive use preempts them.

Harness code: [`evals/`](https://github.com/aiguy110/bonsai-garden/tree/main/evals).
