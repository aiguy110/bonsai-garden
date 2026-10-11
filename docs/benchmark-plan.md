# Benchmark plan

Goal: compare the pi agent on Bonsai **with and without** the memory layer, then
evaluate later memory and compaction variants against the same tasks.

## Arms (each one is a named config in `evals/arms/`)

| Arm | Memory | Compaction | Notes |
|---|---|---|---|
| `baseline` | off | pi default | control |
| `mem0` | mem0 (Bonsai slot 1 + CPU embedder) | pi default | first treatment |
| later | mem0 variants (prompts, top-k, reasoning effort), alternative compaction | | add as new arms; never edit a finished arm |

## Task suites

1. **Cross-session continuity** (the memory layer's reason to exist): sequences of
   2–5 related tasks in one repo, each run in a **fresh pi session**. Later tasks
   depend on facts, decisions, or conventions from earlier ones. Memory should
   help here; without memory the agent has to rediscover them.
2. **Single-session long-horizon**: tasks that push past compaction, to measure
   compaction strategy and in-session recall.
3. **Regression guard**: a small standard coding set, to check memory doesn't
   hurt tasks that don't need it, for example by adding noise or tokens.
4. **Memory layer alone** (optional): a LongMemEval/LoCoMo-style subset, to
   isolate mem0+Bonsai retrieval quality from agent skill.

## Metrics per run

Record task success (scripted checker), turns, wall time, agent and memory tokens
(prompt and completion, split by role), turnstile queue wait, per-turn
re-prefill tokens, and decode tok/s. Also record memory ops (adds, updates, and
retrievals, plus whether the retrieved items were relevant), plus the final
memory store snapshot.

## Rules

- Pin everything per run: model file hash, server flags, pi version, extension
  version, mem0 config, and prompts. Store them in the run manifest.
- Fixed seeds where possible. Bonsai samples at temp 1.0, so run **N≥3 repeats per
  task** and report spread.
- Reset memory state per run (fresh Qdrant path) unless the arm tests carryover.
- Runs go through turnstile with the `local-llm-bench` key (prio 20), for **both**
  agent and memory calls. They're batch jobs and must not starve interactive pi.
- Results are append-only JSONL under `evals/results/` (gitignored if large;
  commit the summaries).
