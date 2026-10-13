# M2: continuity suite

## Question

Does memory's win on `inventory` hold beyond one hand-built task? And is mem0 judged
fairly? So far it has only run as the JS port inside pi. Its reference
implementation, Python mem0 behind a server, is a separate arm.

## What is already known

- One task, N=3 (`evals/results/2026-10-11-baseline-mem0`): `mem0` passed the whole
  sequence 2/3, `baseline` 0/3. That is suggestive, not a result. See the
  memory-evals experiment page.
- Two mem0 arms exist and are immutable:
  - `mem0`: `@amaster.ai/pi-memory-mem0` in embedded mode. mem0's JS port
    (`mem0ai/oss`) runs inside pi, with an in-process SQLite vector store.
  - `mem0-server`: the same extension in self-hosted mode, against Python mem0
    (`mem0ai[nlp]==2.2.1` plus fastembed, so spaCy entities and BM25 hybrid search
    are on). The harness starts one `evals/mem0_server.py` per step outside the
    sandbox, with on-disk Qdrant and SQLite history in the run dir. Its LLM and
    embedder traffic goes through the tap, so `llm.mem` is metered as in `mem0`.
    The arm pins the mem0 build in `mem0_server.pip`.
  
  The JS port and Python mem0 differ in extraction prompts, update logic and
  retrieval, so their numbers are expected to differ. A gap between them is a
  finding, not noise to explain away.
- A plumbing check of `mem0-server` on `inventory`
  (`/home/josiah/Projects/bonsai-garden/evals/results/2026-10-12-mem0-server-smoke`,
  host only) was stopped during step 1. It ran on an older build of the arm without
  spaCy or BM25, while the GPU was contended. It shows that search, add (metered as
  `mem`) and the memory dump work end to end. It is not a result.
- Runs share turnstile's bench key (priority 20) with the autopilot worker, so
  sequences queue behind worker sessions. pi can time out on a long queue wait
  (`pi_errors: ["Request timed out."]`). Count those steps as infrastructure
  failures, not as agent failures, and rerun them.

## Material

- `evals/README.md`, `docs/benchmark-plan.md`: the harness, sandbox, run rules and
  the per-step record.
- `evals/tasks/inventory/`: the template for a task (`task.json`, `repo/`,
  `check.py`).
- The task sanity gate in `docs/roadmap.md` ("Terms").
- Arms: `evals/arms/baseline.json`, `mem0.json`, `mem0-server.json`, and (from N1,
  `autopilot/milestones/N1-mnemopi.md`) `mnemopi-none.json` and `mnemopi-bonsai.json`.
  New arms go in new files, and existing ones are never edited. If N1 did not produce
  working Mnemopi arms, say so in the journal and run the three mem0-family arms only.

## Done when

1. Five new cross-session tasks plus `inventory`, so six in total. At least two are
   *knowledge-update* tasks, where a fact or convention from step 1 is changed in a
   later step and the checker rewards the new value and penalises the old one.
   Every task passes the sanity gate: the checker fails on the untouched `repo/` and
   passes on a known-good workspace, which is kept outside anything an eval agent
   can see.
2. `baseline`, `mem0`, `mem0-server`, `mnemopi-none` and `mnemopi-bonsai` are run on
   all six tasks at N=5 (about 20 GPU-hours; if the budget is tight, finish the
   other four arms first and run `mem0-server` last). Arms are
   interleaved, as `run.py` already does. Infrastructure failures (pi request
   timeouts, a mem0 server that won't start) are rerun, not scored.
3. Per-task and pooled pass rates with spread, per arm. Pairwise comparisons
   `mem0` vs `mem0-server`, and the best mem0 arm vs the best Mnemopi arm, on the
   knowledge-update tasks. Name the layer W3 should use. Memory-LLM tokens per step
   per arm.
4. An experiment page in the memory-layers series, plus updated series and project
   summaries (`site/AUTHORING.md`).
