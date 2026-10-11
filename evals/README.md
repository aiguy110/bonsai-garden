# evals

See `../docs/benchmark-plan.md`.

```
arms/      one file per arm (memory on/off, mem0 settings, compaction); immutable once run
tasks/     task sequences: setup repo, per-step prompt, scripted checker
results/   append-only run JSONL + manifests (raw data gitignored, summaries committed)
```
