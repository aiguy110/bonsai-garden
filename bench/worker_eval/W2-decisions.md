# W2 decisions (fixed before any arm runs)

Sources: `bench/results/2026-10-13/worker-eval/bonsai-2026-10-12/trace_analysis.json` (TA),
`bench/results/2026-10-13/worker-eval-w2/recon/` (pi.txt, llama.txt, drift.json, packages/),
`bench/results/2026-10-13/worker-eval-w2/reasoning-probe/result.json` (probe).
pi paths below are relative to `@earendil-works/pi-coding-agent` 0.86.1 (`pi.txt` has the full paths).
W1 arm settings: context 81920, reserveTokens 28672, max output 16384, thinking low
(`arms/bonsai-2026-10-12.json`).

## Drift and baseline rerun
`drift.json`: drift = **false** (model sha256 3907dc16…, llama-swap entry, pi 0.86.1, sandbox image and
turnstile commit all equal the five W1 manifests). **No baseline rerun.** Informational only: llama-server
is build `9a9394a` (0.2.0-dev).

## 0. Corrected baseline: `bonsai-2026-10-12-honest`
Identical to the W1 arm plus an arm field `prompt_timeout_min: 20` that rewrites the "45 minutes" sentence
of the replayed prompt to the arm's real limit. The harness must report whether anything else in the prompt
changes (it must not). Compared with the W1 arm for the first comparison; every later arm is compared with
this one. Always runs.

## 1a. Think-drop (`w2-think-drop`)
- Mechanism: pi-ai serialises earlier thinking back as `reasoning_content`
  (pi-ai `dist/api/openai-completions.js:971-1001`, `:1043-1045`), and the extension event `context`
  receives and may return a rewritten message list before each model request
  (`dist/core/extensions/runner.js:833-847`; `types.d.ts:924`); `before_provider_request` can replace the
  payload (`runner.js:859-876`; `types.d.ts:926`).
- Fixed value: in the outgoing request only, remove thinking blocks from every assistant message except the
  last **K=2**. The session file keeps them.
- Gate: TA thinking_resent: 643 of 654 discriminating pairs (98.3%) fit "thinking is resent"; median
  resid/predicted_n 1.16. Confirmed. TA prompt_composition_at_pressure: at 35 compaction/overflow points,
  median estimated thinking share of the prompt 0.331 (tool output 0.279). Passes.

## 1b. Reasoning budget (`w2-reasoning-budget`)
- Mechanism: llama-server reads per-request `reasoning_budget_tokens` (alias `thinking_budget_tokens`,
  default -1 = server value) and `reasoning_budget_message`, applied only if the chat template has thinking
  end tags (llama.cpp-bonsai2 `tools/server/server-common.cpp:1354-1364`; `recon/llama.txt`'s source section
  is empty, so this is cited directly). Sent via `before_provider_request` (or the tap), so no live-config change.
- Probe (3 identical requests, max_tokens 4096, via tap/turnstile): **PASS**.
  no budget: 11699 reasoning chars, finish_reason length, answer empty (4096 tokens, 70.2 s);
  budget 256: 1127 chars (limit 1280), message present, answer "ANSWER: 8119" (283 tokens, 5.3 s);
  budget 1024: 3892 chars (limit 4352), message present, answer non-empty (1050 tokens, 18.2 s).
  Caveat: one prompt, one sample per setting; the answer 8119 is not checked for correctness (the probe
  checks the mechanism only).
- Fixed values: TA reply_tokens est_reasoning_tokens p75 = 967.1, so the smallest power of 2 ≥ 967.1 is 1024,
  within [1024, 8192]: **budget = 1024**. Message:
  `\n[Thinking budget reached. Stop thinking and act now with what you have.]\n`.

## 2. Tool-output cap (`w2-tool-cap`): GATE FAILED, no arm
Rule: run only if ≥20 W1 tool results exceed 16 KB or 400 lines, or those are ≥20% of tool-result chars.
TA tool_results: 11 results over the limit (5 bash, 6 read), 9.35% of 2,686,436 chars. Both below the
thresholds. Built-in limits for reference: 2000 lines / 50 KB (`dist/core/tools/truncate.js:10-11`).
Note the W1 results are already pi-truncated, so this is a lower bound on raw output; it does not change the
outcome under the stated rule.

