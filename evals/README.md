# evals

See `../docs/benchmark-plan.md` for the design.

```
arms/        one JSON per arm: model, thinking level, pi packages, settings, env. Immutable once run
tasks/<t>/   task.json (steps), repo/ (starting workspace), check.py (per-step checker)
run.py       runner: arms x tasks x repeats; each step is a fresh `pi -p` session
tap.py       metering pass-through between pi/mem0 and turnstile (per-request timings)
relay.py     TCP -> Unix socket relay: in the sandbox to the tap and mem0 server, on the host to the tap
mem0_server.py  Python mem0 behind upstream's REST endpoints, one per step for self-hosted arms
summarize.py results dir -> summary.md
results/     raw run dirs (gitignored); commit summaries under docs/ or a dated dir
.cache/      pi package installs, the sandbox venv (pytest), model hash (gitignored)
```

## Running

```bash
systemctl --user start bonsai-garden-embed     # only arms with memory need it
python3 evals/run.py --arms baseline,mem0,mem0-server --tasks inventory --repeats 3
```

- All traffic uses the `local-llm-bench` turnstile key (priority 20), read from
  `~/Projects/local-llm-bench/turnstile_run.py`, so interactive pi (40) preempts runs
  between requests. Expect pauses when the GPU is in use.
- **Every pi step runs in a Docker sandbox** (`ubuntu:24.04` with the host's `/usr`
  read-only, `--network none`, empty tmpfs home and `/tmp`, own PID namespace). It
  sees only `/home/dev/inventory` (the workspace), `/home/dev/.pi/agent` (this run's
  agent dir), `/home/dev/.local/share/mem0` (this run's memory), `/opt/node`, and
  `/opt/venv`. Its only way out is the tap, over a Unix socket via `relay.py`; the
  tap forwards only `/v1/` paths to turnstile and the embedder. pi runs with
  `--no-session`, so earlier steps can only come back through memory.
  **Why:** the first, unsandboxed baseline run searched the disk for "as discussed
  before", found another run's workspace and a reference solution, and copied the
  answer. Neutral paths matter too: it had read
  "baseline-mem0" in its cwd and reasoned that this was a memory eval. Those results
  are kept as `results/2026-10-11-CONTAMINATED-unsandboxed` and aren't used.
- pi runs with `--no-skills --no-prompt-templates --no-themes` and a private
  `PI_CODING_AGENT_DIR` per run.
- The sandbox venv (Python 3.12, pytest pinned) is first on `PATH` inside the
  container and for the checker, which runs on the host.
- Re-running with the same `--out` skips finished sequences, so an interrupted run
  can resume.

## Self-hosted mem0 arms

An arm with a `mem0_server` block (`mem0-server.json`) runs Python mem0 instead of the
JS port inside pi. `pip` is a list of requirements installed into a cached venv
(`.cache/mem0srv-<hash>`). To try a mem0 change, add a new arm whose `pip` points at a
fork's git ref (`mem0ai[nlp] @ git+https://github.com/<fork>/mem0@<sha>`). `config` is
`Memory.from_config` input with `{HOSTTAP}`, `{STORE}` and `{CACHE}` substituted.

For each step the harness starts `mem0_server.py` on the host, on a Unix socket. Its
store is `runs/<id>/mem0-server/` and its `~/.mem0` is in there too (`MEM0_DIR`). A
host relay sends its LLM and embedder calls to that step's tap, so they are tagged
`mem`/`embed` like the embedded arm's. The socket is mounted into the sandbox, and pi
reaches it at `127.0.0.1:8092`. The server's log is `step<i>.mem0.log`. After the
step, its memories are dumped to `memories.json`. The manifest records the venv's
`pip freeze`.

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
