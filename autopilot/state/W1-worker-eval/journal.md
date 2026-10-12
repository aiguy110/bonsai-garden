
### 2026-10-12T12:48:21-04:00 · advisor (plan)

1. **Extract a provenance-checked cloud-worker case set**: `bench/worker_eval/cases.jsonl` has at least 20 valid rows from the required time range and at least two distinct `item` values; a committed inventory reports counts by source model, item, request kind, and advisor verdict. Every referenced start commit resolves and has the expected before-round subject. Re-running `python3 bench/worker_eval/build_cases.py --check` on the host exits 0 without changing the file, reports no included rate-limit failures, and demonstrates that each stored prompt differs from its recorded first user message only in the single worker-description substitution. At least one `revise` case is retained if any eligible source round received that verdict.
2. **Define worker arms and implement the resumable replay harness**: `bench/worker_eval/arms/schema.json`, `bench/worker_eval/arms/bonsai-2026-10-12.json`, `bench/worker_eval/run.py`, and tests exist. The baseline arm explicitly has memory disabled, a 20-minute timeout, a 28,672-token compaction reserve, the historical 16,384-token output cap unless the provenance proves otherwise, and the historical thinking level, with sources cited in `README.md`. Tests pass locally without GPU or network. A host smoke run of one case completes through the live turnstile bench route with `gpu=false`, leaves the milestone worktree unchanged except for results, creates its checkout outside that worktree, produces all required fields and artifacts, and a second invocation skips the completed attempt without duplicating its result. The manifest pins the repository commit, cases and arm hashes, pi version, model registration, and non-secret live routing/server metadata.
3. **Run Bonsai at N=2 and summarize deterministic outcomes**: The dated result directory contains exactly two completed records for every case and no duplicate `(case_id, repeat)` keys; its manifest proves use of `bonsai-2026-10-12` and the bench-key live route. `summarize.py --check <result-dir>` exits 0 and recomputes all reported values from `results.jsonl`. `summary.json` and `summary.md` contain the required per-case and pooled valid-request rates, both kind-match denominators, median times, and failure-mode counts. Every timeout, context overflow, and output-limit count traces to an attempt's explicit flag and raw event/error evidence, and every case is represented even when both repeats failed.
4. **Grade a deterministic sample of valid Bonsai requests**: The result directory contains the sample manifest, filled grading packets or their hashes, `advisor_grades.jsonl`, and `advisor_summary.md`. There are 1–10 unique sampled attempts, all marked deterministically valid in `results.jsonl`, and the selection can be regenerated exactly. Every grade names the advisor model, run ID, request kind, verdict, and rationale and is traceable to an advisor journal response using `autopilot/prompts/review.md`. The summary reports approval/revision/rejection counts and approval rate with its sample denominator, separately from valid-request and kind-match rates, and clearly labels this as a small judged sample.
5. **Publish the W1 experiment and update parent summaries**: `site/series/local-worker/worker-eval.md` has valid experiment front matter, a summary of at most 200 words, exact numbers matching `summary.json` and `advisor_grades.jsonl`, per-case and pooled tables, explicit caveats, and evidence-linked W2 priorities. `site/series/local-worker/index.md` and `site/index.md` have current hand-written summaries and `updated` dates no older than the experiment. `README.md` and `docs/roadmap.md` consistently record W1's result and W2 as the next local-worker step. `python3 tools/check_site.py` passes, and the final advisor review verifies every numerical claim against committed result files.

### 2026-10-12T12:51:29-04:00 · worker (gpt-5.6-terra), round 1

Added the host-only corpus builder and schema documentation. The builder parses cloud call logs and the M1 journal, preserves prompt/event provenance, reconstructs requests and advisor verdicts, resolves before-round commits, and writes deterministic cases plus inventory. Local syntax/substitution smoke checks pass. Next: run it on the host archive, inspect validation/counts, and correct parsing if archive formats differ.

```json
{
  "request": "run",
  "command": "python3 bench/worker_eval/build_cases.py",
  "gpu": false,
  "timeout_min": 10,
  "why": "Build the required case corpus from the host-only autopilot call archive, journal, and git history; no GPU, network, or live-stack access is used."
}
```

### 2026-10-12T12:53:53-04:00 · advisor (run request)

