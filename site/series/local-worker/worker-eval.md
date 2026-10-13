---
layer: experiment
series: local-worker
title: "W1: replaying real autopilot rounds on Bonsai"
status: done
date: 2026-10-13
updated: 2026-10-13
tldr: In 44 replays of 22 cloud-worker rounds, Bonsai made 25 valid requests (56.8%) and matched request kind 21 times (47.7%).
summary: |
  **Question:** could the local Bonsai worker do the autopilot's own research
  rounds? **Method:** select 22 provenance-checked, non-rate-limited cloud-worker
  rounds from four M1 plan items, replay each prompt and start commit twice in a
  fresh sandbox, and apply the orchestrator's request checks. The arm recreates
  the 2026-10-12 Bonsai worker with memory off and a 20-minute limit.

  **Result:** 25/44 attempts (56.8%) submitted a valid request; 21/44 (47.7%)
  matched the cloud request kind (21/25, 84.0%, among valid requests). Median
  wall time was 903.5 s. Flags were timeout 17/44, context overflow 3/44, and
  output limit 2/44; flags overlap. A deterministic sample of 10 valid requests
  received 7 approve, 3 revise, 0 reject from the advisor. This small judged
  sample is separate from the deterministic rates. W2 targets the observed
  context, tool, editing, and session failures; it does not yet establish whether
  Bonsai can replace the cloud worker.
---

## Question and evidence

