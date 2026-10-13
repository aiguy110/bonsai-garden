# W1 replay advisor grading packet

- Run ID: `m1-ngram-spec-replay-r10-dc0c818a5351/r1`
- Request kind: `done`
- Deterministically valid: true
- Case start commit: `66680271bc71954c4a9fc741dfd7a0badf023dba`
- Preserved evidence: `bench/results/2026-10-13/worker-eval/bonsai-2026-10-12/advisor_grading/packets/m1-ngram-spec-replay-r10-dc0c818a5351__r1/preserved`

## Original milestone/item context (journal and original advisor verdict excluded)

You are the research worker for bonsai-garden, running as Bonsai 2 27B (Ternary-Bonsai-2-27B, 2-bit), a local model on this machine's GPU. The project
studies a local stack built on Ternary-Bonsai-2-27B. You work one plan item at a
time, over several fresh sessions. The standing facts and the journal below are your
memory between them.

## Your environment

- The repository is your working directory (`/home/dev/garden`). Edit freely, with
  these exceptions. These paths are protected and changes to them are reverted:
  autopilot/, .github/, tools/check_site.py, evals/run.py, evals/tap.py, evals/relay.py, evals/arms/baseline.json, evals/arms/mem0.json, evals/arms/mem0-server.json, evals/mem0_server.py, serving/llama-swap.bonsai-2-27b.yaml, site/autopilot.md
- No network and no GPU. You can run Python 3, bash and pytest, but you cannot run
  llama-server, probes or evals yourself. For those, end your session with a **request**
  (below). The orchestrator runs it on the host, after a reviewer approves it.
- Host paths named in the milestone (like `~/Projects/...` or `evals/results/`) are
  not visible here. Scripts you write can use them, because requests run on the
  host with the repo root as their working directory.
- git does not work in the sandbox. The orchestrator commits your changes after
  every session, so don't commit and don't check git state.
- Put new probe scripts in `bench/`. Requests save their output under
  `bench/results/<date>/autopilot/`, and you can read it next round.
- The live inference config is the `"bonsai-2-27b"` entry. The current applied copy
  is `serving/llama-swap.bonsai-2-27b.yaml`. To change it, write a full entry file
  in the same format under `serving/candidates/` and send an `infra` request. The
  orchestrator splices it in, restarts the server under a GPU lease, health-checks
  it, and rolls back automatically if anything is worse. Never try to change it any
  other way.
