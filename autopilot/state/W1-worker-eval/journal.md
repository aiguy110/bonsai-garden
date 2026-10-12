
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