## 3. Hashline editing (`w2-hashline`)
Review in `bench/worker_eval/vendor/REVIEW.md`: `pi-hashline-edit` 0.8.3 rejected (child_process/rg and
non-pi runtime deps); `pi-hashline-context-edit` 0.11.0 chosen (MIT), needing a small patch for its
`file-type` import. Whether it loads under pi 0.86.1 and whether `registerTool` may replace the built-in
`edit`/`read` are **not established by the recon** (pi.txt shows registerTool at
`dist/core/extensions/loader.js:220` but no override rule; the docs were not readable in the sandbox).
The smoke run decides; if it does not load or cannot replace the built-ins, there is no hashline arm.
Edit failures in TA edit_errors: 18 of 59 edit calls, 17 "text not found", 1 overlapping edits.
Bash errors: 74 of 712; top causes are Python tracebacks (AttributeError 12, TypeError 11), exit 1 with
output 11.

## 4. Session budget (`w2-session-budget`)
Extension on `tool_call` (can block; `types.d.ts:945`) and `tool_result`/`context` for messages. Fixed
values: warnings at **12 and 16 min** elapsed and at turns **30 and 40**, stating elapsed and remaining
minutes of the real 20-minute limit. At **17.5 min or turn 45**, block every tool except `submit_request`
with a message to call it now (`continue` with a note if unfinished).
Evidence: 17 of 44 attempts timed out (TA time_split: 20,407 of 35,291 s wall). Timeout turns p50 26, p90 42,
max 68; non-timeouts p50 14, p90 28. TA timeout_tail: 14 timeouts had a generation in flight at the kill, 3 a
compaction. A turn-45 rule would fire in few attempts; the time rule is the main lever.

## 5. Compaction (`w2-compaction`): GATE PASSED
Rule: run if compaction time ≥10% of wall, or ≥3 timeouts during or within 5 min after a compaction.
TA compactions: 29 compactions, 2408 s = 6.8% of wall (fails the first test); **10 timeouts** during or
within 5 min after one (passes the second). Runs.
Fixed value: `compaction.reserveTokens` = **16384**, nothing else changed.
What it changes (recon): pi compacts when `contextTokens > contextWindow - reserveTokens`
(`dist/core/compaction/compaction.js:162-165`). With window 81920 the W1 value 28672 triggers at 53,248
tokens; 16384 triggers at 65,536 (+12,288 tokens, about 23% more context before each compaction), so fewer
compactions per session. The summary call's max_tokens is `min(0.8*reserveTokens, model.maxTokens)`
(`compaction.js:488`): 16384 gives 13,107, down from 16,384 (the model cap; 0.8*28672 = 22,937), and it
runs with thinking on (`dist/core/agent-session.js:1568`). Cost: less headroom for one reply; the W1 max
reply was 16,384 tokens, so a reply near the cap can overflow the window (TA prompt_composition shows 3
overflow events). The pi default is also 16384 (`compaction.js:78`); `keepRecentTokens` stays 20000 (`:79`).

## 6. Output 32768
Rule: allowed in the combination only if ≥1 W1 length stop is not a loop. TA length_stops: 2 length stops,
0 loops, 2 non-loops (43,069 and 55,328 output chars, both ordinary long thinking). **Allowed in the
combination**, not as a single-factor arm. It needs window room: with a context of 81920, 32768 of output
leaves 49,152 for the prompt, so use it only together with think-drop.

## Deferred, no arm
- Smaller items: a planner change cannot be tested with fixed replays; goes to W4.
- oh-my-pi as a whole harness: deferred. The single-factor arms and the combination have not been run, so
  it is not yet known whether a gap remains, and `submit_request` under oh-my-pi is unchecked (spec
  condition).

## Queue order
1. `bonsai-2026-10-12-honest`
2. (baseline rerun of `bonsai-2026-10-12`: not queued, drift = false)
3. `w2-think-drop`
4. `w2-reasoning-budget`
5. `w2-session-budget`
6. `w2-hashline` (if the smoke run shows the patched package loads and replaces the built-ins)
7. `w2-compaction` (gate passed)
8. Combination of whatever helped (may include output 32768)
(`w2-tool-cap`: gate failed, not queued.)
