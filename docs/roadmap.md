# Roadmap

Status as of 2026-10-11: serving is done (two slots, turnstile co-admission). One
memory eval has run: 1 task, N=3, mem0 2/3 vs baseline 0/3. That is suggestive,
not a result.

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
  (no memory) or `mem0`.
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
| M2 | **Continuity suite** | Does mem0's win hold beyond one hand-built task? | 6 cross-session tasks, `baseline` vs `mem0`, N=5; per-task and pooled pass rates with spread. Include ≥2 *knowledge-update* tasks, where a step 1 fact is changed in step 2 |
| M3 | **Regression guard** | Does memory hurt tasks that don't need it? | 12 single-session tasks run with a pre-filled, *irrelevant* memory store vs baseline; no significant drop |
| M4 | **Other memory layers** | Is mem0 the right design for a small local model? | Arms below, run on the M2 suite and M3 guard; pass rate vs memory-LLM tokens per step |
| M5 | **Cheaper memory writes** | Can the ~8k-token prefill per mem0 write be cut? | Variants of capture (per turn vs end of session), a shorter extraction prompt, recall top-k; cost vs pass-rate curve |
| M6 | **Long-horizon / compaction** | Within one session, does memory beat compaction alone? | 4 tasks that force compaction; pi default vs memory-backed compaction |
| M7 | Memory-only eval (optional) | Isolate retrieval quality from agent skill | LoCoMo-style subset |

Rules from `benchmark-plan.md` apply throughout. New arms never edit old ones.
Every result updates its experiment, series and project pages.

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

Bonsai does the work. A larger model reviews at a few gates. Deterministic code
runs the evals and enforces the rules.

```
autopilot (Python, systemd user timer)
  ├─ worker:  pi -p on bonsai-agent, in the eval Docker sandbox, on branch auto/<milestone>
  │           drafts tasks, checkers, arms, analysis and site pages
  ├─ runner:  evals/run.py + summarize.py + check_site.py, plus bench/ probes (no LLM)
  └─ advisor: pi -p --model meridian/claude-opus-5-5, read-only tools, called at gates
```

The advisor is a pi model string routed through
[meridian](https://github.com/rynfar/meridian), a local proxy that serves Claude
through the Claude Code SDK. Swapping the advisor means changing that string, e.g.
to a hosted API model or a bigger local one. The orchestration doesn't change.

### Loop per milestone

1. **Plan.** The advisor turns the milestone row into a short work list (tasks to
   write, arms to add, probes to run), committed to `autopilot/state/`.
2. **Build.** The worker produces one item at a time, e.g. a task, an arm or
   extension, or a probe script. Tasks must pass the sanity gate.
3. **Review gate.** The advisor reads the diff. It looks for answer leakage,
   checkers that test the wrong thing, and tasks that need no memory. It returns
   approve, or revise with notes. After 3 rounds the item is dropped and logged.
4. **Run.** The runner executes the work. Runs resume after interruption, use
   priority 20 and yield to interactive use.
5. **Analyze.** The worker drafts the experiment page from the raw results. The
   advisor checks every claim against the numbers.
6. **Publish.** `check_site.py` passes, then merge to `main` and push (this updates
   the site).

### Guardrails

- No live-stack changes (llama-swap, turnstile, pi's `models.json`). Those become a
  proposal for the user. M1's deploy step is one.
- The worker has no network except the tap. It writes only to its branch worktree.
- Eval agents never see authoring material: known-good workspaces and advisor notes
  stay outside the sandbox.
- Advisor call budget: 25/day by default. Every verdict is logged, so the worker's
  rejection rate becomes a result too.
- A daily digest goes to the user. Kill switch: `systemctl --user stop bonsai-autopilot`.

### Throughput estimate

One sequence on one arm takes about 8 min, so M2 (6 tasks × 2 arms × N=5) is about
8 GPU-hours. M1 is about 2 GPU-hours of replays.