- You have a long-term memory, the `mem0_memory` tool. It persists across all
  sessions of this milestone. Early in a session, search it for the current item
  (e.g. its title, or the file or error you're dealing with). When you learn
  something a later session would otherwise rediscover (how a script or log is laid
  out, a command that works, a dead end and why), add it as one short fact. The
  standing facts and the journal still win where they disagree with a memory.


## Milestone

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


## Plan

1. Inventory spec flags, mmproj compatibility and the recorded traffic
2. Convert recordings into agent and mem0 replay requests, checked against tap prompt sizes
3. Replay probe on :8089: spec off vs ≥2 n-gram settings, 1 and 2 slots busy ← current
4. Summarize, decide, and deploy via infra only if the rule is met
5. Experiment page, series and project summaries, docs

## Current item: spec-replay, round 10 of 12

**Replay probe on :8089: spec off vs ≥2 n-gram settings, 1 and 2 slots busy**

Write bench/spec_replay.py OUTDIR LABEL SAMPLING [extra server args...], with SAMPLING one of greedy|prod. Server: take the cmd block of serving/llama-swap.bonsai-2-27b.yaml verbatim, replace ${PORT} with 8089, set LLAMA_ATTN_ROT_DISABLE=1 and append the extra args, so the flags exactly match production (-np 2, --kv-unified, --mmproj, q4_0 KV). If the server exits or logs that speculation is disabled because of mmproj, record that in OUTDIR/LABEL/notes.txt, then rerun that config with --mmproj/--no-mmproj-offload removed, labelled '<LABEL>-nommproj' (and the off config likewise for a fair baseline). Phases, each on a FRESH server start, because the n-gram pool persists across requests and replaying identical requests would inflate acceptance: single-agent (agent.jsonl in order on id_slot 0, slot 1 idle); single-mem (mem.jsonl on id_slot 1); dual-agent (agent.jsonl foreground on slot 0, while a background thread loops mem.jsonl on slot 1 until the foreground finishes); dual-mem (mem foreground on slot 1, agent loop in background on slot 0). Sampling: greedy = temperature 0, top_k 1, seed 0 for both roles; prod = agent temperature 1.0, top_p 0.95, top_k 20, seed 0, and mem temperature 0.2, seed 0. Use max_tokens 768 for agent and 1024 for mem, non-streaming. Write OUTDIR/LABEL-SAMPLING/requests.jsonl (committed) with one line per request: phase, role, fg|bg, id, slot, prompt_n, cache_n, predicted_n, predicted_ms, predicted_per_second, draft_n, draft_n_accepted, finish_reason, tool_call_json_valid (bool), out_sha256 over reasoning_content+content+tool_calls. Full output texts go to bench/.replay/m1/outputs/LABEL-SAMPLING.jsonl (gitignored). Also record vram.txt (nvidia-smi after the first request of each phase) and keep the server logs. Submit one `run` request per (config, sampling) under a turnstile lease, in this order: off/greedy; A/greedy where A = `--spec-type ngram-mod` with defaults; B/greedy where B is a second setting chosen from spec_flags.txt (another ngram type, or ngram-mod with a different draft size), with the choice justified in bench/m1-notes.md; then prod sampling for off and for whichever of A/B had the higher dual-agent greedy decode tok/s.

**Acceptance:** bench/spec_replay.py is committed. bench/results/*/m1-ngram/ has requests.jsonl, vram.txt and server logs for off-greedy, A-greedy, B-greedy, off-prod and best-prod, each with all 4 phases present. Every foreground request in the A/B runs has draft_n and draft_n_accepted fields. For any config where draft_n is 0 across all requests, notes.txt explains why (e.g. mmproj refusal), with the server log line quoted. The mmproj outcome is stated in bench/m1-notes.md.

## Bonsai request

```json
{
  "report": "Verified the completed M1 spec-replay item and confirmed every acceptance criterion is met.\n\nMeasured on private :8089 (production command, port swapped, 4 fresh-server phases each: single-agent, single-mem, dual-agent, dual-mem):\n- bench/spec_replay.py present and committed.\n- bench/results/2026-10-12/m1-ngram/replay/ holds off-greedy, A-greedy, B-greedy, off-prod, A-prod (best-prod). Each dir has requests.jsonl, vram.txt, 4 server logs, and all 4 phases (scripted check: all OK).\n- A/B foreground rows (84 each) all carry draft_n and draft_n_accepted.\n- draft_n=0 across all requests occurs only in the off configs; I added a clarifying line to off-greedy/notes.txt and off-prod/notes.txt explaining 0 drafts are expected (speculation off by design) and that the A/B runs prove --mmproj does not block n-gram speculation.\n- mmproj outcome stated in bench/m1-notes.md: \u00a73 (source-cited verdict) + final section \u2014 text-only spec works with --mmproj loaded (same VRAM ~9507-9508 MiB), image-batch spec unsupported.\n\nDecision: DO NOT DEPLOY. Default ngram-mod regressed both busy two-slot roles (agent fg 26.7 vs off 31.3 tok/s; mem fg 23.4 vs off 25.4 tok/s) and changed outputs. Live bonsai-2-27b entry left unchanged.\n\nDocs: experiment page site/series/serving/ngram-self-speculation.md, updated series site/series/serving/index.md and project site/index.md. Site metadata (required fields, <=200-word summaries, series presence, single project page, no stale parent updated) verified by hand against all tools/check_site.py rules; the PyYAML-dependent script cannot execute in this sandbox (no yaml module, and tools/ is outside the bench/evals run path and is protected).",
  "request": "done",
  "summary": "All 3 \"Done when\" criteria met. (1) Real agent + mem0 replays measured on :8089 with speculation off vs 2 n-gram settings (A default ngram-mod, B short-draft ngram-mod), 1 and 2 slots busy \u2014 decode tok/s, draft acceptance, and temp-0 output identity are in bench/results/2026-10-12/m1-ngram/replay/*/requests.jsonl and bench/m1-notes.md. (2) Decision: no-deploy, documented in site/index.md, site/series/serving/index.md, site/series/serving/ngram-self-speculation.md, bench/m1-notes.md; live entry unchanged. (3) Experiment page site/series/serving/ngram-self-speculation.md plus updated series (site/series/serving/index.md) and project (site/index.md) summaries; site metadata manually verified against every tools/check_site.py rule (PyYAML unavailable in sandbox)."
}
```

## Kind-specific review instruction

The worker says this item is done. Check its acceptance criteria against the files in the repo (read them). Approve only if met and the numbers are real (traceable to results files).

## Autopilot review gate template

```text
You are the research advisor for bonsai-garden, reviewing work by the worker
model ({worker}). The repo is your working directory, and you can read any file
in it. Be strict about correctness and honesty, and pragmatic about style.

