# bonsai-garden architecture (target)

```
pi (agent) ──┐                                      ┌─ slot 0: agent  (long ctx, deep)
             ├─> turnstile :8080 ─> llama-swap ─> llama-server "bonsai-2-27b"
mem0 ────────┘   (key: pi / garden)               └─ slot 1: memory (short prompts)
  │                                                  one weights copy, unified q4_0 KV
  ├─ embedder: small embedding GGUF on CPU (stock llama.cpp --embeddings, own port, no GPU)
  └─ vector store: Qdrant embedded mode (on-disk path, no service)
```

## Components

| Role | What | Notes |
|---|---|---|
| Agent LLM | virtual `bonsai-agent` → `bonsai-2-27b` slot 0 via turnstile | pi provider `llama-swap`, key `pi` (prio 40), pi default model |
| Memory LLM | virtual model `bonsai-mem` (same weights), slot 1 | Used for fact extraction, update/dedup decisions, and retrieval rewriting. Turn reasoning off or low per request (`chat_template_kwargs`), because these are short JSON tasks |
| Embeddings | CPU embedder (candidate: Qwen3-Embedding-0.6B GGUF) | Bonsai is not an embedding model. Keeping this on the CPU leaves GPU headroom alone |
| Vector store | Qdrant local path under `memory/data/` (gitignored) | |
| Memory API | mem0 OSS, as a library or self-hosted REST, configured by `memory/mem0.config.yaml` | |
| pi integration | a pi extension that recalls before a turn and captures after it | Candidates: `@mem0/pi-agent-plugin` (official; check whether it supports self-hosted mode) or `@amaster.ai/pi-memory-mem0` (claims self-hosted mode). Fall back to a thin local extension in `agent/` |

## Request tagging

Done by turnstile virtual models (engine-review §4c, deployed 2026-10-11): pi asks
for `bonsai-agent` (pinned to slot 0), mem0 asks for `bonsai-mem` (slot 1,
thinking off, 12k max context). Both resolve to `bonsai-2-27b`, so they co-run
instead of evicting each other. Metering for benchmarks (per-role tokens,
`prompt_n`/`cache_n`, latency) is `evals/tap.py`, a pass-through in front of
turnstile; it no longer needs to rewrite anything.

## Priority choice

The memory capture runs after a turn, and the memory recall runs before one. Both
sit on the agent's critical path, so give memory calls the **same tier as the agent**
(new key `bonsai-garden-mem`, priority 40). A lower tier would let unrelated
tier-30/20 work slip in between an agent turn and its recall.

## Open questions

- Does the pi mem0 plugin support a self-hosted base URL and local embedder?
- ~~Does `id_slot` survive llama-swap and the OAI chat endpoint?~~ Yes.
- Should memory capture be async (now possible: co-admission lets it run next to the
  agent's next turn) or synchronous? Measure both as arms.
