# W1: worker eval

## Question

Could Bonsai do the autopilot's own research work? Build a benchmark out of real
autopilot rounds and measure Bonsai on it, so every later change to the local worker
harness (W2–W4) has a number to move.

## What is already known

- Bonsai was the worker until 2026-10-12. Of 21 M1 rounds, 11 sent no request. The
  failure modes, from the journal and `autopilot/.runtime/calls/` on the host:
  - session timeout at 45 min;
  - `context_length_exceeded` after one large tool output (80k window, compaction
    reserve 28672);
  - the reply cut off at the 16k output limit, once entirely inside thinking;
  - 60–80 tool calls per round, mostly bash. Compaction ran 1–4 times per round.
- From 2026-10-12 08:33 the worker was `meridian/claude-sonnet-5-5`. Its rounds took
  1–3 minutes and 4–13 tool calls, and every one ended with a valid request. From
  10:30 it is `openai-codex/gpt-5.6-terra`. Rounds that failed at a rate limit
  (M1 `spec-replay` rounds 5–12) are not cases.
- Every round leaves a commit `autopilot(<m>): before <item> round <n>` on branch
  `auto/<m>`: the repo state the worker started from. The worker's full event log
  is `autopilot/.runtime/calls/<stamp>-worker-<item>-r<n>.jsonl` in the main
  checkout (host path `~/Projects/bonsai-garden/autopilot/.runtime/calls/`). Its
  first user message is the exact prompt. The journal on `auto/<m>` holds the
  request the worker sent and the advisor's verdict on it.
- `bench/m1-notes.md` (on `auto/M1-ngram`, merged with M1): recorded agent prompts
  appear to include all earlier thinking of the session, so prompt size grows by
  about the tokens generated. That is inferred from token counts, not confirmed in
  pi's source.

## Material

- `autopilot/autopilot.py`: `call_worker`, `worker_agent_dir` and the request checks
  (`check_run_command` and the per-kind rules). A replay script may import it
  read-only to reuse the sandbox, the tap and the request checks. It must not
  change files under `autopilot/`.
- `autopilot/extensions/submit_request.ts`: how a session ends.
- `evals/run.py`: the sandbox, tap and event parsing (`parse_events`).

## Done when

1. A case set of at least 20 cloud worker rounds (from 2026-10-12 08:33 on), in
   `bench/worker_eval/cases.jsonl`. Each case has: the start commit, the exact
   prompt (with the line naming the worker model replaced by the replayed model's),
   the request the cloud worker sent, and the advisor verdict. Rounds with a `revise` verdict
   stay in the set, marked as such. Cover at least two different plan items.
2. A worker-arm format (`bench/worker_eval/arms/<name>.json`): model, thinking
   level, max output tokens, compaction reserve, session timeout, worker memory, and
   extra extensions. One arm, `bonsai-2026-10-12`, reproduces the Bonsai worker as it
   ran on 2026-10-12, but with worker memory off (memory is W3) and a 20-minute
   session timeout.
3. `bench/worker_eval/run.py ARM [--cases ...] [--repeat N]` replays cases in the
   sandbox, each in a fresh checkout of its start commit outside the milestone
   worktree, against the live Bonsai through turnstile (bench key). It is
   resumable and runs in chunks that fit one `run` request (≤150 min). Per case it
   records: request sent (via the tool, the JSON fallback, or none), whether the
   orchestrator's checks accept it, whether its kind matches the cloud worker's, wall time,
   turns, tool calls by tool, tool errors, compactions, the stop reason of the last
   reply, and errors (timeout, context overflow, output limit).
4. `bonsai-2026-10-12` run on every case at N=2. Report the valid-request rate,
   kind-match rate, median time and the failure-mode breakdown, per case and pooled.
5. Advisor grading on a sample of at most 10 Bonsai requests that passed the checks,
   using `autopilot/prompts/review.md`: would it approve them? Report it separately
   from the deterministic numbers.
6. An experiment page for the local-worker series (`site/AUTHORING.md`), with the
   failure modes and what they point to for W2.
