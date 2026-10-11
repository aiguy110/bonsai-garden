# bonsai-garden

A local agent stack on bifrost's single RTX 3080. A pi agent runs on
Ternary-Bonsai-2-27B with a mem0 memory layer. The memory layer's LLM work runs on
the **same** Bonsai weights in a second server slot, and embeddings and retrieval
run locally. The point is to benchmark the agent with and without memory, and
later to try memory and compaction variants.

Status: **scaffold.** The engine review is done, and nothing is deployed yet.

## Layout

| Path | What |
|---|---|
| `docs/engine-review.md` | Measured throughput, the shared-weights feasibility study, and the phased engine proposal. **Start here** |
| `docs/architecture.md` | Target topology, roles, priorities, and open questions |
| `docs/benchmark-plan.md` | Arms, task suites, metrics, and run rules |
| `bench/` | Engine probe scripts plus dated raw results |
| `docs/phase-a-runbook.md` | Step-by-step runbook for Phase A (2-slot config, pi registration) |
| `serving/` | Proposed llama-swap entry (not applied) |
| `memory/` | Draft mem0 config. Runtime data goes in `memory/data/` (gitignored) |
| `agent/` | pi wiring: models.json entry and memory extension choice |
| `evals/` | Benchmark harness: arms, tasks, and results |

## Running a probe

```bash
~/Projects/local-llm-bench/turnstile_run.py -- bench/engine_probe.sh /tmp/probe
~/Projects/local-llm-bench/turnstile_run.py -- bench/server_probe.sh /tmp/probe 2 98304
```

Probes start a private llama-server on :8089 and hold a turnstile lease, so they
never touch the live llama-swap service.

## Next steps

1. Phase A (`docs/phase-a-runbook.md`): apply the 2-slot llama-swap entry and add
   `bonsai-2-27b` to `~/.pi/agent/models.json`. Needs user approval, because it
   changes the live service.
2. Choose the pi memory extension, then stand up the CPU embedder and mem0.
3. Write the first cross-session task sequence and the `baseline` and `mem0` arms.
4. Phase B: turnstile co-admission, so agent and memory calls can batch.
