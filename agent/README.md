# pi wiring

- `~/.pi/agent/models.json` provider `llama-swap` has the `bonsai-2-27b` entry
  (copy: `models.bonsai-2-27b.json`), and it's in `settings.json` `enabledModels`.
- Memory extension candidates, to be evaluated in this order:
  1. `@mem0/pi-agent-plugin`, the official plugin. Confirm it can target a
     self-hosted mem0 rather than the hosted platform.
  2. `@amaster.ai/pi-memory-mem0`, which advertises a self-hosted mode.
  3. A thin local extension here, using recall before the turn and capture
     after it.
- Benchmark arms toggle the extension per run, so the arm config, not global pi
  settings, decides whether memory is on.
