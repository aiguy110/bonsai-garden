# autopilot

Pursues the roadmap (`../docs/roadmap.md`) unattended. A worker model does the
hands-on work, a cloud model advises at gates, and deterministic code enforces the rules.
Progress is published to the site's [autopilot status page](https://aiguy110.github.io/bonsai-garden/autopilot.html).

```
autopilot.py (systemd user service, runs from the main checkout)
  ├─ worker   pi on openai-codex/gpt-5.6-terra (or meridian/…, garden/…) in the eval
  │           Docker sandbox: no network, no GPU, sees only the milestone's worktree
  ├─ advisor  pi on openai-codex/gpt-5.6-sol (or meridian/…), read-only tools: plans, reviews every
  │           request and finished item, fact-checks the write-up
  ├─ fixer    pi on meridian/claude-opus-5-5 with a shell: only when the local model is
  │           down and rollback didn't help
  └─ infra.py transactional live-config changes: lease, back up, restart, health-check,
              roll back
```

Roles are pi model strings in `config.json`. To swap the advisor, edit the string
(any pi provider works). Meridian (`meridian.service`, :3456) serves Claude through
the Claude Code SDK. The advisor's pi agent dir is `.cache/agent-cloud`, which has
`pi-meridian-extension`. An `openai-codex/<id>` advisor gets the Codex CLI's token
through the environment (`CODEX_TOKEN`, named in the agent dir's `models.json`).
Since 2026-10-12 10:30 the advisor is GPT-5.6 Sol (thinking `high`) and the fixer is
still Claude Opus.

The worker is `garden/<id>` (Bonsai through turnstile, bench key, priority 20),
`meridian/<id>` or `openai-codex/<id>`. A cloud worker still has no network; the
sandbox's tap gets one extra route:
- `meridian`: to :3456. The worker loads the extension's source as a plain extension
  file, patched to know `claude-sonnet-5-5`.
- `codex`: to `https://chatgpt.com/backend-api`, only `/codex/responses`, over SSE.
  This is pi's built-in ChatGPT-subscription provider. The tap adds the Codex CLI's
  access token (`~/.codex/auth.json`, read each session) on the host. The sandbox
  only gets a placeholder carrying the account id. Only the CLI refreshes the token:
  if it is about to expire, the tick fails until `codex` has been run once.

Worker calls don't count against `cloud_calls_per_day`. When the worker or advisor
hits a subscription rate limit, the loop pauses (up to an hour, using the
`retry_after` it is given), and the failed session doesn't count as a round.

History: Bonsai was the worker until 2026-10-12 and mostly failed to end its sessions
(timeouts, context overflows, cut-off replies). Then `meridian/claude-sonnet-5-5`
took over, and from 2026-10-12 10:30 `openai-codex/gpt-5.6-terra` (thinking
`medium`), to keep the Claude limit for the advisor. To go back to Bonsai, set the
worker to `garden/bonsai-agent` with thinking `low`.

## The loop

Each milestone is `milestones/<name>.md` and runs on branch `auto/<name>` in
`~/Projects/bonsai-garden-auto/<name>`.

1. **plan:** the advisor writes 3–6 items with acceptance criteria (`state/<m>/plan.json`).
2. **work:** each round is one fresh worker session, given the milestone, plan, item,
   standing facts and journal tail. The session ends when the worker calls the
   `submit_request` tool (`extensions/submit_request.ts`, copied into the worker's
   agent dir). The tool checks the request on the spot, so a malformed one comes
   back as an error the worker can fix in the same session. A fenced `json` block at
   the end of the final message still works as a fallback. Requests:
   - `run`: a script under `bench/` or `evals/`. The advisor reviews it, then it runs
     on the host, under a GPU lease if `gpu`. The output is saved under
     `bench/results/<date>/autopilot/`.
   - `infra`: an entry file under `serving/candidates/`. The advisor reviews it, then
     `infra.py apply` runs.
   - `done`: the advisor checks the acceptance criteria. If it approves, the next
     item starts.
   - `continue`: just another round.
   - `stuck`: triage (below).

   Edits to protected paths (`config.json`) are reverted after every session.

   **Triage.** When an item uses all 12 rounds, fails review 3 times, or the worker
   is stuck, the advisor decides (`prompts/triage.md`). Work is cumulative, so what
   the item built stays in the repo either way:
   - `accept_with_caveats`: the item counts as done. Its unmet criteria go into the
     standing facts, and the status page marks it ⚠️.
   - `replan`: new items replace this one and the rest of the plan. Allowed twice
     per plan position; after that, only accept or block.
   - `block`: a human has to act. `unblock` then gives the item fresh rounds.

   **Memory.** Two kinds outlive a session:
   - The journal (`state/<m>/journal.md`). Prompts include only its last 15k
     characters.
   - The standing facts (`state/<m>/facts.md`). Corrections and caveats that the
     advisor adds in reviews and triage. Every worker and advisor prompt includes
     them in full.

   With `worker_memory` set to an eval arm name (`"mem0"`), the worker also gets that
   arm's pi-memory-mem0 in `active` mode: the `mem0_memory` tool, with no automatic
   capture or recall. The store is per milestone, in `.runtime/memory/<m>`. Set
   `worker_memory` to `null` to turn it off.
3. **publish:** the last item is the write-up. It needs `check_site.py` to pass and
   the advisor's fact-check. Then the branch is merged into `main` from a separate
   publisher worktree and pushed, which deploys the site.

## The local model changing its own server

Bonsai runs on the `bonsai-2-27b` entry it may change. `infra.py` makes that safe:

- **Scope:** the candidate may change only that entry's server flags. The model,
  mmproj, port and env lines must stay byte-identical. The full config never enters
  the repo: entries are spliced into `/etc/llama-swap/config.yaml`.
- **Apply under a turnstile lease,** so nothing else is mid-request. Back up, write,
  restart llama-swap. Health-check directly on :11435: a correctness probe, then
  decode speed with both slots busy. Speed must be ≥ 80% of the recorded baseline.
  Otherwise the previous config is restored on the spot.
- **Soak:** a change becomes known-good only after 3 healthy worker sessions. Before
  each session, a health check runs through turnstile. If one fails during the
  soak, the change is rolled back automatically.
- **Hand-off:** if the local model is down and no rollback applies (or it didn't
  help), the cloud fixer gets the incident and a shell. If that fails too, the
  milestone is marked blocked and the status page says so.

## Operating

```bash
python3 autopilot/autopilot.py status     # where things are
python3 autopilot/autopilot.py tick       # one step by hand
python3 autopilot/autopilot.py unblock    # after fixing whatever blocked it
python3 autopilot/infra.py check          # is the local model answering?
python3 autopilot/infra.py baseline       # re-measure and save known-good
systemctl --user stop bonsai-autopilot    # kill switch
```

To edit `state/<m>/status.json` by hand, stop the service first and commit the edit
in the milestone worktree. Changes under `autopilot/` made during a worker session
are reverted as protected-path edits.

Cloud calls are capped at `cloud_calls_per_day` (30). When the cap is reached,
work pauses until the next day.
