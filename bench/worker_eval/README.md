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

### Scoping and further provenance checks

- Only logs whose prompt has `## Milestone` / `# M1:` and whose stamp is not after the last M1 journal entry are scanned; others (W1 logs etc.) are dropped silently so output does not change as new rounds run.
- `--check` also re-runs `parse_events` on every included log and fails on any rate-limit match.
- Call logs are associated with journal entries by window: for each worker log (sorted by
  stamp), the first `worker (...), round <n>` entry with time in [log start, next worker
  log start). A log with none is skipped as `no_journal_worker` (orphan sessions).
  A journal entry claimed by two logs is a build error.
- Rounds whose original prompt describes the worker as Bonsai are skipped (`bonsai_source`).
- `--check` re-runs in memory and also validates: unique IDs, counts, substitution, prompt
  item/round header, advisor type/order, start-commit subject, and start-commit age
  (0 to 300 s before the log stamp, via `git show -s --format=%aI`).
- The prompt's `## Current item: <id>, round <n>` line must match the log filename.
- The journal's request JSON must be present and equal the recovered request without `report`
  (`journal_request_missing` / `journal_request_mismatch` skips).
- The start commit must be at most 300 s older than the call-log stamp
  (`stale_start_commit` skip), since `commit()` skips unchanged trees.

## Replay harness (`run.py`)

```sh
python3 bench/worker_eval/run.py bonsai-2026-10-12 --repeat 2 --out bench/results/2026-10-12/worker_eval/bonsai-2026-10-12
python3 -m pytest bench/worker_eval/test_run.py      # fixture tests; no GPU, docker or network
```

Options: `--cases PATH` (default `cases.jsonl`), `--repeat N`, `--out DIR` (keep it the same
across chunks; default is a dated dir), `--budget-min` (default 145, at most 150),
`--only CASE_ID` and `--limit N` for smoke runs.

Per `(arm, case_id, repeat)`: a new repo under `/tmp` that holds only the start commit and
its ancestors (fetched by SHA, not cloned, so later branches and the cloud answer are not
visible), checked out detached and removed afterwards; a fresh pi agent dir (settings,
model registration and extensions from the arm); the replay-model line rendered and
verified (exactly one `running as <desc>. The project` line, naming the case's recorded
description, replaced by the arm's, and no other change); pi in the eval sandbox (docker,
`--network none`) reaching live `bonsai-agent` through the tap with the bench key.
`run.py` imports `evals/run.py` and `autopilot/autopilot.py` read-only and lazily, and
uses autopilot's own `check_run_command` against the replay checkout (a local copy is used
only if autopilot cannot be imported).

The prompt is replayed verbatim, so it still says "each session is killed after 45
minutes" (the cloud rounds' limit) while the arm enforces 20.

Requests are taken from `request.json` (the `submit_request` tool), else the last JSON
object in the final reply, else none. Both are checked with `submit_request.ts`'s field and
path rules and the orchestrator's per-kind checks, against the replay checkout as the
session left it.

### Output (`--out`)

- `manifest-<stamp>.json`, one per invocation: repo commit and dirty flag, arm and cases
  SHA-256, pi version and flags, the model registration, model file SHA-256, the
  `bonsai-2-27b` llama-swap entry, turnstile routing (no keys) and commit, sandbox image id.
- `results.jsonl`: one line per finished attempt, appended and fsynced after the attempt.
  Only these lines count as done. Resume skips an exact `(arm, case_id, repeat)` match, so a
  rerun never duplicates one; an attempt killed mid-way has no line and is rerun. Records
  from a different arm file hash make `run.py` refuse (use a new `--out`).
- `<case_id>/r<N>/`: `manifest.json`, `events.jsonl`, `stderr.txt`, `final.txt`,
  `request.json` (if any), `workspace.diff`, `record.json`.
- `infra-errors.jsonl`: attempts that could not start (git, docker, tap); not recorded as
  done. Three in a row stop the chunk.

Record fields: `request_source` (`tool`, `json_fallback`, `none`), `request`,
`validation_errors`, `valid_request`, `cloud_kind`, `replay_kind`, `kind_match`, `wall_s`,
`turns`, `tool_calls`, `tools`, `tool_errors`, `compaction_start`, `compaction_end`,
`stop_reasons` (every assistant reply), `last_stop`, `errors` (raw messages), and the flags
`timeout`, `context_overflow`, `output_limit` (any reply stopped on `length`), `rate_limit`,
`pi_exit_nonzero`.

Cases are scheduled repeat-major, so a partial chunk covers every case once before any twice.
A case is launched only if the arm's session timeout fits in the remaining budget.

## Arms (`arms/`)

`arms/schema.json` documents the format; `run.py` checks required keys, types, enums and
ranges. Fields: `name` (= file name), `description`, `model`, `worker_description`
(the text for the prompt's model line), `thinking`, `max_output_tokens`, `context_window`,
`compaction_reserve_tokens`, `session_timeout_min`, `worker_memory` (`null` only, for now),
`extensions` (repo paths copied into the agent dir) and `sources`.

`bonsai-2026-10-12` and where each value comes from:

| setting | value | source |
|---|---|---|
| model | `garden/bonsai-agent` | `autopilot/README.md` "History" (to go back to Bonsai: `garden/bonsai-agent`); `autopilot.py` `worker_agent_dir()` |
| thinking | `low` | same README paragraph; `evals/arms/baseline.json` |
| max output tokens | 16384 | `agent/models.bonsai-agent.json` `maxTokens`; `autopilot.py` `do_work()` names the 16k limit |
| context window | 81920 | `agent/models.bonsai-agent.json` `contextWindow` |
| compaction reserve | 28672 | `autopilot.py` `worker_agent_dir()` (provider `garden`) |
| session timeout | 20 min | W1 milestone (the historical `worker_timeout_min` was 45) |
| worker memory | off | W1 milestone (the historical `worker_memory` was `mem0`; memory is W3) |
| extensions | `autopilot/extensions/submit_request.ts` | `autopilot.py` `worker_agent_dir()` |

Not proven from here: `autopilot/config.json` now names Terra, and git history is not
readable in the sandbox, so `thinking: low` and the 16384 cap rest on the README's
instruction for restoring the Bonsai worker and the model registration file, not on a
recorded 2026-10-12 config. A reviewer with host access can check them against the first
`autopilot(M1-ngram)` commits' `config.json`.
