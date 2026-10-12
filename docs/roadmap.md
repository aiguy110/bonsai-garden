# Roadmap

Status as of 2026-10-12: serving is done (two slots, turnstile co-admission). One
memory eval has run: 1 task, N=3, mem0 2/3 vs baseline 0/3. That is suggestive,
not a result. A second mem0 arm, `mem0-server`, runs Python mem0 (the reference
implementation) instead of the JS port. The autopilot works M1, then M2.

## Terms

- **Task:** one benchmark scenario, stored in `evals/tasks/<name>/`. It has three
  parts:
  - `task.json`: an ordered list of **steps**. Each step is one prompt given to a
    *fresh* pi session, as if the user came back the next day.
  - `repo/`: the starting workspace that the agent edits.
  - `check.py`: run after each step. It inspects the workspace and the agent's final
    message and scores named checks pass/fail (e.g. `docstring`, `risk_line`,
    `suite_green`).
  
  Example: `inventory` has 3 steps. Step 1 states four conventions and a staging
  host. Steps 2 and 3 only say "follow the conventions" or "as discussed".
- **Arm:** one agent configuration (`evals/arms/<name>.json`), e.g. `baseline`
  (no memory), `mem0` (mem0's JS port inside pi) or `mem0-server` (Python mem0
  behind a per-step server; see [mem0 arms](#mem0-arms)).
- **Run:** arms × tasks × repeats. Each step of each repeat counts as one pass or
  fail.
- **Task sanity gate:** a new task is only accepted if two things hold. First, its
  checker *fails* on the untouched `repo/`, so the task is not already solved.
  Second, the checker *passes* on a known-good finished workspace, so the checker is
  not broken. The known-good workspace is kept outside anything an eval agent can
  see.

## Milestones

| # | Milestone | Question | Done when |
|---|---|---|---|
| M1 | **N-gram speculation** | Does llama-server's n-gram self-speculation speed up real agent and memory traffic, including when both slots are busy? | Replay of recorded agent and mem0 traces on :8089 (np2, both slots loaded) with and without `--spec-type ngram-*`; tok/s and acceptance rate per role. If it wins, a proposed config goes to the user. Deploying it is a live-stack change |
| M2 | **Continuity suite** | Does mem0's win hold beyond one hand-built task, and does it depend on which mem0? | 6 cross-session tasks, `baseline` vs `mem0` vs `mem0-server`, N=5; per-task and pooled pass rates with spread. Include ≥2 *knowledge-update* tasks, where a step 1 fact is changed in step 2. Spec: [`autopilot/milestones/M2-continuity.md`](../autopilot/milestones/M2-continuity.md) |
| M3 | **Regression guard** | Does memory hurt tasks that don't need it? | 12 single-session tasks run with a pre-filled, *irrelevant* memory store vs baseline; no significant drop |
| M4 | **Other memory layers** | Is mem0 the right design for a small local model? | Arms below, run on the M2 suite and M3 guard; pass rate vs memory-LLM tokens per step |
| M5 | **Cheaper memory writes** | Can the ~8k-token prefill per mem0 write be cut? | Variants of capture (per turn vs end of session), a shorter extraction prompt, recall top-k; cost vs pass-rate curve |
| M6 | **Long-horizon / compaction** | Within one session, does memory beat compaction alone? | 4 tasks that force compaction; pi default vs memory-backed compaction |
| M7 | Memory-only eval (optional) | Isolate retrieval quality from agent skill | LoCoMo-style subset |

Rules from `benchmark-plan.md` apply throughout. New arms never edit old ones.
Every result updates its experiment, series and project pages.

### mem0 arms

The extension can reach mem0 in three ways. `platform` is mem0's hosted API, which
we don't use. `embedded` loads mem0's JS port (`mem0ai/oss`) into pi. `self-hosted`
calls a mem0 REST server. The JS port ships less often than Python mem0 and has
different prompts and update logic, so judging mem0 only by the port could be unfair
to it. Both are arms:

- `mem0` (embedded): JS port, in-process SQLite vector store.
- `mem0-server` (self-hosted): Python mem0, served by `evals/mem0_server.py`, which
  is upstream's REST endpoints over `mem0.Memory` without Postgres or auth. The
  harness starts one server per step outside the sandbox. It uses the run's
  on-disk Qdrant and SQLite history, and its LLM and embedder traffic is metered
  through the tap. `mem0_server.pip` in the arm pins the build. A mem0 change can
  be tested by pointing a *new* arm at a fork's git ref. It is a full install
  (spaCy entities, fastembed BM25 hybrid search), as a stock deployment would be.

### M4 candidates

mem0 OSS 3.x is a passive extractor. Each turn costs one large LLM call (the
extraction prompt alone is ~36 KB). It only *adds* memories, deduplicated by exact
hash, so a changed fact leaves the old one in place. The two alternatives sit on
either side of that design:

1. **`blocks`: agent-managed memory blocks (Letta/MemGPT "core memory" style).**
   A thin pi extension keeps a few small named text blocks, such as `conventions`,
   `facts` and `open-threads`, in a file per workspace. It shows them on every turn
   and gives the agent `memory_replace` / `memory_append` tools. It makes no extra
   LLM calls and uses no embeddings, but it relies on the model's own judgement
   about what to save. That is a real question for a 2-bit 27B. We would write and
   publish it as a pi package. It also covers the "plain notes file" baseline.
2. **`graphiti`: temporal knowledge graph (Zep's open-source Graphiti), with
   FalkorDB in one local container.** Facts are graph edges with validity intervals, so an
   updated convention retires the old one rather than sitting next to it. It is the
   most structured option, and its per-episode cost is several LLM calls. Comparing
   it with mem0 on the knowledge-update tasks is the point. The work is a pi
   extension that calls Graphiti's Python API through a small local service.

## Autonomous pursuit ("autopilot")

Implemented in [`autopilot/`](../autopilot/README.md). Bonsai does the work in a
sandbox. A cloud advisor (`meridian/claude-opus-5-5` via pi, swappable) plans,
reviews every request and fact-checks write-ups. Deterministic code runs the
probes and evals, enforces protected paths, and publishes. Live-server changes go
through `autopilot/infra.py`:
- the change is applied under a GPU lease;
- it is health-checked and speed-checked, and rolled back on failure;
- it becomes known-good only after a soak period.

If the local model goes down, a cloud fixer takes over. Progress is published to
the site's autopilot status page.

M1 (n-gram speculation) is the first milestone and the test case. Bonsai measures,
then possibly changes, the server it runs on. M2 (continuity suite) is queued next.
Milestones run in the order of `milestones` in `autopilot/config.json`, and each
needs a spec in `autopilot/milestones/<name>.md`.

### Throughput estimate

One sequence on one arm takes about 8 min, so M2 (6 tasks × 3 arms × N=5) is about
12 GPU-hours. M1 is about 2 GPU-hours of replays.
