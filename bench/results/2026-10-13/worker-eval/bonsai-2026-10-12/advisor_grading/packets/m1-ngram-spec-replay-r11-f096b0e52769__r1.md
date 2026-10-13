# W1 replay advisor grading packet

- Run ID: `m1-ngram-spec-replay-r11-f096b0e52769/r1`
- Request kind: `done`
- Deterministically valid: true
- Replay artifact: `bench/results/2026-10-13/worker-eval/bonsai-2026-10-12/m1-ngram-spec-replay-r11-f096b0e52769/r1`
- Case start commit: `a19472b61e0876baaf63bffe90fdf781fe04b2e2`

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

## Current item: spec-replay, round 11 of 12

**Replay probe on :8089: spec off vs ≥2 n-gram settings, 1 and 2 slots busy**

Write bench/spec_replay.py OUTDIR LABEL SAMPLING [extra server args...], with SAMPLING one of greedy|prod. Server: take the cmd block of serving/llama-swap.bonsai-2-27b.yaml verbatim, replace ${PORT} with 8089, set LLAMA_ATTN_ROT_DISABLE=1 and append the extra args, so the flags exactly match production (-np 2, --kv-unified, --mmproj, q4_0 KV). If the server exits or logs that speculation is disabled because of mmproj, record that in OUTDIR/LABEL/notes.txt, then rerun that config with --mmproj/--no-mmproj-offload removed, labelled '<LABEL>-nommproj' (and the off config likewise for a fair baseline). Phases, each on a FRESH server start, because the n-gram pool persists across requests and replaying identical requests would inflate acceptance: single-agent (agent.jsonl in order on id_slot 0, slot 1 idle); single-mem (mem.jsonl on id_slot 1); dual-agent (agent.jsonl foreground on slot 0, while a background thread loops mem.jsonl on slot 1 until the foreground finishes); dual-mem (mem foreground on slot 1, agent loop in background on slot 0). Sampling: greedy = temperature 0, top_k 1, seed 0 for both roles; prod = agent temperature 1.0, top_p 0.95, top_k 20, seed 0, and mem temperature 0.2, seed 0. Use max_tokens 768 for agent and 1024 for mem, non-streaming. Write OUTDIR/LABEL-SAMPLING/requests.jsonl (committed) with one line per request: phase, role, fg|bg, id, slot, prompt_n, cache_n, predicted_n, predicted_ms, predicted_per_second, draft_n, draft_n_accepted, finish_reason, tool_call_json_valid (bool), out_sha256 over reasoning_content+content+tool_calls. Full output texts go to bench/.replay/m1/outputs/LABEL-SAMPLING.jsonl (gitignored). Also record vram.txt (nvidia-smi after the first request of each phase) and keep the server logs. Submit one `run` request per (config, sampling) under a turnstile lease, in this order: off/greedy; A/greedy where A = `--spec-type ngram-mod` with defaults; B/greedy where B is a second setting chosen from spec_flags.txt (another ngram type, or ngram-mod with a different draft size), with the choice justified in bench/m1-notes.md; then prod sampling for off and for whichever of A/B had the higher dual-agent greedy decode tok/s.

