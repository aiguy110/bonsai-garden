# Worker-eval corpus

`cases.jsonl` is a replay corpus of successful cloud-worker autopilot rounds. It is
built on the host, where the uncommitted call archive is available:

```sh
python3 bench/worker_eval/build_cases.py
python3 bench/worker_eval/build_cases.py --check
```

The builder reads `~/Projects/bonsai-garden/autopilot/.runtime/calls/`, the M1
journal (preferring the active `auto/M1-ngram` worktree), and `git log --all`. It
never writes under `autopilot/`. `GARDEN_SOURCE` or `GARDEN_CALLS` can override the
host locations. `--check` regenerates in memory and fails if either committed output
differs; it does not modify files.

## Row schema (version 1)

Each JSONL row is one replay case.

| field | meaning |
|---|---|
| `case_id` | Stable ID derived from the call-log path and original prompt hash. |
| `milestone`, `item`, `round` | Autopilot plan position. |
| `source_timestamp`, `source_model` | Call-log timestamp and journal worker model. |
| `start_commit`, `start_commit_subject` | Exact `autopilot(<m>): before <item> round <n>` checkout. |
| `prompt` | First user message replayed verbatim except for one replacement of the first-line worker description. |
| `source_first_user_prompt_sha256`, `prompt_sha256` | Hashes for auditing the input and replay prompt. |
| `event_log`, `event_log_sha256`, `journal` | Host provenance locations and immutable-content hashes. Paths are informative host paths, not replay inputs. |
| `worker_description_from`, `worker_description_to` | The one permitted prompt transformation. `to` is the canonical local Bonsai description. |
| `request`, `request_source` | Recovered cloud request and whether an event tool call, journal copy, or final JSON fallback supplied it. |
| `advisor_timestamp`, `advisor_verdict`, `advisor_notes` | First chronological advisor verdict after the worker request and before the next worker round. `revise` is retained. |

`inventory.json` is a deterministic companion containing included and skipped totals,
and included counts by source model, item, request kind, and advisor verdict.

## Inclusion and validation

Cases start at 2026-10-12 08:33 -04:00. The builder excludes pre-cutoff calls,
rate-limited `spec-replay` entries, absent/recoverable requests, absent advisor
verdicts, and calls without a matching before-round commit. It requires at least 20
rows spanning two items. It validates unique IDs, nonempty prompts and requests,
start-commit subjects, request-before-advisor ordering, exactly one canonical worker
description in each replay prompt, and reconstructs the source prompt from the stored
replacement fields before comparing its SHA-256 hash.
