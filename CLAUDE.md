# bonsai-garden

Local agent stack on bifrost's single RTX 3080: a pi agent on Ternary-Bonsai-2-27B
with a mem0 memory layer whose LLM work runs on the same weights in a second
llama-server slot. Goal: benchmark the agent with and without memory, then try
memory and compaction variants. Start with `README.md` and `docs/engine-review.md`.

## Workflow (SOP)

- After a change is validated (probe re-run, config checked, docs consistent),
  commit it and merge it into `main`. Don't leave validated work on a side branch.
- Commit messages are imperative and say why. Unvalidated experiments stay on a
  branch until they are.
- Changes that touch the live stack (`/etc/llama-swap/config.yaml`, turnstile, pi's
  `models.json`) need the user's go-ahead first; proposed configs live in `serving/`.

## Environment notes

- GPU work goes through turnstile: run probes with
  `~/Projects/local-llm-bench/turnstile_run.py -- <script>`, using a private
  llama-server port (8089), never the live llama-swap on :11435.
- Turnstile evicts by model name; the agent and memory roles share one real model.
- Raw benchmark results go in dated dirs under `bench/results/`.
