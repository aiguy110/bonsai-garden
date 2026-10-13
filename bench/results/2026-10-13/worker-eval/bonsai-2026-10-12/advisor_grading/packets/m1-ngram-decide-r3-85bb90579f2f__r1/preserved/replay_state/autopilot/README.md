# autopilot

Pursues the roadmap (`../docs/roadmap.md`) unattended. Bonsai does the hands-on
work, a cloud model advises at gates, and deterministic code enforces the rules.
Progress is published to the site's [autopilot status page](https://aiguy110.github.io/bonsai-garden/autopilot.html).

```
autopilot.py (systemd user service, runs from the main checkout)
  ├─ worker   pi on bonsai-agent (turnstile, bench key, priority 20) in the eval Docker
  │           sandbox: no network, no GPU, sees only the milestone's worktree
  ├─ advisor  pi on meridian/claude-opus-5-5, read-only tools: plans, reviews every
  │           request and finished item, fact-checks the write-up
  ├─ fixer    pi on meridian/claude-opus-5-5 with a shell: only when the local model is
  │           down and rollback didn't help
  └─ infra.py transactional live-config changes: lease, back up, restart, health-check,
              roll back
```

Roles are pi model strings in `config.json`. To swap the advisor, edit the string
(any pi provider works). Meridian (`meridian.service`, :3456) serves Claude through
the Claude Code SDK. The advisor's pi agent dir is `.cache/agent-cloud`, which has
`pi-meridian-extension`.

## The loop

Each milestone is `milestones/<name>.md` and runs on branch `auto/<name>` in
`~/Projects/bonsai-garden-auto/<name>`.

1. **plan:** the advisor writes 3–6 items with acceptance criteria (`state/<m>/plan.json`).
2. **work:** each round is one fresh worker session, given the milestone, plan, item
   and journal. The journal is its memory between sessions. The session ends with a
   request:
   - `run`: a script under `bench/` or `evals/`. The advisor reviews it, then it runs
     on the host, under a GPU lease if `gpu`. The output is saved under
     `bench/results/<date>/autopilot/`.
   - `infra`: an entry file under `serving/candidates/`. The advisor reviews it, then
     `infra.py apply` runs.
   - `done`: the advisor checks the acceptance criteria. If it approves, the next
     item starts.
   - `continue` or `stuck`: just another round.

   Edits to protected paths (`config.json`) are reverted after every session. An
   item is dropped after 8 rounds or 3 failed reviews.
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

Cloud calls are capped at `cloud_calls_per_day` (25). When the cap is reached,
work pauses until the next day.
