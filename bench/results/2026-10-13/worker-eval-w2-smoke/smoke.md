# W2 smoke run

Source: bench/results/2026-10-13/worker-eval-w2-smoke

| arm | record.json | extension load errors | mechanism evidence | ok |
|---|---|---|---|---|
| bonsai-2026-10-12-honest | yes | none | 0 ext lines | yes |
| w2-reasoning-budget | not run | - | - | - |
| w2-smoke-hashline | yes | none | tools sourced from the hashline package: ['edit', 'read']; read/edit calls {'read': 2} | yes |
| w2-smoke-reasoning-budget | yes | none | 6 requests, fields ['reasoning_budget_message', 'reasoning_budget_tokens'], budget message in a thinking block: True | yes |
| w2-smoke-session-budget | yes | none | 2 warn, 1 block events | yes |
| w2-smoke-think-drop | yes | none | 11 strips, removed_chars total 192855 | yes |
| w2-think-drop | yes | none | 16 strips, removed_chars total 441255 | yes |

## Notes

- Load errors: stderr.txt is grepped for the exact pi string `Failed to load extension` (loader.js:331). events.jsonl is not grepped
  (the model's own text could match). All stderr.txt files were empty.
- Hashline: the package overrides `read` and `edit` under the built-in names, so load is confirmed from tool_audit's source path
  (`.../pi-hashline-context-edit@0.11.0/index.ts`) for both, not from a tool name.
- Reasoning budget: tap.jsonl keeps no request bodies, so receipt by the server is shown only indirectly: the budget message
  appears inside thinking blocks in events.jsonl (the 256 variant). The ext.jsonl lines show what was sent.
- Smoke arm descriptions/sources are inaccurate in places (think-drop says 'last 2' but keep_last is 1; session-budget text says 12/16 min
  though the smoke thresholds are 0.5/1/1.5 min; hashline says 'same as w2-hashline'; sources say 20 min; the prompt says 20 min while the
  limit is 8). Correcting those files changes the arm hashes.
- The real-arm records in this dir (honest, w2-think-drop) are N=1 on one case and must not be used in any comparison. w2-reasoning-budget,
  w2-session-budget, w2-hashline and w2-compaction did not run (budget ran out).

