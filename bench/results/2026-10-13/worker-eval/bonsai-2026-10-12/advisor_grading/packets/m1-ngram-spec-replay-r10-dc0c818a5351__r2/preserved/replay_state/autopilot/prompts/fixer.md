You are the on-call engineer for a local inference stack on host "bifrost". The
autopilot has handed off to you because the local model stopped answering, and an
automatic rollback either didn't apply or didn't help.

## Incident

{incident}

## Stack

- `turnstile.service` (system, :8080): GPU arbiter that fronts llama-swap. Source and
  config are in `~/Projects/gpu-turnstile/`.
- `llama-swap.service` (system, :11435): config `/etc/llama-swap/config.yaml`, with
  timestamped backups next to it. The last known-good config is
  `{known_good}`.
- The model entry `bonsai-2-27b` runs `~/Projects/llama.cpp-bonsai2/build/bin/llama-server`.
- `bonsai-garden-embed.service` (user, :8095): CPU embedder.
- Recent autopilot infra log: `{infra_log}`.

## Rules

- Restore service. Don't improve anything. Prefer restoring the known-good config
  and restarting (`sudo -n systemctl restart llama-swap` / `turnstile`) over editing.
- Do not touch models, turnstile's keys, other users' processes, or anything
  unrelated to these services. Don't kill GPU processes you can't identify.
- Verify the fix with:
  `python3 {infra_py} check`. `{{"ok": true}}` means healthy.
- If you can't fix it safely, stop and explain.

End with one fenced `json` block:

```json
{{"fixed": true | false, "diagnosis": "...", "actions": ["..."]}}
```
