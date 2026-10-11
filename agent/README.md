# pi wiring

- `~/.pi/agent/models.json` provider `llama-swap` has the `bonsai-2-27b` entry
  (copy: `models.bonsai-2-27b.json`) and the virtual `bonsai-agent` entry
  (`models.bonsai-agent.json`, pi's default model). Both are in `enabledModels`.
- `~/.pi/agent/extensions/llama-swap-discover.ts` rebuilds the provider's model list
  from llama-swap; it keeps models.json entries llama-swap doesn't serve, which is
  how `bonsai-agent` stays visible.

## Memory extension: `@amaster.ai/pi-memory-mem0` (chosen 2026-10-11)

| Candidate | Verdict |
|---|---|
| `@mem0/pi-agent-plugin` 0.3.2 (official) | **No.** Only talks to the hosted Mem0 platform (`new MemoryClient({apiKey})`, no host or OSS option) and sends PostHog telemetry. |
| `@amaster.ai/pi-memory-mem0` 0.1.24 | **Yes.** `embedded` mode runs mem0 OSS in-process with any OpenAI-compatible LLM and embedder (explicit `apiKey`/`baseURL` bypass pi's registry), a SQLite vector store, and separate switches for auto-capture, auto-recall, and the `mem0_memory` tool, which map directly onto benchmark arms. Recalled memories go in as a user-channel message marked untrusted, not into the system prompt. |
| Thin local extension | Not needed yet. |

Behaviour worth knowing when reading results:
- **Capture** happens on the first assistant turn that has text after each user
  input: it sends that user prompt plus that assistant text to mem0 (`add`). Later
  turns of the same run, including the final summary, are not captured.
  `session_shutdown` waits for pending writes, so `pi -p` doesn't lose them.
- **Recall** runs a search on each user input and injects the top `topK` hits
  before the agent starts.
- Memories are namespaced by `userId` and a hash of the cwd, so one workspace is
  one memory pool.
- mem0 OSS sends telemetry unless `MEM0_TELEMETRY=false` (the arms set it).
- mem0 sends no `temperature` or `max_tokens`, so turnstile's `bonsai-mem` injects
  `temperature: 0.2` and `max_tokens: 2048`.

To use it interactively, `pi install npm:@amaster.ai/pi-memory-mem0@0.1.24` and copy
the `pi-memory-mem0` block from `evals/arms/mem0.json` into `~/.pi/agent/settings.json`,
pointing `baseURL` at `http://127.0.0.1:8080/v1` with the `bonsai-garden-mem` key and
choosing a durable `dbPath`. This isn't done; the global pi config has no memory.
