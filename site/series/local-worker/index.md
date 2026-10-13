---
layer: series
series: local-worker
order: 4
title: Local worker
status: active
updated: 2026-10-13
tldr: A 22-round replay finds Bonsai submits a valid request in 25/44 attempts; W2 tests harness changes aimed at its observed failures.
summary: |
  **Goal:** measure how much of the autopilot's research work the local Bonsai
  worker can complete, then improve that number without conflating it with the
  memory experiments.

  **Baseline:** W1 replayed 22 real cloud-worker rounds twice with the historical
  Bonsai worker configuration (memory off, 20-minute limit). Bonsai submitted a
  request accepted by deterministic checks in **25/44 attempts (56.8%)** and
  matched the cloud request kind in **21/44 (47.7%)**. The median attempt took
  **903.5 seconds**. A separately sampled advisor review approved 7/10 valid
  requests; it is a small judged sample, not a rate.

  **Next:** W2 tests thinking/history retention and output budget, smaller tool
  outputs, safer editing, session discipline, and compaction changes against this
  fixed corpus.
---

This series asks whether a local Ternary-Bonsai-2-27B worker can carry out the
same guarded research rounds currently handled by a cloud worker. It uses real
cloud-worker starting states and prompts, then evaluates local replays with the
same request checks. Worker memory is deliberately out of scope until W3.

## Experiments

- [W1: worker-eval](worker-eval.md) — fixed 22-case, N=2 baseline and failure
  analysis for the historical Bonsai worker configuration.

## Rules for comparisons

W2 and later arms retain the case corpus, fresh-checkout sandbox, deterministic
request checks, and N=2 baseline reference. A change is useful only if it improves
completion or request quality without hiding failure modes behind a different task
set. Advisor review remains separate from deterministic acceptance.
