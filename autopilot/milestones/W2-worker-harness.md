# W2: worker harness

## Question

Which pi and server settings close the gap between Bonsai and the cloud worker on the
W1 case set? W1 measured the `bonsai-2026-10-12` arm: 25/44 valid requests (56.8%),
21/44 kind matches (47.7%), median 903.5 s. Every candidate below runs as a new worker
arm on that benchmark and is compared with that arm. Keep what helps; report what
doesn't.

## What is already known

- W1's experiment page (`site/series/local-worker/worker-eval.md`), `bench/worker_eval/`
  and `bench/worker_eval/arms/bonsai-2026-10-12.json` hold the benchmark, the baseline
  numbers and the failure-mode breakdown. Read the failure modes first: they say which
  candidates to try first.
- W1 caveats to respect: the arm file's digests hash stripped text, not blob bytes (the
  correct ones are in `bench/worker_eval/README.md`); replay checkouts expose Git
  history the original worker could not see; the replay prompt says 45 minutes while
  the arm enforces 20 (candidate 0 fixes this).
- Within one worker session there is only one user message, so every earlier turn's
  thinking appears to stay in the prompt (`bench/m1-notes.md`): prompt growth matched
  tokens generated. Inferred from token counts, not confirmed in pi's source.
- pi caps a tool result at 50 KB / 2000 lines, about 12k tokens, which is large for
  the 80k window. pi's `edit` is exact-text replacement; 18 of Bonsai's 59 edits
  failed, and it did most work through bash (74 of 712 calls failed, 10.4%).
- llama.cpp's reasoning budget (`reasoning_budget_tokens`, `reasoning_budget_message`)
  is settable per request, so it can be tested through the tap without a live-config
  change.

## Candidates

Work in this order unless W1's failure modes say otherwise. Each is an arm in
`bench/worker_eval/arms/`; new arms never edit old ones. Run each at N=2 on all cases.

0. **Corrected baseline (first; every later arm is compared with this one, not with
   `bonsai-2026-10-12`).** W1 replays each recorded prompt verbatim, and it says
   sessions are killed after 45 minutes, while the arm enforces 20. Add a replay
   option (an arm field, e.g. `prompt_timeout_min`) that rewrites that sentence to the
   arm's real limit, and run a `bonsai-2026-10-12-honest` arm identical to the W1 arm
   but with it. Keep the 20-minute limit. Report the difference from the W1 run: that
   shows how much the false 45 minutes cost, within the run-to-run spread. Do not
   change `bonsai-2026-10-12` or its recorded results. If the rewrite changes anything
   else in the prompt, say so.
1. **Thinking.** Drop thinking older than the last few turns before each request; a
   larger output limit (16k now) paid for by the freed context; a reasoning budget.
1b. **Stock oh-my-pi as a whole harness (moved up: run it right after the first
   single-factor batch, before session discipline and the combinations).** It
   brings hashline edits natively, so it also stands in for candidate 3. Steps: pack
   the npm package into a new empty directory with `--ignore-scripts` (no install
   scripts; record version, license, tarball sha256 and what runtime it needs), and
   put any runtime it needs (for example Bun) in a pinned, hash-checked user-space
   directory under the milestone worktree, never system-wide. Add a harness field
   to the arm format (`pi` by default) and run `omp` in the same sandbox, tap and
   model entry, with the honest prompt and the 20-minute limit. Try `submit_request`
   under it; if it doesn't load, rely on the JSON fallback and say so. Record the
   first request's prompt tokens under both harnesses, so the context-cost question
   is answered with a number. Do not tune omp beyond stock defaults except to make
   it talk to our model. Compare with the honest baseline like any other arm.
2. **Tool output.** A smaller result cap that tells the model where the rest is.
3. **Editing.** Hash-anchored line edits ("hashline", from oh-my-pi) as a plain pi
   extension (ports exist: `pi-hashline-edit`, `pi-hashline-context-edit`). Install
   in the sandbox only; check the package source before use.
4. **Session discipline.** Turn and time budgets in `submit_request`: warnings first,
   then only that tool allowed. Smaller items for a local worker.
5. **Compaction (M6 alongside).** The reserve, and what the summary keeps. Only the
   settings that matter to worker arms; the memory-backed compaction suite is M6 and
   is not part of this milestone.
6. **Combinations** of whatever helped.

## Constraints

- Do not change files under `autopilot/`, the live llama-swap entry or turnstile.
  Settings that need a live-config change are reported as proposals in `serving/`.
- Replay runs go through turnstile with the bench key, in chunks of at most 150 min.
- The GPU is power-capped (250 W); do not alter it.

## Done when

1. Arm files for the candidates above, each with a stated hypothesis.
2. Every arm run on every W1 case at N=2, with valid-request rate, kind-match rate,
   median time and failure-mode breakdown against the corrected baseline (and the
   W1 arm, for the first comparison). Note which
   differences exceed the run-to-run spread; don't claim wins inside it.
3. Advisor grading of at most 10 passing requests from the best arm, as in W1.
4. A recommended worker configuration (arm + any extension or setting), with the
   remaining gap to the cloud worker.
5. An experiment page in the local-worker series (`site/AUTHORING.md`), and updated
   series and project pages. `python3 bench/check_site.py` passes.
