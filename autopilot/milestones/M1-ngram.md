# M1: n-gram self-speculation on real traffic

## Question

Does llama-server's n-gram self-speculation (`--spec-type ngram-*`, no draft model)
speed up the stack's real traffic, i.e. pi agent turns and mem0 extraction calls,
including when both slots are busy at once? If it does, deploy it to the live
`bonsai-2-27b` entry. That entry is the server the worker itself runs on.

## What is already known

- `docs/engine-review.md`: on one slot, `--spec-type ngram-mod` drafted nothing on a
  fresh prompt (61.0 vs 61.5 tok/s) and reached 162 tok/s on repeated text, with +4
  MiB VRAM. It was never tested with `--parallel 2`, and never on agent traffic.
- Baseline on the live config (2026-10-11, `autopilot/infra.py baseline`): 61.9 tok/s
  on a single stream, 43.8 / 44.8 tok/s with both slots busy.
- Agents re-emit file contents, diffs and test output a lot, so drafts from earlier
  context should often be accepted. mem0 extraction mostly restates the
  conversation as facts, which may also suit n-gram drafting.

## Material

- `bench/server_probe.sh`, `bench/checkpoint_replay.py`: existing probes. Both start a
  **private** llama-server on :8089 under a turnstile GPU lease, with the
  production flags. Extra server flags pass through.
- Recorded traffic is on the host only, gitignored, and not visible in the sandbox:
  `/home/josiah/Projects/bonsai-garden/evals/results/2026-10-11-baseline-mem0/runs/*/step*.events.jsonl`. These are pi
  JSON event streams with full assistant messages, tool calls and tool results.
  mem0's request bodies were not logged, but its prompts can be rebuilt from the
  extension's code (see `site/series/memory-layers/mem0-in-pi.md`). To read or
  convert the recordings, write a script and run it with a `run` request.
- llama-server flags: `--spec-type`, and the `--spec-ngram-*` / `--draft-*` options.
  Check `llama-server --help` for the fork at
  `~/Projects/llama.cpp-bonsai2/build/bin/llama-server` (run that in a `run` request
  too).

## Done when

1. A replay of real agent turns, and of mem0-style extraction calls if feasible,
   is measured on :8089, with speculation off vs on (≥2 settings). Both runs have
   1 slot busy and 2 slots busy. Report decode tok/s, draft acceptance, and
   whether outputs at temperature 0 are identical.
2. A decision based on the numbers. If speculation helps with both slots busy,
   apply it to the live entry with an `infra` request and record the post-deploy
   health numbers. If it doesn't, say so and leave the stack alone.
3. An experiment page in the `serving` series, plus updated series and project
   summaries (`site/AUTHORING.md`).
