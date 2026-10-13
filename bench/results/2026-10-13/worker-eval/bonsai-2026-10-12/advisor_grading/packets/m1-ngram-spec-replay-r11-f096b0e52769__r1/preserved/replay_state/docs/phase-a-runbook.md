# Phase A runbook: two-slot `bonsai-2-27b`

For a fresh agent. Read `README.md` and `docs/engine-review.md` (§1–3, §5) first.
Phase A is config-only: no code changes in turnstile or llama.cpp.

## Goal

Serve `bonsai-2-27b` with `--parallel 2 --kv-unified --checkpoint-min-step 2048`
(one copy of the weights, two slots), register it in pi, and measure the effect on
real pi traffic. Expected: ~9.5 GB VRAM at 98304 ctx, ~770 MiB headroom.

## Ground rules

- **Get the user's go-ahead before touching the live stack.** Steps 3–5 edit
  `/etc/llama-swap/config.yaml`, restart llama-swap (sudo, interrupts any model in
  use), and edit `~/.pi/agent/models.json`. Steps 1–2 are safe at any time.
- Turnstile is the GPU arbiter. Anything holding the GPU directly must hold a lease:
  `~/Projects/local-llm-bench/turnstile_run.py -- <cmd>` (key `local-llm-bench`,
  priority 20). If `curl -s localhost:8080/api/queue` shows a holder, your lease
  waits; that's expected. Use the `gpu-turnstile` skill for details.
- Probes use a private llama-server on :8089. Never benchmark against live
  llama-swap (`:11435`) or turnstile (`:8080`).
- Don't change the model **name** `bonsai-2-27b`. Turnstile evicts by name.
- Fork binary: `~/Projects/llama.cpp-bonsai2/build/bin/llama-server` (PrismML,
  commit 9a9394a). Stock llama.cpp rejects this model. `LLAMA_ATTN_ROT_DISABLE=1`
  is required for the mean-center bias.

## Steps

1. **Baseline (safe).** Re-run `bench/server_probe.sh OUT 1 98304` and
   `OUT 2 98304` under a lease and compare with `bench/results/2026-10-10/`
   (1 slot: ~61 tok/s, 9349 MiB; 2 slots: ~45 tok/s each, 9503 MiB). If numbers
   drifted by more than ~10%, find out why before continuing (driver, desktop
   GPU use, thermal).
2. **Checkpoint-spacing test (safe).** Add a script under `bench/` that replays a
   multi-turn agent-shaped conversation (growing history, with earlier `<think>`
   blocks stripped by the template) against a private server twice, with `-cms 8192`
   and `-cms 2048`. Record `prompt_n` (tokens re-processed) and prefill time per
   turn from the `/completion` or chat `timings`. Commit the script and results.
   Check `--cache-ram` use. If 2048 doesn't clearly reduce re-processing, don't ship it.
3. **Apply the config (needs go-ahead).**
   ```bash
   cp /etc/llama-swap/config.yaml /etc/llama-swap/config.yaml.bak.$(date +%Y%m%d-%H%M%S)
   # edit ONLY the "bonsai-2-27b" entry to match serving/llama-swap.bonsai-2-27b.proposed.yaml
   sudo systemctl restart llama-swap
   ```
   llama-swap listens on :11435. Then unload any warm model through turnstile
   (`curl -X POST localhost:11435/api/models/unload/<model>`) if the GPU is busy.
4. **Validate through the real path.** Send a chat completion to
   `http://localhost:8080/v1/chat/completions` with the pi key and
   `model: bonsai-2-27b` (the key is in `~/Projects/gpu-turnstile/.keys.env`; don't
   copy it into this repo). Confirm in `journalctl --user -u turnstile -f` that it
   is tagged `name=pi priority=40`, check `nvidia-smi` (expect ≲9.6 GB), and confirm
   llama-swap logs `n_slots = 2`.
   Then send two simultaneous requests **directly to llama-swap** (:11435) and
   confirm both stream at the ~45 tok/s rate. Through turnstile they serialize, so
   that part waits for Phase B.
5. **Register in pi.** Add this to the `llama-swap` provider's `models` array in
   `~/.pi/agent/models.json`, and keep a copy under `agent/`:
   ```json
   {
     "id": "bonsai-2-27b",
     "name": "Bonsai 2 27B (llama-swap, local, 96k ctx)",
     "reasoning": true,
     "input": ["text"],
     "contextWindow": 98304,
     "maxTokens": 16384,
     "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}
   }
   ```
   See the `pi-agent` skill for settings and compaction. Run a short real pi session
   on it and note tokens re-processed per turn (llama-swap/server logs).
6. **Rollback.** Restore the backup config, `sudo systemctl restart llama-swap`,
   and remove the pi entry. If VRAM headroom is a problem, first try
   `--ubatch-size 256` before reverting to one slot.
7. **Record and merge.** Update `docs/engine-review.md` §5 with measured results,
   copy the applied entry into `serving/` (rename it from `.proposed`), put raw
   results in a new dated dir under `bench/results/`, commit, and merge to `main`
   (see `CLAUDE.md`).

## Done when

- `bonsai-2-27b` runs with 2 slots via llama-swap, with measured VRAM and tok/s
  recorded in the repo.
- pi can use it, and the checkpoint-spacing result is recorded either way.
- Anything surprising is written down under `docs/`, including questions for
  Phase B (`engine-review.md` §4).

## Known unknowns

- Does `id_slot` survive llama-swap and the OAI chat endpoint? Test it and record it.
- Whether the 1 GB headroom bar the other llama-swap entries hold to is worth `-ub 256`.
- Real agent traces for `ngram-mod`. That's Phase C, not part of this one.