**revise**: Fix `bench/worker_eval/build_cases.py` before running: (1) `host_paths()` returns multiple copies of the M1 journal (main, old M1 worktree, and current worktree). After sorting, duplicate worker entries make `associated_advisor()` stop at the next duplicate worker, so valid rounds lose their verdicts. Select exactly one authoritative journal with an explicit preference order, rather than merging copies. (2) `commits()` keys only by milestone/item/round and overwrites duplicate subjects; repeated rounds such as `spec-replay` round 5 can therefore receive the wrong start commit. Collect commit timestamps and select the latest matching before-round commit at or before each call timestamp, rejecting ambiguity. (3) Recover fallback requests from the event log's final assistant text before consulting the journal, and label sources only `tool` or `json_fallback` as required; use the journal only to cross-check equality. (4) Make case IDs independent of the absolute archive path, e.g. hash the log filename plus original prompt hash. (5) Require exactly one source worker-description match before substitution, validate advisor type against request kind and compare parsed datetimes, explicitly reject included source logs/worker entries containing rate-limit errors, and make absence of a retained eligible `revise` case an error rather than a warning. (6) Do not write `cases.jsonl` or `inventory.json` when validation fails; currently an empty or invalid build clobbers outputs before exiting nonzero. The script otherwise performs only read-only git/archive operations and writes under `bench/worker_eval/`.

### 2026-10-12T12:54:50-04:00 · worker (gpt-5.6-terra), round 2

Corrected the builder for authoritative single-journal selection, timestamped start-commit resolution, event-first request recovery, strict provenance/substitution checks, rate-limit exclusion, advisor-kind validation, and no-write-on-validation-error. Updated the corpus README. Local syntax/help checks pass; host archive generation is next.

```json
{
  "request": "run",
  "command": "python3 bench/worker_eval/build_cases.py",
  "gpu": false,
  "timeout_min": 10,
  "why": "Run the corrected host-only corpus builder against the call archive, authoritative M1 journal, and git history to generate and validate the required provenance-checked cases and inventory."
}
```

### 2026-10-12T12:55:14-04:00 · orchestrator

The advisor's subscription hit its rate limit; pausing 30 min. This session doesn't count as a round.

### 2026-10-12T13:25:17-04:00 · orchestrator

The worker's subscription hit its rate limit; pausing 30 min. This session doesn't count as a round.

### 2026-10-12T13:41:33-04:00 · orchestrator

The worker's subscription hit its rate limit; pausing 96 min. This session doesn't count as a round.

### 2026-10-12T13:46:58-04:00 · worker (gpt-5.6-terra), round 3

The round 2 corrections are in place. The script compiles and `--help` works. The earlier run request never executed because of the rate-limit pauses, so this resubmits it. I have not run the builder against the host archive, so I don't know yet whether the validation passes. Next round I'll read the output and fix any parsing problems.

```json
{
  "request": "run",
  "command": "python3 bench/worker_eval/build_cases.py",
  "gpu": false,
  "timeout_min": 10,
  "why": "Run the corrected corpus builder on the host against the call archive, the M1 journal and git history. It needs no GPU. The output will show whether the validation passes and how the cases and inventory look."
}
```

### 2026-10-12T13:49:31-04:00 · advisor (run request)

**revise**: Safe to run, but three bugs would discard almost every round, so it would only waste a round. Fix them first. (1) associated_advisor() expects `advisor (done request)`, but the orchestrator writes `advisor (finished item)` or `advisor (write-up)` for done requests (autopilot.py:852); only run/infra become `advisor (<kind> request)` (lines 833, 837). Map kinds to those labels in build() and validate(), or roughly 8 done rounds are lost, including the revise verdicts at 11:24, 11:32 and 11:35. Because eligible_revise is only counted after an advisor match, the revise-retention check would also pass vacuously. (2) The journal JSON omits `report` (worker_entry, autopilot.py:783), while submit_request.ts:106 requires it, so same_json() fails for every tool request. Drop `report` from the recovered request before the cross-check, but keep the full request in the row. (3) RATE_LIMIT.search(raw) scans the whole event log, including the prompt's 15,000-char journal tail (which contains the 09:55 rate_limit_error entries and the 10:23 note) and all tool output, and `\b429\b` matches stray numbers. That wrongly drops the Terra rounds at 10:30, 10:33, 10:35 and likely 10:52. Apply the regex only to evals/run.py parse_events(path)['errors'] (as check_rate_limit does) and to the worker's journal entry. (4) Decide the 08:33 cutoff by the matched journal entry (time >= 08:33 and model != Bonsai), not the call-log start time; Sonnet round 6's session probably started before 08:33:00 although its entry is at 08:33:38. (5) Give `continue` requests (rounds 8 and 9 at 11:16/11:19) and `stuck` requests their own skip reason, not no_matching_advisor_verdict. By the journal, about 22 rounds should qualify; if a correct build finds fewer than 20, report it rather than loosening the rules. Then resubmit this run request.

