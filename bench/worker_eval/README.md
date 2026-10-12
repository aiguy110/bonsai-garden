# Worker-eval corpus

`cases.jsonl` is a replay corpus of successful cloud-worker autopilot rounds. It is
built on the host, where the uncommitted call archive is available:

```sh
python3 bench/worker_eval/build_cases.py
python3 bench/worker_eval/build_cases.py --check
```

The builder reads `~/Projects/bonsai-garden/autopilot/.runtime/calls/`, **one**
authoritative M1 journal, and `git log --all`.  Its explicit journal preference is
`GARDEN_M1_JOURNAL`, the `auto/M1-ngram` worktree, the main source checkout, then
the current checkout; it never merges copies. It never writes under `autopilot/`.
`GARDEN_SOURCE` or `GARDEN_CALLS` can override the host locations. `--check`
regenerates in memory and fails if either committed output differs; it does not
modify files.

## Row schema (version 1)

Each JSONL row is one replay case.

| field | meaning |
|---|---|
| `case_id` | Stable ID derived from the call-log filename and original prompt hash (not an absolute path). |
| `milestone`, `item`, `round` | Autopilot plan position. |
| `source_timestamp`, `source_model` | Call-log timestamp and journal worker model. |
| `start_commit`, `start_commit_subject` | Exact `autopilot(<m>): before <item> round <n>` checkout. |
| `prompt` | First user message replayed verbatim except for one replacement of the first-line worker description. |
| `source_first_user_prompt`, `source_first_user_prompt_sha256`, `prompt_sha256` | The recorded first user message and hashes for auditing the sole replay transformation. |
| `event_log`, `event_log_sha256`, `journal`, `journal_sha256` | Host provenance locations and immutable-content hashes. Paths are informative host paths, not replay inputs. |
| `worker_description_from`, `worker_description_to` | The one permitted prompt transformation. `to` is the canonical local Bonsai description. |
| `worker_entry_timestamp` | Time of the matched worker journal entry. |
| `request`, `request_source` | Recovered cloud request from an event tool call or final-assistant JSON fallback. A journal JSON copy is only an equality cross-check. |
| `advisor_timestamp`, `advisor_actor`, `advisor_verdict`, `advisor_notes` | First chronological, request-kind-matched advisor verdict after the worker request and before the next worker round. `revise` is retained. |

`inventory.json` is a deterministic companion containing included and skipped totals,
and included counts by source model, item, request kind, and advisor verdict.

## Inclusion and validation

Cases start at 2026-10-12 08:33 -04:00, decided by the matched worker journal
entry time (`worker_entry_timestamp`) and a non-Bonsai model. The builder excludes
earlier entries, rate-limited rounds (rate-limit text in the parsed event errors of
`evals/run.py:parse_events`, or in the worker journal entry; prompt and tool text
are not scanned), `continue`/`stuck` requests (no advisor review; `done` is
matched to `advisor (finished item)` or `advisor (write-up)`), absent recoverable requests, absent kind-matched advisor verdicts,
and calls without an unambiguous before-round commit. Repeated before-round subjects
are selected by the latest commit timestamp at or before the call timestamp; tied
candidates are rejected. It requires at least 20 rows spanning two items. It
validates unique IDs, nonempty prompts and requests, start-commit subjects,
request-before-advisor ordering, advisor type, and exactly one worker-description
substitution by rebuilding the replay prompt from the recorded first user message.
If any otherwise eligible round was marked `revise`, at least one such case must be
retained. Outputs are written only after all validation succeeds.

## Additional provenance checks

- A journal worker entry may be claimed by at most one call log (duplicate is a build error).
- The prompt's `## Current item: <id>, round <n>` line must match the log filename.
- The journal's request JSON must be present and equal the recovered request without `report`
  (`journal_request_missing` / `journal_request_mismatch` skips).
- The start commit must be at most 300 s older than the call-log stamp
  (`stale_start_commit` skip), since `commit()` skips unchanged trees.
