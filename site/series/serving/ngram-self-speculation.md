---
layer: experiment
series: serving
title: N-gram self-speculation on recorded agent traffic
status: done
date: 2026-10-12
updated: 2026-10-12
tldr: On real agent and mem0 replays, n-gram speculation did not speed the two busy slots, changed outputs, and was not deployed.
summary: |
  **Question:** can llama-server's no-extra-model n-gram speculation make the
  agent and mem0 faster on their actual traffic?

  **Method:** replayed 30 recorded agent requests and 12 reconstructed mem0
  extraction calls on a private production-equivalent two-slot server. Each of
  four phases used a fresh server: agent alone, memory alone, agent foreground
  with memory looping, and memory foreground with agent looping. We compared
  speculation off with default `ngram-mod`, plus a shorter-draft variant, under
  greedy decoding; then repeated off and the better greedy candidate with the
  production sampling settings.

  **Result:** default `ngram-mod` was equal for single-agent production traffic
  (56.0 tok/s), but slower with both slots busy: agent foreground **26.7 vs
  31.3 tok/s** and memory foreground **23.4 vs 25.4 tok/s**. It also changed
  outputs and sometimes changed whether an agent turn reached its token cap.
  **Decision:** do not deploy speculation.
---

## Replay results

The probe is [`bench/spec_replay.py`](https://github.com/aiguy110/bonsai-garden/blob/main/bench/spec_replay.py).
It uses the live server command verbatim, except for private port `8089`, and
keeps the production `--parallel 2`, unified q4_0 KV, and multimodal projector.
The traffic set contains 30 agent turns from recorded pi event streams and 12
mem0-style JSON-object extraction requests rebuilt from the extension source.
Agent requests use slot 0; memory requests use slot 1.

`ngram-mod` with its default 48--64-token drafts was candidate A. Candidate B
used 8--16-token drafts, to test whether shorter rejected drafts help when the
slots compete for the GPU. Every B server start warned that `ngram_mod n_match=12`
was too small and poor quality was possible, so B was a deliberately risky throughput
experiment rather than a deployment candidate. At greedy sampling, neither candidate
beat the no-speculation arm in the two-slot phases:

| foreground decode tok/s | off | A: default mod | B: short mod |
|---|---:|---:|---:|
| agent, both slots busy | 26.3 | 25.5 | 23.0 |
| memory, both slots busy | 25.0 | 23.8 | 22.4 |

A had the less-bad dual-agent greedy result, so it was the preselected
production-sampling candidate. The production comparison is the decision run:

| phase | off decode tok/s | A decode tok/s | A drafted / accepted |
|---|---:|---:|---:|
| agent alone | 56.0 | 56.0 | 3,231 / 670 |
| memory alone | 55.6 | 53.5 | 804 / 90 |
| agent foreground, memory looping | 31.3 | 26.7 | 2,293 / 350 |
| memory foreground, agent looping | 25.4 | 23.4 | 996 / 115 |

Decode rate is generated tokens divided by server-reported generation time. A
"combined" rate was also calculated from completed foreground output plus only
background requests that ended before the foreground ended. It is deliberately
conservative rather than an exact GPU rate. Its apparent A dual-agent advantage
(51.4 vs 47.8 tok/s) comes from different sampled output lengths: A completed
17,355 foreground and 21,359 eligible background tokens, versus 9,831 and
9,666 off. Per-request agent decode was slower, so this is not a speedup.

## Correctness and compatibility

Speculation materially changed output hashes: under production sampling, A
matched the no-speculation foreground hash on 4/30 single-agent requests, 10/12
single-memory, 0/30 dual-agent, and 9/12 dual-memory. Some variation is expected
from sampling and concurrent batching, but greedy decoding also changed with
speculation, including requests with zero drafted tokens. In one greedy
single-agent comparison A made two additional requests run to their token cap;
they normally finished with tool calls off-speculation. That is a quality risk,
not a throughput win.

The multimodal projector loaded and text-only requests did draft tokens; GPU
use was effectively unchanged (9507--9508 MiB with and without A). This does
not establish image compatibility. The server rejects a speculative batch that
carries image embeddings, so image traffic remains untested and risky with this
option.

## Decision

The deployment rule was a benefit while both slots are busy. Neither tested
setting met it, and default `ngram-mod` regressed both production two-slot
foreground roles. The live `bonsai-2-27b` entry is therefore unchanged. Raw
requests, server logs, VRAM samples, and replay notes are under
[`bench/results/2026-10-12/m1-ngram/replay/`](https://github.com/aiguy110/bonsai-garden/tree/main/bench/results/2026-10-12/m1-ngram/replay).
