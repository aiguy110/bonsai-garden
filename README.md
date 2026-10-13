# bonsai-garden

A local agent stack on bifrost's single RTX 3080. A pi agent runs on
Ternary-Bonsai-2-27B with a mem0 memory layer. The memory layer's LLM work runs on
the **same** Bonsai weights in a second server slot, and embeddings and retrieval
run locally. The point is to benchmark the agent with and without memory, and
later to try memory and compaction variants.

Status: **Phases A and B deployed** (2-slot `bonsai-2-27b`; turnstile co-admission and
the `bonsai-agent` / `bonsai-mem` virtual models; pi defaults to `bonsai-agent`).
M1 n-gram self-speculation replay is complete: it slowed busy two-slot traffic
and was not deployed. W1 local-worker replay is complete: on 22 real cloud-worker
rounds run twice, Bonsai submitted valid requests in 25/44 attempts (56.8%) and
matched request kind in 21/44 (47.7%); W2 will test worker-harness changes.

## Layout

| Path | What |
|---|---|
| `docs/engine-review.md` | Measured throughput, the shared-weights feasibility study, and the phased engine proposal. **Start here** |
| `docs/architecture.md` | Target topology, roles, priorities, and open questions |
| `docs/roadmap.md` | Milestones (M1 n-gram speculation onward) and the autopilot design |
| `docs/benchmark-plan.md` | Arms, task suites, metrics, and run rules |
| `bench/` | Engine probe scripts plus dated raw results |
| `docs/phase-a-runbook.md` | Step-by-step runbook for Phase A (2-slot config, pi registration) |
| `docs/phase-b-runbook.md` | Turnstile work: co-admission, context budget, virtual models (in [gpu-turnstile](https://github.com/aiguy110/gpu-turnstile)) |
| `serving/` | The applied llama-swap entry and the CPU embedder unit |
| `agent/` | pi wiring: models.json entry and memory extension choice |
| `evals/` | Benchmark harness: arms, tasks, runner, metering tap, results |
| `autopilot/` | Unattended roadmap runner: Bonsai worker, cloud advisor, guarded live-config changes |
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
5. ~~M1 n-gram self-speculation~~ done 2026-10-12: default `ngram-mod` was
   slower with both slots busy (agent 26.7 vs 31.3 tok/s; mem0 23.4 vs 25.4),
   changed outputs, and was not deployed.
6. Next local-worker step: W2 tests thinking/history and output budget, tool-output
   caps, editing, session discipline, and compaction against the W1 replay baseline.
   In parallel, expand the continuity suite to more tasks and repeats, then add the
   unrelated-task regression guard. See [the local-worker experiment](site/series/local-worker/worker-eval.md).