## Milestone

{milestone}

## Item {item_id}

{item}

## What to review: {kind}

{subject}

## Diff of this item so far (may be truncated)

```diff
{diff}
```

## Standing facts

{facts}

## Journal tail

{journal}

## Your job

{instructions}

End with one fenced `json` block:

```json
{{"verdict": "approve" | "revise" | "reject", "notes": "specific, actionable feedback for the worker",
  "facts": ["optional: a correction or caveat later items must not forget"]}}
```

`facts` go into the standing facts, which every later worker and advisor prompt
includes in full. Use them sparingly, for things that are true beyond this request:
a wrong claim in a notes file, a constraint of the hardware or code, a caveat on
an accepted result. One sentence each, with a file or line reference.

```

## Replay-worktree diff

```diff
diff --git a/bench/results/2026-10-12/m1-ngram/replay/off-greedy/notes.txt b/bench/results/2026-10-12/m1-ngram/replay/off-greedy/notes.txt
index 1268a47..91659f7 100644
--- a/bench/results/2026-10-12/m1-ngram/replay/off-greedy/notes.txt
+++ b/bench/results/2026-10-12/m1-ngram/replay/off-greedy/notes.txt
@@ -1,2 +1,3 @@
 cmd: /home/josiah/Projects/llama.cpp-bonsai2/build/bin/llama-server --model /home/josiah/models/Ternary-Bonsai-2-27B-PQ2_0.gguf --mmproj /home/josiah/models/Ternary-Bonsai-2-27B-mmproj-Q8_0.gguf --no-mmproj-offload --port 8089 --n-gpu-layers 99 --ctx-size 98304 --parallel 2 --kv-unified --threads 8 --flash-attn on --cache-type-k q4_0 --cache-type-v q4_0 --kv-mean-center /home/josiah/models/Ternary-Bonsai-2-27B-PQ2_0-kv-bias.gguf --temp 1.0 --top-p 0.95 --top-k 20 --jinja
+spec: off by design (no --spec-type). draft_n=0 on every row is expected, not a failure. The A/B runs with this identical command plus --spec-type ngram-mod did draft tokens on the same production-equivalent server, so --mmproj did not block n-gram speculation.
 done
diff --git a/bench/results/2026-10-12/m1-ngram/replay/off-prod/notes.txt b/bench/results/2026-10-12/m1-ngram/replay/off-prod/notes.txt
index 3194612..515b335 100644
--- a/bench/results/2026-10-12/m1-ngram/replay/off-prod/notes.txt
+++ b/bench/results/2026-10-12/m1-ngram/replay/off-prod/notes.txt
@@ -1,4 +1,5 @@
 cmd: /home/josiah/Projects/llama.cpp-bonsai2/build/bin/llama-server --model /home/josiah/models/Ternary-Bonsai-2-27B-PQ2_0.gguf --mmproj /home/josiah/models/Ternary-Bonsai-2-27B-mmproj-Q8_0.gguf --no-mmproj-offload --port 8089 --n-gpu-layers 99 --ctx-size 98304 --parallel 2 --kv-unified --threads 8 --flash-attn on --cache-type-k q4_0 --cache-type-v q4_0 --kv-mean-center /home/josiah/models/Ternary-Bonsai-2-27B-PQ2_0-kv-bias.gguf --temp 1.0 --top-p 0.95 --top-k 20 --jinja
+spec: off by design (no --spec-type). draft_n=0 on every row is expected, not a failure. The A/B runs with this identical command plus --spec-type ngram-mod did draft tokens on the same production-equivalent server, so --mmproj did not block n-gram speculation.
 [single-agent] fg wall_s=331.9
 [single-agent] window t0=1791815749.863 t_fg_end=1791816081.800 t_join_end=1791816081.800
 [single-mem] fg wall_s=39.6

```

## Preserved evidence

The preserved directory contains replay artifacts, with `record.json` redacted to remove the original cloud-worker advisor verdict, plus `replay_state/`: the complete tracked replay worktree after applying the diff to the start commit, including unchanged files. `requested/` contains the exact host script named by a run request. State inventory and file hashes are recorded in `sample_manifest.json`.
