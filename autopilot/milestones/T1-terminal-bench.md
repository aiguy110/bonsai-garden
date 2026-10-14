# T1: Terminal-Bench probe

## Question

Our worker eval is 22 rounds of one milestone in one repo, and only 9 of them separate
arms. Can Terminal-Bench 2.0 (TB2) give us signal for Bonsai, or is its fail rate too
high to separate harnesses? And how does vanilla pi compare with stock oh-my-pi (`omp`),
both without memory? This is a small probe (N=1), run before W2 resumes (user decision
2026-10-14). It answers "is TB2 worth adopting", not "which harness is better".

## Design

Two harnesses, both on the same model entry (`garden/bonsai-agent` through the bench tap
and turnstile), no memory layer in either:

- **pi:** stock pi 0.86.1, no extensions on TB tasks. On the signal cases this is the
  honest baseline `bonsai-2026-10-12-honest`, which already has these records: reuse
  its repeat-1 records (repeat 2 as a reference), do not rerun it.
- **omp:** stock oh-my-pi at its default settings, with Mnemopi and any other memory
  feature off. Change nothing beyond model and provider wiring.

Two case sets, N=1 per harness:

1. **10 TB2 tasks**, drawn at random: seed 20261014, `random.Random(seed).sample` over
   the sorted task names of the pinned dataset version. If a task cannot run on this
   host at all (it needs a GPU, more RAM than the host has, or similar), record why
   and take the next task in the same seeded order. Don't swap tasks for being hard.
2. **The 9 W2 signal cases** (`bench/worker_eval/cases-signal.jsonl`) for omp, under
   the W1 replay rules: honest prompt, 20-minute limit, `submit_request` if it loads
   under omp, else the JSON fallback (say which). Run them as the arm
   `w2-omp-stock`, so W2's omp item can reuse the records.

## What is already known

Verify each before relying on it.

- TB2's official harness is Harbor (`harbor run -d terminal-bench/terminal-bench-2`;
  some sources write `terminal-bench@2.0`). It runs each task in its own Docker
  container and grades it with the task's tests. A custom agent is passed with
  `--agent-import-path module:Class`, and one task with `--include-task-name`. The
  oracle agent checks the setup. Docs: tbench.ai/docs/run-terminal-bench-2-0 and
  github.com/harbor-framework/harbor.
- TB2 has 89 tasks; the task count differs between sources, so record the real one.
  Frontier agents score under about 65%; GPT-OSS-20B scored about 3%. Bonsai on pi has
  not been measured.
- Each task sets its own agent timeout. Use it as is: it is part of the benchmark.
- Bun 1.4.3 is installed at `~/.local/bin/bun` (zip sha256 `3e730528…e18`). omp is not
  installed; pack it with `npm pack --ignore-scripts` into a new empty directory, as
  W2's omp item says. Don't install a runtime.
- This branch starts from W2's state, so `bench/worker_eval/` already has `run.py`,
  `cases-signal.jsonl`, `compare.py` and the honest baseline.

## Constraints

- Don't change files under `autopilot/`, the live llama-swap entry or turnstile. The
  GPU stays capped at 250 W.
- Model traffic goes through the bench tap with the bench key, like W1. Agent
  containers reach it via the Docker host gateway. Bind any proxy to loopback or the
  Docker bridge only, never 0.0.0.0. Runs that send LLM requests are `gpu:false` (see
  facts). Chunks are at most 150 min.
- Install Harbor in its own virtualenv under `bench/terminal_bench/`, pinned, with the
  version and hashes recorded. Pull task images by digest and record the digests.
- Agent runtimes (Node and pi, Bun and omp) go into task containers as read-only mounts
  of host copies pinned by hash. Install over the network inside the task only if
  that is impossible, and say why. No secrets or tokens go into any container, and no
  host path other than these mounts and the output directory.
- If the 20 TB attempts' summed task timeouts exceed 12 GPU-hours, report that before
  running them.

## Done when

1. `bench/terminal_bench/` holds a recon note (Harbor version, dataset version and
   commit, task count, how a custom agent runs, how pi and omp get into the container,
   per-task timeouts of the drawn tasks), the seeded task list with any skips and
   their reasons, and the two agent adapters.
2. The oracle agent passes on at least 2 of the drawn tasks: that checks the setup.
3. Each harness has 10 TB records: pass/fail from the task tests, timeout, wall time,
   turns, tool calls, request and token counts from the tap, and the failure mode
   (no progress, wrong answer, timeout, harness error).
4. `w2-omp-stock` has 9 records on the signal cases, compared with the honest baseline
   by `compare.py`, with the first request's prompt tokens under each harness.
5. A short experiment page in the local-worker series (`site/AUTHORING.md`), with
   per-task tables for both case sets and the pass rate per harness. It gives a
   verdict on TB2 with this rule: if both harnesses pass at most 1 of 10, TB2 is too
   hard for Bonsai to separate arms; otherwise propose how to add TB2 tasks to the
   worker eval (for example, a signal screen like W2's). It states pi vs omp as N=1
   observations, not a ranking. `docs/roadmap.md` is updated.
