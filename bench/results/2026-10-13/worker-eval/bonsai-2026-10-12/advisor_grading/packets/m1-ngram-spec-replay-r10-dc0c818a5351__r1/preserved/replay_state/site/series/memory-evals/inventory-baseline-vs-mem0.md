---
layer: experiment
series: memory-evals
title: "inventory: baseline vs mem0"
status: done
date: 2026-10-11
updated: 2026-10-11
tldr: Over 3 fresh sessions, mem0 finished all steps 2/3 times vs 0/3 without memory, by recalling a spoken-only rule and a staging host the baseline had to invent.
summary: |
  **Task:** a small Python repo worked on over **3 separate sessions**. Session 1
  states four project conventions and one fact for later: staging lives at
  `staging.internal:8443`. Sessions 2 and 3 just say "follow the project
  conventions" and "as discussed before".

  **Trap:** three conventions leave visible traces in the repo. The fourth (end
  every reply with `Risk: low|medium|high`) and the staging address exist **only
  in the session 1 conversation**.

  **Result (3 repeats each):**
  - Full sequence: **mem0 2/3, baseline 0/3.**
  - Both arms rediscovered the visible conventions every time.
  - Baseline never ended with a `Risk:` line after session 1. It **invented**
    `staging.inventory.example.com` for the staging host in all 3 repeats.
  - mem0 recalled the address correctly 3/3. Its one failure was a free-text Risk
    line instead of `Risk: low`.
  - Wall time was the same for both arms.

  **Caveat:** one hand-built task, n=3. Directional, not conclusive.
---

## The task

Three prompts, each run as a separate `pi -p --no-session` in a fresh sandbox. The
repo carries over between steps; the conversation does not.

1. *"Implement `parse_qty(text)`…"* followed by:
   > Some conventions for this project. Follow them now and in every future task:
   > 1. Every public function's docstring starts with "Inventory:".
   > 2. Tests live in tests/test_&lt;module&gt;.py and use plain assert statements run by pytest. Never use unittest.
   > 3. Every change gets a one-line entry under "## Unreleased" in CHANGELOG.md, in the form "- &lt;module&gt;: &lt;summary&gt;".
   > 4. End your final message to me with a line "Risk: low", "Risk: medium" or "Risk: high" for the change.
   >
   > Also, for a later task: our staging API is served over HTTPS at staging.internal on port 8443.
2. *"Add `format_qty(grams)`… Follow the project conventions."*
3. *"Add inventory/config.py with a function staging_url() that returns the base
   URL of our staging API, as discussed before… Follow the project conventions."*

The [checker](https://github.com/aiguy110/bonsai-garden/blob/main/evals/tasks/inventory/check.py)
scores `correct`, `docstring`, `tests`, `changelog`, `risk_line`, and
`suite_green` separately. A step passes only if all of them pass.

## Results

| step | arm | pass | correct | risk line | other conventions | wall s | memory LLM calls |
|---|---|---|---|---|---|---|---|
| 1 | baseline | 3/3 | 3/3 | 3/3 | 3/3 | 185 ± 43 | — |
| 1 | mem0 | 3/3 | 3/3 | 3/3 | 3/3 | 172 ± 23 | 4 |
| 2 | baseline | **0/3** | 3/3 | **0/3** | 3/3 | 170 ± 52 | — |
| 2 | mem0 | **3/3** | 3/3 | **3/3** | 3/3 | 175 ± 13 | 1 |
| 3 | baseline | **0/3** | **0/3** | **0/3** | changelog 2/3 | 108 ± 38 | — |
| 3 | mem0 | **2/3** | **3/3** | 2/3 | 3/3 | 110 ± 16 | 1 |

Whole sequence: **baseline 0/3, mem0 2/3.**

## What it looks like in the transcripts

### Session 3, mem0: recall is injected before the agent starts

```
## Recalled Memories (Mem0)
- [UNTRUSTED MEMORY DATA] "The staging API is served over HTTPS at staging.internal on port 8443"
- [UNTRUSTED MEMORY DATA] "User's project conventions: public function docstrings start with
  'Inventory:', tests live in tests/test_<module>.py using plain assert statements with pytest
  (never unittest), every change gets a one-line entry under '## Unreleased' in CHANGELOG.md
  in the form '- <module>: <summary>', and final messages must end with a risk assessment
  line ('Risk: low', 'Risk: medium', or 'Risk: high')"
- [UNTRUSTED MEMORY DATA] "User added format_qty(grams) to inventory/units.py ..."
```

The code it wrote:

```python
STAGING_SCHEME = "https"
STAGING_HOST = "staging.internal"
STAGING_PORT = 8443

def staging_url() -> str:
    """Inventory: return the base URL of the staging API. ..."""
    return f"{STAGING_SCHEME}://{STAGING_HOST}:{STAGING_PORT}"
```

The end of its final message:

```
Conventions followed: docstring starts with "Inventory:", no third-party dependencies,
one-line changelog entry, pytest plain asserts (no unittest).

Risk: low
```

### Session 3, baseline: no memory, so it guesses

```python
_STAGING_URL = "https://staging.inventory.example.com:8443"
```

The end of its final message:

```
- Returns `https://staging.inventory.example.com:8443` — scheme, host, explicit port,
  no trailing path. Note: I don't have the earlier discussion's exact value, so if the
  discussed host/port differs, it's a one-line change in `_STAGING_URL`.
- All 10 tests pass.
```

It flags the gap honestly, but the host is made up. Port 8443 is a lucky guess,
since it's the common HTTPS alternate port. All three baseline repeats invented the
same `staging.inventory.example.com` host. All three mem0 repeats wrote
`https://staging.internal:8443`.

### Session 2: visible conventions vs a spoken-only rule

Both arms read the repo and copied the docstring, test, and changelog style from
`parse_qty`. The baseline's reply ends:

```
**`CHANGELOG.md`** — added the `format_qty` line under `## Unreleased`, matching the
existing `parse_qty` entry.

All 8 tests pass (`pytest tests/` → `8 passed`), ...
```

It has no `Risk:` line, and this happened in all three repeats. The repo had no
trace of that rule. mem0 had it recalled and ended with `Risk: low`, 3/3.

### mem0's one failure

In one repeat, mem0 remembered the rule but wrote prose instead of the format:

```
Risk: staging URL comes from a recalled memory and may need verification against your
actual staging environment if it has changed (host/port) — I used
`https://staging.internal:8443` as previously discussed.
```

The checker requires exactly `Risk: low|medium|high`, so this step failed. The
content is reasonable; the format is not.

## Cost

- **Wall time:** no measurable difference in this run. Memory writes run on slot 1
  while the agent works on slot 0.
- **Memory LLM:** 4 calls in session 1, then 1 per later session. Each extraction prompt is about 8.2k tokens with no prompt-cache
  reuse between calls, so roughly 15 s of slot-1 prefill per write. That is the
  main target for a cheaper memory variant.

## Caveats

- One task, which was built so that memory should help. This shows the mechanism
  works end to end; it doesn't show a general benefit.
- n = 3 per arm. The model samples at temperature 1.0.
- The run manifest is marked "dirty": it started on `d97ea63` with the Docker
  sandbox still uncommitted; that code was committed as `387910a` right after.
- Only the first assistant reply after each user prompt is captured into memory
  (an extension behaviour), so final summaries are never stored.

Raw summary, per-step records, and manifest:
[`bench/results/2026-10-11/evals-baseline-mem0/`](https://github.com/aiguy110/bonsai-garden/tree/main/bench/results/2026-10-11/evals-baseline-mem0).
