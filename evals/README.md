# evals

See `../docs/benchmark-plan.md` for the design.

```
arms/        one JSON per arm: model, thinking level, pi packages, settings, env. Immutable once run
tasks/<t>/   task.json (steps), repo/ (starting workspace), check.py (per-step checker)
run.py       runner: arms x tasks x repeats; each step is a fresh `pi -p` session
tap.py       metering pass-through between pi/mem0 and turnstile (per-request timings)
summarize.py results dir -> summary.md
results/     raw run dirs (gitignored); commit summaries under docs/ or a dated dir
.cache/      pi package installs, the eval venv (pytest), model hash (gitignored)
```

## Running

```bash
systemctl --user start bonsai-garden-embed     # only arms with memory need it
python3 evals/run.py --arms baseline,mem0 --tasks inventory --repeats 3
```

- All traffic uses the `local-llm-bench` turnstile key (priority 20), read from
  `~/Projects/local-llm-bench/turnstile_run.py`, so interactive pi (40) preempts runs
  between requests. Expect pauses when the GPU is in use.
- Workspaces live under `/tmp/bonsai-garden-evals/` so no AGENTS.md or CLAUDE.md from
  this repo leaks into the agent's context. pi runs with `--no-skills
  --no-prompt-templates --no-themes` and a private `PI_CODING_AGENT_DIR` per run.
- The agent and the checker get `.cache/venv` first on `PATH` (Python 3.12, pytest
  pinned), so `python3 -m pytest` works.
- Re-running with the same `--out` skips finished sequences, so an interrupted run
  can resume.

## Per-step record (`results.jsonl`)

`pass` (all checks), `checks` (each one), `wall_s`, `turns`, `tool_calls`, `exit`,
and `llm.<role>` with `requests`, `prompt_n` (tokens actually prefilled), `cache_n`
(reused), `predicted_n`, `prompt_ms`, `predicted_ms`, `queue_wait_ms`. Role `agent`
is pi; `mem` is mem0's LLM. Embedding calls go straight to the CPU server and
aren't metered.

## Tasks

- `inventory` (cross-session continuity, 3 steps). Step 1 states four conventions
  and a fact. Three conventions leave traces in the repo (rediscoverable). The
  closing `Risk:` line and the staging host and port exist only in the step 1
  conversation, so without memory the agent can't know them.