W1 asks whether Bonsai can perform the guarded research-worker rounds that the
autopilot currently delegates to a cloud model. The committed [case
set](https://github.com/aiguy110/bonsai-garden/blob/main/bench/worker_eval/cases.jsonl)
and its [inventory](https://github.com/aiguy110/bonsai-garden/blob/main/bench/worker_eval/inventory.json)
are the input evidence. The deterministic output is
[`summary.json`](https://github.com/aiguy110/bonsai-garden/blob/main/bench/results/2026-10-13/worker-eval/bonsai-2026-10-12/summary.json);
the separately judged output is
[`advisor_grades.jsonl`](https://github.com/aiguy110/bonsai-garden/blob/main/bench/results/2026-10-13/worker-eval/bonsai-2026-10-12/advisor_grading/advisor_grades.jsonl).

## Corpus and replay

The corpus contains 22 M1 cloud-worker rounds whose matched worker journal entry
is at or after 2026-10-12 08:33 -04:00. Every row preserves the exact start
commit, original first user prompt, recovered worker request, and matched advisor
verdict; replay changes only the prompt's worker-model description. It includes
11 Claude Sonnet 5.5 and 11 GPT-5.6 Terra rounds, across `replay-set` (7),
`spec-replay` (10), `decide` (3), and `write-up` (2). Fourteen cloud requests are
`run`, eight are `done`; 15 source verdicts approve and seven revise. Keeping
`revise` cases avoids selecting only cloud rounds that the advisor liked.

The builder excluded 24 pre-cutoff logs, one pre-cutoff/Bonsai entry, eight
rate-limited rounds, two logs without a matched journal worker entry, and two
unreviewed `continue` requests. It also requires a recoverable request, a
kind-matched advisor verdict, and an unambiguous recent before-round commit.
Those criteria, hashes, and the time-window association are documented in
[`bench/worker_eval/README.md`](https://github.com/aiguy110/bonsai-garden/blob/main/bench/worker_eval/README.md).

Each case ran twice (44 completed attempts) in a fresh checkout of its start
commit, in the replay sandbox, against the live Bonsai through the benchmark
turnstile key. The arm was `bonsai-2026-10-12`: `garden/bonsai-agent`, low
thinking, 16,384 maximum output tokens, 81,920-token context, 28,672-token
compaction reserve, worker memory off, and only
`autopilot/extensions/submit_request.ts`; it enforced a 20-minute session timeout.
The historical worker had a 45-minute setting, so the retained prompt wording says
45 minutes even though the replay timeout is 20. The exact executed arm is committed in
[`arms/bonsai-2026-10-12.json`](https://github.com/aiguy110/bonsai-garden/blob/main/bench/worker_eval/arms/bonsai-2026-10-12.json).

## Deterministic results

A valid request means the replay recovered a request and the orchestrator's
per-kind checks accepted it. “Kind match” compares that request's kind with the
cloud worker's kind. The first rate uses all attempts; the conditional rate uses
valid requests only.

| scope | attempts | valid requests | kind matches / all | kind matches / valid | median wall s | median turns |
|---|---:|---:|---:|---:|---:|---:|
| pooled | 44 | 25 (56.8%) | 21 (47.7%) | 21 (84.0%) | 903.5 | 16.5 |

| case | attempts | valid | kind match / all | median wall s |
|---|---:|---:|---:|---:|
| replay-set r6 | 2 | 0 (0.0%) | 0 (0.0%) | 1200.35 |
| replay-set r7 | 2 | 0 (0.0%) | 0 (0.0%) | 1200.45 |
| replay-set r8 | 2 | 0 (0.0%) | 0 (0.0%) | 1200.4 |
| replay-set r9 | 2 | 0 (0.0%) | 0 (0.0%) | 669.05 |
| replay-set r10 | 2 | 1 (50.0%) | 1 (50.0%) | 1022.2 |
| replay-set r11 | 2 | 1 (50.0%) | 0 (0.0%) | 1110.95 |
| replay-set r12 | 2 | 2 (100.0%) | 2 (100.0%) | 425.25 |
| spec-replay r1 | 2 | 0 (0.0%) | 0 (0.0%) | 1200.3 |
| spec-replay r2 | 2 | 2 (100.0%) | 2 (100.0%) | 771.9 |
| spec-replay r3 | 2 | 2 (100.0%) | 2 (100.0%) | 1043.5 |
| spec-replay r4 | 2 | 1 (50.0%) | 1 (50.0%) | 1155.25 |
| spec-replay r5 (144aca) | 2 | 2 (100.0%) | 2 (100.0%) | 179.5 |
| spec-replay r5 (5c5d98) | 2 | 2 (100.0%) | 2 (100.0%) | 197.6 |
| spec-replay r6 | 2 | 2 (100.0%) | 2 (100.0%) | 228.9 |
| spec-replay r7 | 2 | 2 (100.0%) | 2 (100.0%) | 397.6 |
| spec-replay r10 | 2 | 2 (100.0%) | 2 (100.0%) | 555.6 |
| spec-replay r11 | 2 | 2 (100.0%) | 2 (100.0%) | 367.75 |
| decide r1 | 2 | 0 (0.0%) | 0 (0.0%) | 1200.5 |
| decide r2 | 2 | 0 (0.0%) | 0 (0.0%) | 1131.9 |
| decide r3 | 2 | 2 (100.0%) | 1 (50.0%) | 661.75 |
| write-up r2 | 2 | 0 (0.0%) | 0 (0.0%) | 1200.5 |
| write-up r3 | 2 | 2 (100.0%) | 0 (0.0%) | 524.4 |

The abbreviated case labels map uniquely to the full IDs in the linked summary.
The full per-case table, including conditional kind-match rate and median turns,
is in [`summary.md`](https://github.com/aiguy110/bonsai-garden/blob/main/bench/results/2026-10-13/worker-eval/bonsai-2026-10-12/summary.md).

## Failure modes

All denominators below are 44 attempts. Flags are event-level and overlap: in
particular, a context-overflow flag can occur in an attempt that later sends a
valid request. They are not a partition of failed attempts.

| outcome or flag | count | denominator |
|---|---:|---:|
| valid requests | 25 | 44 |
| failed attempts | 19 | 44 |
| no request | 18 | 44 |
| invalid request | 1 | 44 |
| timeout flag | 17 | 44 |
| context-overflow flag | 3 | 44 |
| output-limit flag | 2 | 44 |
| rate-limit flag | 0 | 44 |
| nonzero pi exit flag | 0 | 44 |
| unclassified no-request failure | 1 | 44 |
| unclassified invalid-request failure | 1 | 44 |

Per-case flags have the same overlapping semantics and a denominator of two
attempts per row. Full IDs and all other per-case measures are in the linked
summary.

| case | timeout | context overflow | output limit |
|---|---:|---:|---:|
| replay-set r6 | 2 | 1 | 0 |
| replay-set r7 | 2 | 0 | 0 |
| replay-set r8 | 2 | 0 | 0 |
| replay-set r9 | 1 | 0 | 0 |
| replay-set r10 | 1 | 2 | 0 |
| replay-set r11 | 1 | 0 | 0 |
| replay-set r12 | 0 | 0 | 0 |
| spec-replay r1 | 2 | 0 | 1 |
| spec-replay r2 | 0 | 0 | 0 |
| spec-replay r3 | 0 | 0 | 0 |
| spec-replay r4 | 1 | 0 | 0 |
| spec-replay r5 (144aca) | 0 | 0 | 0 |
| spec-replay r5 (5c5d98) | 0 | 0 | 0 |
| spec-replay r6 | 0 | 0 | 0 |
| spec-replay r7 | 0 | 0 | 0 |
| spec-replay r10 | 0 | 0 | 0 |
| spec-replay r11 | 0 | 0 | 0 |
| decide r1 | 2 | 0 | 1 |
| decide r2 | 1 | 0 | 0 |
| decide r3 | 0 | 0 | 0 |
| write-up r2 | 2 | 0 | 0 |
| write-up r3 | 0 | 0 | 0 |

The 44 attempts made 1,121 tool calls: 712 `bash`, 309 `read`, 59 `edit`, 30
`submit_request`, and 11 `write`; 99 tool errors were recorded (74 bash, 18 edit,
one read, four submit-request, two write). Compaction events within attempts: 32 started and 29 ended
(`compaction_start` / `compaction_end` counts in `summary.json`). These counts describe this arm and corpus, not a
causal attribution.

## Advisor sample

After deterministic checking, a fixed stratified sample of 10 valid attempts (five
`run`, five `done`, no valid `infra`) was graded with the autopilot review prompt
by `openai-codex/gpt-5.6-sol`. It received **7 approve, 3 revise, 0 reject**
(7/10 approve, 70.0%). The response was independently transcription-verified.
This is a small, selected judged sample—not a deterministic success rate and not
evidence that the remaining valid requests would be approved. The sample manifest,
packets, verbatim responses, and grades are in the linked
[`advisor_grading/`](https://github.com/aiguy110/bonsai-garden/tree/main/bench/results/2026-10-13/worker-eval/bonsai-2026-10-12/advisor_grading) directory.

## What W2 should test

Measured evidence motivates, but does not prove causes for, five priorities:

1. **Thinking/history retention and output budget.** Three context-overflow flags
   and two output-limit flags make retaining less old thinking/history and spending
   freed context on output a direct W2 candidate.
2. **Tool-output caps.** Long tool output is a plausible contributor to prompt
   pressure in an 81,920-token window; W2 should test smaller, navigable caps. This
   is a hypothesis, not a causal result from W1.
3. **Editing and tool errors.** Eighteen edit errors and 74 bash errors warrant a
   safer edit mechanism and clearer tool guidance; error counts alone do not say
   which change will help.
4. **Session discipline.** Seventeen timeout flags and 18 absent requests support
   testing warnings and a request-first end-of-session policy. The 20-minute
   enforced replay limit is also a fidelity difference from the historical
   45-minute prompt wording.
5. **Compaction.** The arm logged 32 starts and 29 ends, so reserve and summary
   retention deserve controlled variants. W1 does not isolate compaction as the
   cause of any failure.

## Caveats

This is a replay, not an online replacement trial. Its real Git checkout exposes
history that the original autopilot sandbox could not use; this can only change
behavior relative to the source round. All five run manifests record `repo_dirty:
true`, a provenance caveat. The executed arm's embedded historical SHA-256 values
came from an earlier inspector that hashed stripped `git show` text rather than raw
blobs, so they must not be treated as byte hashes; its memory source also says the
historical config explicitly set `worker_memory: null`, whereas the key was absent
and memory was disabled through `CFG.get()`. The arm is preserved because it is the
one executed; raw-byte provenance has not yet been rerun. The corpus is M1-only and
contains 22 selected rounds, not the full future workload. The summary recomputes
result-level metrics but does not independently reparse every event file for failure
flags. Finally, deterministic request acceptance and the 10-request advisor sample
measure different things; neither supports a blanket claim that Bonsai can or cannot
replace the cloud worker.
