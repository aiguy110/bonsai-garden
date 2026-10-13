---
layer: experiment
series: serving
title: Two-slot server and prompt-cache behaviour
status: done
date: 2026-10-11
updated: 2026-10-11
tldr: Deployed the 2-slot server; replaying agent traffic showed every turn prefills only its new tokens, so the planned checkpoint tuning was unnecessary.
summary: |
  **Question:** does the two-slot config behave in production? And does the
  prompt cache force agents to re-process thousands of tokens each turn?

  **Why it mattered:** Bonsai is a hybrid model. Its recurrent layers can't be
  rewound, so if a new prompt diverges from the cached one, the server falls back
  to the last saved checkpoint. The default checkpoint spacing could mean ~8k
  tokens (~9 s) of re-prefill per agent turn.

  **Results:**
  - Deployed: 9503 MiB VRAM, 44.6 tok/s per stream with both slots busy.
  - A 14-turn tool-calling replay (to ~17k tokens) prefilled **only the new
    tokens each turn**. That held with the default spacing and with 4x denser
    checkpoints. This fork checkpoints right at the end of each prompt, so
    append-only traffic never rolls back. A real pi session looked the same.
  - Requests can be pinned to a slot (`id_slot`), and thinking can be turned off
    per request. The memory role needs both.

  **Conclusion:** no cache tuning shipped. The issue may come back once
  compaction starts rewriting history.
---

## Changes

- `bonsai-2-27b` in llama-swap now runs `--parallel 2 --kv-unified`
  ([config](https://github.com/aiguy110/bonsai-garden/blob/main/serving/llama-swap.bonsai-2-27b.yaml)).
- pi got a `bonsai-2-27b` model entry.

## Checkpoint replay

[`bench/checkpoint_replay.py`](https://github.com/aiguy110/bonsai-garden/blob/main/bench/checkpoint_replay.py)
replays a tool-calling conversation the way an OpenAI-style client sends it:
reasoning is dropped from history and each turn appends tool results. For every
turn it records `prompt_n` (tokens actually prefilled) and `cache_n` (tokens
reused).

| checkpoint spacing | per-turn prefill |
|---|---|
| 8192 (default) | new tokens only |
| 2048 | identical |

A live pi session through a metering proxy showed `cache_n` equal to the previous
prompt plus the previous generation on every turn.

## Gotchas found along the way

- Scripted `pi -p` with a fresh config directory hangs unless stdin is closed.
- `chat_template_kwargs: {enable_thinking: false}` works on this fork. No
  reasoning is emitted.