### 2026-10-12T13:49:31-04:00 · orchestrator

Added to the standing facts:

- The journal labels advisor verdicts by review type, not request kind: `advisor (run request)` and `advisor (infra request)`, but `advisor (finished item)` or `advisor (write-up)` for done requests, and `continue` requests get no review (autopilot/autopilot.py:831-855).
- The worker's journal entry stores its request JSON with `report` removed (autopilot/autopilot.py:781-784), so a journal request is not byte-equal to the submit_request arguments.

### 2026-10-12T13:50:33-04:00 · worker (gpt-5.6-terra), round 4

Fixed the advisor's five points in build_cases.py. Done requests now match `advisor (finished item)` or `advisor (write-up)`. `report` is dropped before the journal cross-check, but the full request stays in the row. The rate-limit regex now runs only on `parse_events` errors and the worker's journal entry. The cutoff uses the journal entry time and a non-Bonsai model, and the log filename prefilter has a one-hour margin. `continue` and `stuck` requests get their own skip reasons. The README is updated and the script compiles. I have not run it against the host archive, so I don't know the case count yet. Next round I'll read the inventory and skip counts and fix any parsing problems.

```json
{
  "request": "run",
  "command": "python3 bench/worker_eval/build_cases.py",
  "gpu": false,
  "timeout_min": 10,
  "why": "Run the corrected builder on the host archive, journal and git history to produce cases.jsonl and inventory.json. It needs no GPU."
}
```

### 2026-10-12T13:53:24-04:00 · advisor (run request)

**approve**: Safe: read-only on the archive, journal and git; it writes only bench/worker_eval/{cases.jsonl,inventory.json}, and only after validation passes. The round 3 fixes check out against autopilot.py. Expect about 22 rows; if fewer than 20 pass, report the skip counts instead of loosening the rules. Before calling the item done, add these checks and re-run with --check: (1) Each journal worker entry may be claimed by at most one log. associated_worker() matches on round number and nearest time only, so two logs can map to one entry. Treat a duplicate as an error. (2) Check that the recorded prompt's `## Current item: <id>, round <n>` line matches the log filename's item and round. The journal headers don't name the item, so this is the only direct item check. (3) Require journal_req to be present and equal to the request without `report`; skip with `journal_request_missing` otherwise. Every reviewed round has the JSON in its worker entry (worker_entry, autopilot.py:781-784). Today a missing journal JSON passes the cross-check, so a final submit_request call the tool rejected could slip through. (4) Reject a start commit whose author time is more than a few minutes before the call-log stamp. commit() skips when nothing changed (autopilot.py:426-430), and select_commit() would then quietly pick an earlier attempt's commit with the same subject. (5) In log_data(), skip lines whose JSON isn't a dict or whose `message` isn't a dict, so a stray event can't crash the build. Commit the inventory with the cases.

### 2026-10-12T13:53:24-04:00 · orchestrator

Added to the standing facts:

- autopilot.py commit() (lines 426-430) only commits when the tree changed, so a round's `before <item> round <n>` commit can be missing and the latest earlier same-subject commit is not necessarily that round's start state.

### 2026-10-12T13:53:26-04:00 · orchestrator

Ran `python3 bench/worker_eval/build_cases.py` (gpu=False) in 1s, exit 0. Full output: `bench/results/2026-10-12/autopilot/case-corpus-r4.log`. Last lines:

```
{
  "canonical_worker_description": "Bonsai 2 27B (Ternary-Bonsai-2-27B, 2-bit), a local model on this machine's GPU",
  "counts": {
    "advisor_verdict": {
      "approve": 15,
      "revise": 7
    },
    "item": {
      "decide": 3,
      "replay-set": 7,
      "spec-replay": 10,
      "write-up": 2
    },
    "request_kind": {
      "done": 8,
      "run": 14
    },
    "source_model": {
      "claude-sonnet-5-5": 11,
      "gpt-5.6-terra": 11
    }
  },
  "eligible_revise": 7,
  "included": 22,
  "schema_version": 1,
  "skipped": {
    "before_cutoff": 24,
    "before_cutoff_or_bonsai": 1,
    "no_journal_worker": 6,
    "no_recoverable_request": 2,
    "rate_limited": 8,
    "unreviewed_continue_request": 2
  }
}

```
