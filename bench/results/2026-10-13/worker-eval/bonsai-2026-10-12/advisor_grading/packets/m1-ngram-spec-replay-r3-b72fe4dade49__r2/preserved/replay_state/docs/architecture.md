# bonsai-garden architecture

```
pi (agent) ──┐                                      ┌─ slot 0: agent  (long ctx, deep)
             ├─> turnstile :8080 ─> llama-swap ─> llama-server "bonsai-2-27b"
mem0 ────────┘   (bonsai-agent / bonsai-mem)      └─ slot 1: memory (short prompts)
  │  (in-process in pi,                              one weights copy, unified q4_0 KV
  │   @amaster.ai/pi-memory-mem0)
  ├─ embedder: Qwen3-Embedding-0.6B on CPU (stock llama.cpp, :8095, no GPU)
  └─ vector store: mem0 OSS "memory" store = a SQLite file (no service)
```

## Components

| Role | What | Notes |
|---|---|---|
| Agent LLM | virtual `bonsai-agent` → `bonsai-2-27b` slot 0 via turnstile | pi provider `llama-swap`, key `pi` (prio 40), pi default model |
| Memory LLM | virtual model `bonsai-mem` (same weights), slot 1 | Used for fact extraction, update/dedup decisions, and retrieval rewriting. Turn reasoning off or low per request (`chat_template_kwargs`), because these are short JSON tasks |
| Embeddings | `Qwen3-Embedding-0.6B-Q8_0.gguf` on CPU, user unit `bonsai-garden-embed` (`serving/bonsai-garden-embed.service`), `:8095`, 1024-d, last-token pooling, ~60 ms/query | Bonsai is not an embedding model. `CUDA_VISIBLE_DEVICES=` keeps it off the GPU |
| Vector store | mem0 OSS `memory` provider (SQLite file, `dimension: 1024`) | Per eval run: `<run>/memory/`. Simpler than Qdrant and enough at this scale |
| Memory API | mem0 OSS JS (`mem0ai` 3.3.1), in-process inside pi | Telemetry is on by default: set `MEM0_TELEMETRY=false` |
| pi integration | `@amaster.ai/pi-memory-mem0` 0.1.24, embedded mode | Configured per arm (`evals/arms/mem0.json`). See `agent/README.md` for why not the official plugin |

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
