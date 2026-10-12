# bonsai-garden

A local agent stack on bifrost's single RTX 3080. A pi agent runs on
Ternary-Bonsai-2-27B with a mem0 memory layer. The memory layer's LLM work runs on
the **same** Bonsai weights in a second server slot, and embeddings and retrieval
run locally. The point is to benchmark the agent with and without memory, and
later to try memory and compaction variants.

Status: **Phases A and B deployed** (2-slot `bonsai-2-27b`; turnstile co-admission and
the `bonsai-agent` / `bonsai-mem` virtual models; pi defaults to `bonsai-agent`).

## Layout

| Path | What |
|---|---|
| `docs/engine-review.md` | Measured throughput, the shared-weights feasibility study, and the phased engine proposal. **Start here** |
| `docs/architecture.md` | Target topology, roles, priorities, and open questions |
| `docs/benchmark-plan.md` | Arms, task suites, metrics, and run rules |
| `bench/` | Engine probe scripts plus dated raw results |
| `docs/phase-a-runbook.md` | Step-by-step runbook for Phase A (2-slot config, pi registration) |
| `docs/phase-b-runbook.md` | Turnstile work: co-admission, context budget, virtual models (in [gpu-turnstile](https://github.com/aiguy110/gpu-turnstile)) |
| `serving/` | The applied llama-swap entry and the CPU embedder unit |
| `agent/` | pi wiring: models.json entry and memory extension choice |
| `evals/` | Benchmark harness: arms, tasks, runner, metering tap, results |
| `site/` | Research site (GitHub Pages): project → series → experiment pages; see `site/AUTHORING.md` |

## Running a probe

```bash
~/Projects/local-llm-bench/turnstile_run.py -- bench/engine_probe.sh /tmp/probe
~/Projects/local-llm-bench/turnstile_run.py -- bench/server_probe.sh /tmp/probe 2 98304
```

Probes start a private llama-server on :8089 and hold a turnstile lease, so they
never touch the live llama-swap service.

## Next steps

1. ~~Phase A~~ done 2026-10-11 (results in `docs/engine-review.md` §5).
2. ~~Memory stack and first baseline vs mem0 eval~~ done 2026-10-11 (site: memory-evals).
3. Keep `site/` current: every new result updates its experiment, series and project pages.
4. ~~Phase B~~ done 2026-10-11 (results in `docs/engine-review.md` §5).
