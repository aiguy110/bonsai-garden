---
layer: experiment
series: serving
title: N-gram self-speculation on recorded agent traffic
status: done
date: 2026-10-12
updated: 2026-10-12
tldr: N-gram speculation slowed real two-slot agent and mem0 replays, changed outputs, and was not deployed.
summary: |
  **Question:** can llama-server's no-extra-model n-gram speculation make the
  agent and mem0 faster on their actual traffic?

  **Method:** replayed 30 recorded pi agent requests and 12 rebuilt mem0
  extraction calls on a private production-equivalent two-slot server. A fresh
  server ran each single- and dual-slot phase. We compared speculation off with
  default `ngram-mod` and a shorter-draft setting under greedy decoding, then
  repeated off and default `ngram-mod` with production sampling.

  **Result:** default `ngram-mod` was equal for single-agent production traffic
  (56.0 tok/s), but slower with both slots busy: agent foreground **26.7 vs
  31.3 tok/s** and memory foreground **23.4 vs 25.4 tok/s**. Its dual-phase
  draft acceptance was 15.3% (agent) and 11.5% (memory), and it changed output
  hashes. The projector loaded for text-only traffic, but image embeddings are
  unsupported with speculation. **Decision:** do not deploy.
---

## Method

The probe is [`bench/spec_replay.py`](https://github.com/aiguy110/bonsai-garden/blob/main/bench/spec_replay.py).
It uses the live command except for private port `8089`, retaining `--parallel 2`,
unified q4_0 KV, and the multimodal projector. Each phase starts a fresh server:
agent alone, memory alone, agent foreground with memory looping, and memory
foreground with agent looping. The set has 30 recorded pi agent turns and 12
mem0-style JSON-object extraction requests rebuilt from extension source.

Candidate A was default `ngram-mod`; candidate B used 8--16-token drafts rather
than A's default 48--64. Every B server log warns that `ngram_mod n_match=12 is
too small - poor quality is possible`, so B was a deliberately risky throughput
experiment rather than a deployment candidate.

## Replay results

Decode rate is generated tokens divided by server-reported generation time. These
foreground results are copied from the [decision summary](https://github.com/aiguy110/bonsai-garden/blob/main/bench/results/2026-10-12/m1-ngram/summary.md).

| sampling | foreground phase | off tok/s | A tok/s | B tok/s | A acceptance |
|---|---|---:|---:|---:|---:|
| greedy | agent, both slots busy | 26.3 | 25.5 | 23.0 | 14.0% |
| greedy | memory, both slots busy | 25.0 | 23.8 | 22.4 | 9.3% |
| production | agent alone | 56.0 | 56.0 | — | 20.7% |
| production | memory alone | 55.6 | 53.5 | — | 11.2% |
| production | agent, both slots busy | 31.3 | 26.7 | — | 15.3% |
| production | memory, both slots busy | 25.4 | 23.4 | — | 11.5% |

A's production two-slot rates are 0.853x off for agent foreground and 0.920x
off for memory foreground. Its phase-specific VRAM deltas were +1, +1, +1, and
-1 MiB. The deployment decision therefore failed the two busy-slot performance
rules and the tool-JSON validity rule; the live `bonsai-2-27b` entry was not
changed.

## Identity and compatibility

At greedy sampling, compared with off in the same phase, A was identical on
3/30 single-agent, 10/12 single-memory, 0/30 dual-agent, and 11/12 dual-memory
requests. This is not solely a speculation effect: the off dual-versus-single
batch control was 0/30 for agent and 10/12 for memory. Nevertheless,
`ngram-mod` changed even some zero-draft greedy responses, and sampled outputs
also diverged from the original recordings. It also caused some agent turns to
reach their token cap where off-speculation finished with tool calls.

The pinned multimodal projector loaded in all four production A phases, and
text-only requests drafted tokens. That does **not** establish image support:
the server rejects a speculative batch carrying image embeddings, so image
traffic is untested and risky with this option.

## Replay caveats

The recorded pi system sections were joined with blank lines; that rendering is
inferred rather than directly captured. Rebuilt mem0 user prompts are likewise
approximate: memory serialization, history formatting, retrieval choice, and
tool-add content require reconstruction. Each replay body used a per-request
`max_tokens` cap derived from the recorded generated-token count (with role
floors), because the recordings did not retain original caps. These limits and
the reconstructed prompts mean replay output need not reproduce the recordings.

Raw requests, server logs, VRAM samples, and replay notes are under
[`bench/results/2026-10-12/m1-ngram/`](https://github.com/aiguy110/bonsai-garden/tree/main/bench/results/2026-10-12/m1-ngram), with the
[analysis script](https://github.com/aiguy110/bonsai-garden/blob/main/bench/spec_summarize.py)
and [decision artifact](https://github.com/aiguy110/bonsai-garden/blob/main/bench/results/2026-10-12/m1-ngram/deploy.json).
