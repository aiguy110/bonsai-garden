# Phase B runbook: turnstile co-admission, context budget, virtual models

For a fresh agent. Read `docs/engine-review.md` §2 and §4 first (the design and the
measurements behind it), then do Phase A (`docs/phase-a-runbook.md`) or confirm it
is done: Phase B is only useful against a multi-slot `bonsai-2-27b`.

The work happens in a **different repo**: `~/Projects/gpu-turnstile` (Go 1.26, module
`github.com/aiguy110/gpu-turnstile`, public at https://github.com/aiguy110/gpu-turnstile). Read
its `README.md`, `internal/types/doc.go` (wiring contract + scheduler policy), and
the `gpu-turnstile` skill before editing. Record outcomes back in this repo.

## Goal

Three features, in this order. Each is independently useful and testable.

1. **Co-admission** (§4a): several LLM requests for the *same* warm model run at
   once, up to the model's slot count.
2. **Context budget** (§4b): co-admission also requires that the in-flight requests'
   estimated tokens fit the server's context pool.
3. **Virtual models** (§4c): several client-facing names map to one real
   llama-swap model, each with its own `max_ctx` and injected request fields.

Everything is backward compatible: a model with no `models:` entry behaves exactly
as today (1 slot, no budget), and leases are unchanged (exclusive).

## Config schema (add to `types.Config`, `config.example.yaml`, and README)

```yaml
models:                     # optional; keyed by the real llama-swap model name
  bonsai-2-27b:
    slots: 2                # max concurrent LLM requests (default 1)
    ctxPool: 98304          # server -c value; 0 = no budget accounting
virtual:                    # optional; keyed by the client-facing name
  bonsai-agent:
    backend: bonsai-2-27b   # must exist in models:
    maxCtx: 81920           # reject if est. prompt + max_tokens exceeds this; 0 = none
  bonsai-mem:
    backend: bonsai-2-27b
    maxCtx: 12288
    defaultMaxTokens: 1024  # used for budgeting when the request sets none
    inject:                 # merged into the JSON body
      chat_template_kwargs: { enable_thinking: false }
```

Validate at load (return an error, no `os.Exit`): `backend` exists, `slots >= 1`,
`maxCtx <= ctxPool`, and no virtual name equals a real model name.
Check the exact reasoning switch against Bonsai's chat template
(`enable_thinking` is the Qwen convention; confirm it works on this fork).

## Design decisions (settled; deviate only with a reason, and document it)

- **Where:** rewriting and `maxCtx` rejection happen in `internal/proxy` before
  `Acquire`. Admission and the budget live in `internal/queue`. Keep `types` as the
  only shared dependency (see its package comment).
- **Rewrite:** replace the top-level `model` with the backend name, then merge
  `inject` into the body. `inject` wins over client values; maps merge recursively
  (so a client's other `chat_template_kwargs` survive). Fix `Content-Length`
  (`restoreBody` already does this). `AcquireSpec.Model` carries the **real** name,
  so eviction and warm tracking work by real name. Add `AcquireSpec.Alias` (the
  virtual name) for display, and put it in the activity record so the console and
  benchmarks can tell agent from memory.
- **Token estimate:** `prompt_tokens ≈ ceil(chars/3)` over message contents, tool
  definitions, and `input`, deliberately pessimistic (~3 chars/token). Optionally
  call llama-server's `/tokenize` later for exact counts. `max_tokens` comes from
  `max_tokens` or `max_completion_tokens`, else the virtual model's
  `defaultMaxTokens`, else `ctxPool - prompt` (so an unbounded request is
  budgeted as the rest of the pool). Bodies over the 4 MiB peek limit are budgeted
  as the whole pool (they run alone).
- **Rejection:** if `prompt + max_tokens > maxCtx`, answer 400 with an OpenAI-style
  error (`code: context_length_exceeded`) and never touch the queue.
- **Scheduler:** replace the single `holder *ticket` with a set of holders (all
  `KindLLM` of one model, or exactly one `KindLease`). `tryAdmit` takes the front
  waiter (priority desc, FIFO, unchanged). If it is an LLM request for the warm
  model and `len(holders) < slots` and `sum(holder tokens) + its tokens <= ctxPool`,
  grant it without eviction. Otherwise it waits for the holders to drain; **do not
  skip ahead to a smaller waiter** (that would starve big requests and break the
  "no request while higher priority pending" rule). A lease or a different model
  still requires an empty GPU and the existing eviction rules, which also keep
  working with several holders: `lastLLMComplete` and `warmTier` update when a
  request completes. `handlePreemption` only ever targets a lease holder, and LLM
  holders are still never revoked.
- **Snapshot/console:** keep `QueueSnapshot.Holder` (first holder) for existing
  clients and add `Holders []TicketStatus`. Update the web console to show all
  holders. History records are per hold and need no change.
- **Observability:** log `joined` (with holders count and budget used) next to
  `granted`, and a `deferring: context budget` line when a waiter is blocked on
  tokens.

## Steps

Work on a feature branch in the turnstile repo (`git switch -c virtual-models`).

1. **Tests first** in `internal/queue/queue_test.go` (it has a fake clock and
   fake evictor; follow `TestEqualTierDifferentModelEvictsImmediately`):
   - second same-model request is granted while the first is held (slots 2);
   - third waits until one releases; FIFO is kept;
   - a higher-priority different-model waiter blocks further joins and evicts
     after holders drain;
   - a lease waits for all LLM holders, then runs alone;
   - budget: two requests that don't fit together don't co-run; a small one behind a
     big blocked front waiter does not jump the queue;
   - `slots` unset behaves exactly as before (rerun the existing suite unchanged).
2. **Co-admission** in `internal/queue` (holders set, `tryAdmit`, snapshot).
3. **Budget:** `AcquireSpec.CtxTokens`, accounting in `tryAdmit`.
4. **Config + validation** in `types.Config` and `cmd/turnstile/main.go`
   (`loadConfig` is where defaults live); thread the models/virtual maps to
   `proxy.NewObserved` (this changes the frozen constructor signature, so update
   `doc.go` and the tests in the same commit).
5. **Proxy rewrite/inject/estimate/reject** in `internal/proxy` (`parseRequest` and
   `peekRequestAndRestore` are the hooks). Tests in `proxy_test.go`: rewrite,
   deep-merge, `Content-Length`, estimate, 400 on overflow, oversized-body path,
   model with no virtual entry passes through untouched.
6. **Console:** show all holders and the alias; fix `internal/web` tests.
7. `go vet ./... && go test ./... -race` must pass.

## Deploy (needs the user's go-ahead)

Restarting turnstile cuts any in-flight proxied stream (pi, hermes), so ask first
and prefer a quiet moment (`curl -s localhost:8080/api/queue`).

```bash
cd ~/Projects/gpu-turnstile
cp config.yaml config.yaml.bak.$(date +%s)    # gitignored; has real keys
# add the models:/virtual: blocks (above) to config.yaml
go build -o ~/.local/bin/turnstile ./cmd/turnstile
systemctl --user restart turnstile && journalctl --user -u turnstile -n 20
```

Also mint a key for memory calls if you want it distinct (same priority as the
agent, see `docs/architecture.md`; add it to `config.yaml`, which is the seed of
record).

## Validate end to end

1. With the 2-slot server loaded, send two simultaneous streaming requests through
   `:8080`, one as `bonsai-agent` and one as `bonsai-mem`. Both should be granted
   together (`joined` in the journal, two holders in `/api/queue`) and each should
   stream at ~45 tok/s (compare `bench/results/2026-10-10/`).
2. `bonsai-mem` with thinking injected off returns no `reasoning_content`.
3. A request over `maxCtx` gets the 400; a pair of requests whose budgets exceed
   the pool run one after the other.
4. A tier-30 lease arriving mid-stream waits for both LLM holders, then runs
   (existing behaviour, but check it with two holders).
5. Test whether an injected `id_slot` is honored through llama-swap and the OAI
   endpoint. If it is, pin agent to slot 0 and memory to slot 1 via `inject`; if
   not, record it and rely on `--slot-prompt-similarity`.

## After it works

- Point pi at `bonsai-agent` (its `models.json` `id`, `contextWindow` = `maxCtx`)
  and mem0 at `bonsai-mem` (now `evals/arms/mem0.json`); update `agent/README.md` and
  `docs/architecture.md` (drop the tagging shim).
- Add measured results to `docs/engine-review.md`, add a dated dir under
  `bench/results/`, and commit and merge per `CLAUDE.md` here.
- In the turnstile repo, merge the branch to `main`, push, and update the
  `gpu-turnstile` skill (`~/.claude/skills/gpu-turnstile/SKILL.md`) with the new
  config and the multi-holder behaviour.

## Known unknowns

- Whether llama-swap or llama-server mishandle extra body fields from `inject`.
- Estimator accuracy: log estimate vs the response's `usage.prompt_tokens` for a
  while and tune the chars/token ratio, or switch to `/tokenize`.
- Whether pi surfaces the 400 `context_length_exceeded` as an overflow it compacts
  on, or as a hard error. Test with a long session.
