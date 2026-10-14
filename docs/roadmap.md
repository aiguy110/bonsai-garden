# Roadmap

Status as of 2026-10-14: serving is done (two slots, turnstile co-admission;
n-gram speculation replayed and rejected). One memory eval has run: 1 task, N=3,
mem0 2/3 vs baseline 0/3. That is suggestive, not a result. A second
mem0 arm, `mem0-server`, runs Python mem0 (the reference implementation)
instead of the JS port. W1 local-worker replay is also done: on 22 real
cloud-worker rounds at N=2, Bonsai submitted valid requests in 25/44 attempts
(56.8%) and matched request kind in 21/44 (47.7%). W2 (worker harness) is running.
Alongside it, T1, a small Terminal-Bench 2.0 probe, is being prepared for a rented GPU:
the worker eval is one milestone in one repo, and only 9 of its 22 cases separate arms.

Bonsai couldn't keep up as the autopilot's worker (11 of 21 rounds sent no request),
so since 2026-10-12 the worker is a cloud model (Claude Sonnet 5.5, then GPT-5.6
Terra through Codex). The priority now is the
[local worker track](#local-worker-track): making the stack good enough that Bonsai
can do this research itself. M1 and W1 are done. Order from here on the 3080: W2
(worker harness; its single-factor arms are screened at N=1 on the signal cases), then
N1 (oh-my-pi's Mnemopi memory layer as a pi extension), then M2 with
Mnemopi arms added, then W3 (using whichever layer wins M2), W4, and the rest. T1
(vanilla pi vs stock oh-my-pi on 10 random Terminal-Bench 2.0 tasks and W2's 9 signal
cases, N=1) runs by hand on rented hardware, outside the autopilot queue.

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

## Local worker track

The share of autopilot work a local model can do is the number this track tries to
grow. Each step is measured on W1.

| # | Milestone | Question | Done when |
|---|---|---|---|
| W1 | **Worker eval — done** | Could Bonsai do the autopilot's own rounds? | 22 real cloud-worker rounds replayed at N=2: 25/44 valid requests (56.8%), 21/44 kind matches (47.7%), median 903.5 s. [Experiment](../site/series/local-worker/worker-eval.md); spec: [`autopilot/milestones/W1-worker-eval.md`](../autopilot/milestones/W1-worker-eval.md) |
| T1 | **Terminal-Bench probe** | Does Terminal-Bench 2.0 give Bonsai any signal, or is the fail rate too high? How do vanilla pi and stock omp compare, without memory? | Plan: [`bench/terminal_bench/PLAN.md`](../bench/terminal_bench/PLAN.md). 10 seeded-random TB2 tasks plus W2's 9 signal cases, both harnesses at N=1, with pass rates per task and a verdict on adopting TB2. Runs by hand on a rented GPU, not in the autopilot queue |
| W2 | **Worker harness** | Which pi and server settings close the gap? | [Candidates](#w2-candidates) each run as a worker arm on W1 against the 2026-10-12 Bonsai arm; keep what helps |
| N1 | **Mnemopi adapter** | Can oh-my-pi's Mnemopi memory engine run inside our pi harness, and what does it cost? | Spec: [`autopilot/milestones/N1-mnemopi.md`](../autopilot/milestones/N1-mnemopi.md). A pi extension over the `@oh-my-pi/pi-mnemopi` library, two arms (`mnemopi-none`: no LLM, FTS-only; `mnemopi-bonsai`: Bonsai extracts and consolidates), smoke-tested on `inventory`. Runs after W2 |
| W3 | **Passive worker memory** | Does memory let the worker survive compaction and fresh sessions? Uses the layer that wins M2 (mem0 or Mnemopi) | Auto-recall and capture keyed on the item and the round report, not the whole prompt; measured on W1 cases that span several rounds of one item |
| W4 | **Routing** | How much real work can go local? | The planner marks local-capable items; Bonsai tries them first and hands an item to the cloud worker after N failed rounds. The status page tracks the local share |

### W2 candidates

- **Thinking.** Within one worker session there is only one user message, so every
  earlier turn's thinking appears to stay in the prompt (`bench/m1-notes.md`):
  prompt growth matched tokens generated. Candidates:
  - drop thinking older than the last few turns before each request, which frees
    context for everything else;
  - a larger output limit (16k now), which that freed context can pay for;
  - llama.cpp's reasoning budget, settable per request (`reasoning_budget_tokens`,
    `reasoning_budget_message`), so it can be tested through the tap without a
    live-config change. At the budget it forces the message and the end-of-thinking
    tag, and the model carries on with its answer.
- **Tool output.** pi caps a tool result at 50 KB / 2000 lines, about 12k tokens, which
  is large for an 80k window. Try a smaller cap that tells the model where the rest
  is.
- **Editing.** pi's `edit` is exact-text replacement; 18 of Bonsai's 59 edits
  failed, and it did most work through bash (74 of 712 calls failed, 10.4%). Try
  hash-anchored line edits ("hashline", from oh-my-pi) first as a plain pi extension: several
  ports exist (e.g. `pi-hashline-edit`, `pi-hashline-context-edit`).
- **Session discipline.** Turn and time budgets in the `submit_request` extension:
  warnings first, then only that tool allowed. Smaller items when the worker is local.
- **Compaction** (M6): the reserve, and what the summary keeps.
- **Harness:** stock oh-my-pi (`omp`) as a whole-harness arm, run right after the first
  single-factor batch rather than last. It brings hashline edits natively. The earlier
  worry that its tool set and system prompt cost too much of the 80k window looks
  smaller than assumed, so the arm records the first request's prompt size for both
  harnesses and settles it. If `submit_request` doesn't run under it, the arm uses
  the JSON-fallback path.

## Milestones

| # | Milestone | Question | Done when |
|---|---|---|---|
| M1 | **N-gram speculation — done, not deployed** | Does llama-server's n-gram self-speculation speed up real agent and memory traffic, including when both slots are busy? | Replayed recorded agent and rebuilt mem0 traces on :8089, one and two slots busy. Default `ngram-mod` was slower at production sampling with two slots (agent 26.7 vs 31.3 tok/s; mem 23.4 vs 25.4), changed outputs, and was not deployed. |
| M2 | **Continuity suite** | Does mem0's win hold beyond one hand-built task, does it depend on which mem0, and does Mnemopi do as well? | 6 cross-session tasks, `baseline` vs `mem0` vs `mem0-server` vs `mnemopi-none` vs `mnemopi-bonsai`, N=5; per-task and pooled pass rates with spread. Include ≥2 *knowledge-update* tasks, where a step 1 fact is changed in step 2. Spec: [`autopilot/milestones/M2-continuity.md`](../autopilot/milestones/M2-continuity.md) |
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

Implemented in [`autopilot/`](../autopilot/README.md). A worker model does the
work in a sandbox: Bonsai until 2026-10-12, then a cloud model (Claude Sonnet 5.5, then GPT-5.6 Terra), until the
local worker track brings Bonsai back. A cloud advisor (`openai-codex/gpt-5.6-sol` via pi since 2026-10-12, before that Claude Opus; swappable) plans,
reviews every request and fact-checks write-ups. Deterministic code runs the
probes and evals, enforces protected paths, and publishes. Live-server changes go
through `autopilot/infra.py`:
- the change is applied under a GPU lease;
- it is health-checked and speed-checked, and rolled back on failure;
- it becomes known-good only after a soak period.

An item that runs out of rounds or reviews is triaged by the advisor: accepted
with caveats, re-planned, or blocked for the user. It is never silently dropped.
If the local model goes down, a cloud fixer takes over. Progress is published to
the site's autopilot status page.

M1 (n-gram speculation) was the first milestone and test case: it measured the
live-server candidate and rejected deployment. W1 (worker eval) is complete; W2
(worker harness) is running for the local-worker track. Milestones run in the order
of `milestones` in `autopilot/config.json`, and each needs a spec in
`autopilot/milestones/<name>.md`.

### Throughput estimate

One sequence on one arm takes about 8 min, so M2 (6 tasks × 3 arms × N=5) is about
12 GPU-hours. M1 is about 2 GPU-hours of replays.