**Acceptance:** bench/spec_replay.py is committed. bench/results/*/m1-ngram/ has requests.jsonl, vram.txt and server logs for off-greedy, A-greedy, B-greedy, off-prod and best-prod, each with all 4 phases present. Every foreground request in the A/B runs has draft_n and draft_n_accepted fields. For any config where draft_n is 0 across all requests, notes.txt explains why (e.g. mmproj refusal), with the server log line quoted. The mmproj outcome is stated in bench/m1-notes.md.

## Bonsai request

```json
{
  "report": "Applied the advisor's three revision requests. (1) bench/m1-notes.md \u00a77: mem0-r0 step0 agent requests corrected 11\u219210, cross-checked against bench/results/2026-10-12/m1-ngram/recon/inventory.json (10 agent taps; sums prompt_n=36127/cache_n=30196/predicted_n=6654 unchanged). (2) bench/m1-notes.md \u00a71: per-type ngram descriptions re-attributed \u2014 help.txt lists only value names (line 369) and per-flag help (lines 374\u2013405); the one-liners are now labeled inferences from flag names + docs/engine-review.md. (3) B's server warning \"ngram_mod n_match=12 is too small - poor quality is possible\" disclosed in bench/m1-notes.md \u00a79 (all four B server logs emit it, quoted with PR link) and on the experiment page site/series/serving/ngram-self-speculation.md. No rerun needed; measurement artifacts untouched.",
  "request": "done",
  "summary": "M1 complete with advisor revisions applied. (1) Real-traffic replay measured in bench/spec_replay.py on :8089: spec off vs ngram-mod (A defaults, B short drafts), 4 fresh-server phases (single-agent, single-mem, dual-agent, dual-mem), greedy + production sampling \u2014 results in bench/results/2026-10-12/m1-ngram/replay/{off-greedy,A-greedy,B-greedy,off-prod,A-prod}/, each with 4 phases, requests.jsonl (decode tok/s, draft_n/draft_n_accepted, out_sha256, t_end), vram.txt, per-phase server logs; combined rates analyzed via bench/spec_analyze.py as conservative completed-output throughput. (2) Decision: no-deploy \u2014 A slower on both production two-slot foreground roles (agent 26.7 vs 31.3; mem 23.4 vs 25.4) and B worse (dual 23.0/22.4); live bonsai-2-27b entry unchanged. (3) Docs: site/series/serving/ngram-self-speculation.md (with B warning disclosure), site/series/serving/index.md, site/index.md, docs/engine-review.md updated. Advisor revisions: \u00a77 count fixed (bench/m1-notes.md:322), \u00a71 attribution corrected, B's \"n_match=12 too small\" warning disclosed in bench/m1-notes.md \u00a79 and the experiment page."
}
```

## Kind-specific review instruction

The worker says this item is done. Check its acceptance criteria against the files in the repo (read them). Approve only if met and the numbers are real (traceable to results files).

## Replay-worktree diff

```diff
diff --git a/bench/m1-notes.md b/bench/m1-notes.md
index 1460f1f..a68071d 100644
--- a/bench/m1-notes.md
+++ b/bench/m1-notes.md
@@ -28,7 +28,10 @@ Files: `help.txt` (57 KB), `spec_flags.txt` (8.6 KB),
 
 The **default is `none`** (no speculation). The **ngram family** is what M1
 targets (self-speculation over n-grams of the current prompt, no separate
-draft weights):
+draft weights). `help.txt` (line 369) lists only the value names and the per-flag
+help for the ngram knobs (lines 374--405); it provides no per-type
+ descriptions. The one-liners below are inferences from the flag names and
+`docs/engine-review.md`, not from `help.txt`:
 
 - `ngram-simple` — self-speculation over simple n-gram matches.
 - `ngram-map-k`, `ngram-map-k4v` — n-gram map variants (k=1 vs k=4v).
@@ -316,7 +319,7 @@ are omitted; index row counts are `-1` and omitted.)
   `timings.draft_n` / `timings.draft_n_accepted`; both are **absent** from
   these recordings (the live entry has no `--spec-*` flags, §1).
 - Example (mem0-r0):
-  - step0 — agent: (11 reqs, prompt_n=36127, cache_n=30196, predicted_n=6654);
+  - step0 — agent: (10 reqs, prompt_n=36127, cache_n=30196, predicted_n=6654);
     mem: (7 reqs, prompt_n=36181, cache_n=24464, predicted_n=419)
   - step1 — agent: (11, 3021, 90003, 8627); mem: (1, 8874, 0, 289)
   - step2 — agent: (14, 2645, 75700, 3691); mem: (1, 9183, 0, 2048)
@@ -357,7 +360,11 @@ B = ngram-mod with `--spec-ngram-mod-n-min 8 --spec-ngram-mod-n-max 16 --spec-ng
 same algorithm, shorter lookup and much shorter drafts, to cut the cost of rejected drafts
 when both slots share the GPU, and to start drafting on shorter repeats. I keep one type
 so the difference from A is only the draft-size knobs. (ngram-map-k/simple were not
-chosen: their 12/48 defaults have the same long-draft cost.) Not yet measured.
+chosen: their 12/48 defaults have the same long-draft cost.) All four B server
+logs warn `ngram_mod n_match=12 is too small - poor quality is possible, see:
+https://github.com/ggml-org/llama.cpp/pull/19164`, a direct consequence of the short
+`n_match=12`. B is measured in §9b/§9c; it does not beat off in the two-slot
+phases.
 
 ### 9b. Corrected greedy summary, off vs A vs B (round 4)
 
diff --git a/site/series/serving/ngram-self-speculation.md b/site/series/serving/ngram-self-speculation.md
index 163830e..144bbc5 100644
--- a/site/series/serving/ngram-self-speculation.md
+++ b/site/series/serving/ngram-self-speculation.md
@@ -36,8 +36,9 @@ Agent requests use slot 0; memory requests use slot 1.
 
 `ngram-mod` with its default 48--64-token drafts was candidate A. Candidate B
 used 8--16-token drafts, to test whether shorter rejected drafts help when the
-slots compete for the GPU. At greedy sampling, neither candidate beat the
-no-speculation arm in the two-slot phases:
+slots compete for the GPU. Every B server log warns `ngram_mod n_match=12 is
+too small - poor quality is possible`. At greedy sampling, neither candidate
+beat the no-speculation arm in the two-slot phases:
 
 | foreground decode tok/s | off | A: default mod | B: short mod |
 |---|---:|---:|---:|

```

## Preserved evidence

`preserved/` contains copied request.json (where recovered), final.txt, workspace.diff, record.json, and manifest.json.
