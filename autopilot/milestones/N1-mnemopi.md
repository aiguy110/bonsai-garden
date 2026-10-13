# N1: Mnemopi adapter

## Question

oh-my-pi ships a local memory engine, Mnemopi (`@oh-my-pi/pi-mnemopi`, MIT, a
TypeScript port of Mnemosyne). Can it run inside our pi harness as a memory layer
for the continuity suite, what does it cost per step, and does it behave sensibly?
N1 builds and smoke-tests the arms. M2 measures them.

## What is already known

From the package's README and omp's docs
(`docs/mnemosyne-memory-backend.md` in `can1357/oh-my-pi`); verify each against the
installed source before relying on it:

- A library: `new Mnemopi({dbPath, bank, ...})` with `remember`, `recall`, `stats`,
  `sleep` and `close`. A CLI and MCP tool definitions also exist. The omp wrapper adds
  project scoping (global, per-project, per-project-tagged) on top.
- Storage is one SQLite file (`dbPath`, or `MNEMOPI_DATA_DIR` / `MNEMOPI_DB_PATH`).
- Embeddings: local `fastembed` (the library default `BAAI/bge-small-en-v1.5`; omp
  defaults to `bge-base-en-v1.5`), an OpenAI-compatible endpoint, or none
  (`noEmbeddings`, FTS-only). Local embeddings run in a child process; omp's detached
  embed server exits after 15 min idle, and two omp processes once duplicated an
  embedding rebuild.
- LLM work (fact extraction, "sleep"/consolidation) goes through `llmMode`: the host's
  model, a remote OpenAI-compatible endpoint, or `none` (deterministic heuristics).
  The package bundles no local model.
- omp's defaults: retain after agent turns at most every 4 turns; recall into a
  `<memories>` block on the first model turn of a session (8 memories, ~5000
  tokens); tools `recall`, `retain`, `reflect`, `memory_edit` (update, forget,
  invalidate). That 5000-token default is large for our 80k window.
- No automatic contradiction handling was found; the agent must `memory_edit` or
  invalidate. M2's knowledge-update tasks test exactly this.
- The package is a Bun/TypeScript port. Bun 1.4.3 is installed at `~/.local/bin/bun`.
  Whether it also runs under Node, which pi uses, is unverified; if it doesn't, run
  the library under Bun and have the extension talk to it over stdio or a local socket.
- No controlled no-memory baseline exists upstream (can1357/oh-my-pi issue #10276
  asks for one).

## Material

- `evals/arms/mem0.json`, `evals/arms/mem0-server.json`, `evals/run.py`, and the
  `@amaster.ai/pi-memory-mem0` extension: how a memory layer is wired into a pi step,
  how the tap meters memory-LLM traffic (`llm.mem`), and the arm format. Arm files
  are immutable once they have a real record.
- `docs/benchmark-plan.md`, `evals/README.md`: run rules and the per-step record.
- The CPU embedder (`serving/`) and the `bonsai-mem` virtual model: the local
  embedding and memory-LLM endpoints.

## Constraints

- Do not edit `autopilot/`, the live llama-swap entry, turnstile or `evals/arms/`
  files that already have results. Do not `npm install` or run package install
  scripts on the host; pack with `--ignore-scripts`, read the source, and install only
  inside the sandbox or a milestone-local directory with pinned versions and hashes.
- Anything omp-specific (the wrapper's scoping, its prompts) is reimplemented only as
  far as the arms need; say what was and wasn't copied.
- The 250 W GPU cap stays.

## Done when

1. A recon note (`bench/results/<date>/mnemopi/recon.md`): version, license, tarball
   sha256, install scripts, runtime (Node or Bun), dependencies and their sizes, and
   verbatim source excerpts with file:line for retain, recall, the LLM calls, the
   embedding path and `memory_edit`.
2. A pi extension (a package directory under `agent/` or `evals/`, following how the
   mem0 extension is organised) that wraps the library: auto-recall at session start
   with a configurable limit (default 8 memories, ≤1500 tokens, not omp's 5000),
   retain every N turns and at session end, and the `recall`, `retain` and
   `memory_edit` tools. Data lives in the run directory, one bank per run.
3. Two arm files, `evals/arms/mnemopi-none.json` (`llmMode: none`, `noEmbeddings` so
   recall is FTS-only) and `evals/arms/mnemopi-bonsai.json` (Bonsai on `bonsai-mem`
   does extraction and consolidation through the tap; embeddings from the CPU
   embedder or fastembed, whichever the recon shows works headless). Each has a
   stated hypothesis. If something blocks an arm (for example no Node support), build
   the smallest thing that unblocks it, or record the blocker and what it would take.
4. A smoke test of each arm on `inventory`, N=1, run under turnstile. Report per step:
   memories written, memories recalled and injected (tokens), memory-LLM tokens
   (`llm.mem`), added wall time, and pass/fail per check. Check the data dumps for
   what was actually stored.
5. A short experiment page (`site/AUTHORING.md`) covering what Mnemopi is, how it was
   wired, its defaults versus ours, and the smoke results, marked as plumbing
   (N=1), not a result. `python3 bench/check_site.py` passes.
