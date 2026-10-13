# W1 replay advisor grading packet

- Run ID: `m1-ngram-replay-set-r12-e62a974c8e88/r2`
- Request kind: `done`
- Deterministically valid: true
- Replay artifact: `bench/results/2026-10-13/worker-eval/bonsai-2026-10-12/m1-ngram-replay-set-r12-e62a974c8e88/r2`
- Case start commit: `f9c13c62c0ad158e6d7547e8b9c0df84f903b770`

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
2. Convert recordings into agent and mem0 replay requests, checked against tap prompt sizes ← current
3. Replay probe on :8089: spec off vs ≥2 n-gram settings, 1 and 2 slots busy
4. Summarize, decide, and deploy via infra only if the rule is met
5. Experiment page, series and project summaries, docs

## Current item: replay-set, round 12 of 12

**Convert recordings into agent and mem0 replay requests, checked against tap prompt sizes**

Write bench/build_replay_set.py and run it via a `run` request. Output goes to bench/.replay/m1/ (add bench/.replay/ to .gitignore; recorded content stays out of git). (1) agent.jsonl: one line per recorded agent LLM request, i.e. each assistant turn. Fields: id ('<run>/<step>/<turn>'), body (OpenAI /v1/chat/completions body: messages = system prompt + full history before that turn, assistant reasoning dropped as pi does, tool_calls and tool results kept; tools = pi's tool schemas, plus mem0_memory in the mem0 arm), recorded_prompt_tokens (prompt_n+cache_n of the matching tap.jsonl record, matched by run, step, role=agent and order). Rebuild the system prompt from pi_prompt_src.txt. If that isn't possible, use a stand-in of the same length in characters, and set system_prompt_exact=false in the manifest. Choose turns from at least 4 different steps across both arms, up to 30 requests total, and prefer steps with file reads, edits and test output. (2) mem.jsonl: one line per rebuilt mem0 extraction call, up to 12, built from the mem0-arm runs. System = ADDITIVE_EXTRACTION_PROMPT verbatim. User prompt is assembled as in mem0_extract_src.txt: the existing memories come from that run's SQLite store, filtered to entries created before the call where timestamps allow; the recent and new messages are the user prompt plus the first assistant text, taken from the events. Add chat_template_kwargs {enable_thinking:false}, plus recorded_prompt_tokens from the matching tap role=mem record. Do not put sampling params in the bodies; the probe sets them. (3) Commit bench/results/<run date>/m1-ngram/replay_manifest.json. Per request it holds id, role, n_messages, prompt chars, chars/4 estimate, recorded_prompt_tokens and est/recorded ratio. It also holds totals and system_prompt_exact.

**Acceptance:** .gitignore contains bench/.replay/. replay_manifest.json is committed and lists 20–30 agent requests from ≥4 distinct steps and 6–12 mem requests (or a documented reason mem is infeasible). Every entry has recorded_prompt_tokens. The median est/recorded ratio is within 0.75–1.33 for each role, and outliers are explained in bench/m1-notes.md. The builder script is committed and runnable as `python3 bench/build_replay_set.py`.

## Bonsai request

```json
{
  "report": "Round 12 (replay-set, final): advisor asked to replace the unmeasured \"tool output\" outlier explanation in bench/m1-notes.md \u00a78 with the measured cause, notes-only. Verified all cited numbers against artifacts: inventory.json baseline-r0 step0 turn2 total=2761 (pred 8565), turn3=576, turn4=1024, turn5 total=13032 (sum generated 10165, prompt growth +10271); replay_manifest.json /0/2=8502 vs /0/5=38559 chars (+30057, tool +1935\u21922154 = +219; /0/5 chars_by_role tool=2154 vs reasoning=25717). Edited \u00a78: outlier bullet now gives the measured cause (~2.96 chars/token for reasoning/assistant text, 30057/10165, so chars/4 under-counts; tool-output hypothesis ruled out), the reasoning bullet cites the prompt-growth\u2248generated-tokens arithmetic as measured evidence reasoning is sent back, and the source-caveat bullet was updated accordingly. No builder re-run, manifest untouched, live entry untouched (no infra request).",
  "request": "done",
  "summary": "All acceptance criteria met. (1) .gitignore has bench/.replay/ (line 8). (2) bench/results/2026-10-12/m1-ngram/replay_manifest.json lists 30 agent requests over 6 distinct steps (\u22654) and 12 mem requests over 5 steps, every entry has recorded_prompt_tokens (verified), medians est/recorded: agent 0.833, mem 1.027 (both inside 0.75\u20131.33); system_prompt_exact=true. (3) The three agent outliers below 0.75 (baseline-r0/0/5 0.740, /0/8 0.743, /0/10 0.742) are explained in bench/m1-notes.md \u00a78 with the measured cause: turns 2\u20134 generated 8565+576+1024=10165 tokens, recorded prompt grows 2761\u219213032 (+10271), rebuilt body grows 8502\u219238559 chars (+30057, tool only +219), so reasoning/assistant text tokenizes at ~2.96 chars/token and chars/4 under-counts; tool-output hypothesis ruled out (tool=2154 vs reasoning=25717 at /0/5). (4) bench/build_replay_set.py is committed, runnable (host run r10 exited 0; syntax-OK here), unchanged this round. Notes-only edit per advisor; no infra change to the live entry. Next milestone item (plan 3): :8089 replay probe with spec off vs \u22652 ngram settings, 1 and 2 slots busy."
}
```

## Kind-specific review instruction

The worker says this item is done. Check its acceptance criteria against the files in the repo (read them). Approve only if met and the numbers are real (traceable to results files).

## Replay-worktree diff

```diff
diff --git a/bench/m1-notes.md b/bench/m1-notes.md
index d0b0b44..ab13222 100644
--- a/bench/m1-notes.md
+++ b/bench/m1-notes.md
@@ -329,9 +329,9 @@ are omitted; index row counts are `-1` and omitted.)
 Estimator: chars/4 over the rebuilt body, against recorded prompt_n+cache_n.
 
 - Agent: 30 requests, 6 steps, median est/recorded **0.833** (inside 0.75–1.33). Mem: 12 requests, 5 steps, median **1.027**.
-- Agent bodies keep assistant thinking as `reasoning_content` (pi's thinkingSignature). Without it the median is 0.457, so recorded prompts clearly included earlier reasoning. The probe server needs `--jinja`.
+- Agent bodies keep assistant thinking as `reasoning_content` (pi's thinkingSignature). Without it the median is 0.457. Recorded prompts include earlier reasoning in full, measured: in baseline-r0 step 0 the recorded prompt grows 2761→13032 tokens (+10271, turn 2→5), matching the 8565+576+1024=10165 tokens generated in turns 2–4 (inventory.json). The probe server needs `--jinja`.
 - The "reasoning after last user only" ratio equals the "all reasoning" ratio. Every step is a fresh session with one user message, so this says nothing about the chat template.
-- Not confirmed from source: the pi-ai `openai-completions.js` search found no file (empty list), so that pi sends `reasoning_content` back is inferred from the token counts only.
-- Outliers below 0.75: baseline-r0/0/5 (0.740), /0/8 (0.743), /0/10 (0.742). They are 1% under the bound. They are late turns of baseline-r0 step 0. Likely cause (not measured): code/JSON tool output tokenizes at under 4 chars/token, so chars/4 under-counts. Not corrected.
+- Not confirmed from source: the pi-ai `openai-completions.js` search found no file (empty list), so that pi sends `reasoning_content` back is not source-confirmed; the measured prompt-growth arithmetic in the outlier bullet (recorded prompt growth ≈ generated tokens) is the evidence for it.
+- Outliers below 0.75: baseline-r0/0/5 (0.740), /0/8 (0.743), /0/10 (0.742). They are 1% under the bound; late turns of baseline-r0 step 0. Measured cause: turns 2–4 of baseline-r0 step 0 generated 8565+576+1024=10165 tokens, and the recorded prompt grows 2761→13032 (turn 2→5, +10271); the rebuilt body grows 8502→38559 chars (turn 2→5, +30057), of which only +219 is tool. The model's own reasoning/assistant text thus tokenizes at ~2.96 chars/token (30057/10165), so chars/4 under-counts it, and late turns of a step dominated by one long reasoning output land just under 0.75. The tool-output hypothesis is ruled out by the same data: /0/5 has tool=2154 vs reasoning=25717 in chars_by_role.
 - Mem requests are all 1.02–1.04: the prompt is mostly the fixed ADDITIVE prompt, so they pass easily. They do not test the tokenizer on conversation content.
 - Replays still lack sampling params and per-request max_tokens (not recorded); the probe must set them.

```

## Preserved evidence

`preserved/` contains copied request.json (where recovered), final.txt, workspace.diff, record.json, and manifest.json.
