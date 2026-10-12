---
title: Autopilot status
kind: Live status
updated: 2026-10-12
---

*Updated 2026-10-12T08:21:07-04:00. Written by `autopilot/autopilot.py`; see the [roadmap](https://github.com/aiguy110/bonsai-garden/blob/main/docs/roadmap.md) for how it works.*

Cloud advisor calls left today: **18** of 25.

## M1-ngram

**Phase:** work

- ⚠️ **Inventory spec flags, mmproj compatibility and the recorded traffic**
- ▶️ **Convert recordings into agent and mem0 replay requests, checked against tap prompt sizes** (round 5)
- ⬜ **Replay probe on :8089: spec off vs ≥2 n-gram settings, 1 and 2 slots busy**
- ⬜ **Summarize, decide, and deploy via infra only if the rule is met**
- ⬜ **Experiment page, series and project summaries, docs**

<details><summary>Recent journal entries</summary>

- 2026-10-12T06:08:02-04:00 · worker (Bonsai), round 1
- 2026-10-12T06:08:02-04:00 · orchestrator
- 2026-10-12T06:53:07-04:00 · worker (Bonsai), round 2
- 2026-10-12T06:53:07-04:00 · orchestrator
- 2026-10-12T06:53:30-04:00 · orchestrator
- 2026-10-12T07:12:16-04:00 · worker (Bonsai), round 3
- 2026-10-12T07:12:16-04:00 · orchestrator
- 2026-10-12T07:15:20-04:00 · orchestrator
- 2026-10-12T08:00:21-04:00 · worker (Bonsai), round 4
- 2026-10-12T08:00:21-04:00 · orchestrator
- 2026-10-12T08:21:06-04:00 · worker (Bonsai), round 5
- 2026-10-12T08:21:06-04:00 · orchestrator

Full journal: [branch auto/M1-ngram](https://github.com/aiguy110/bonsai-garden/blob/auto/M1-ngram/autopilot/state/M1-ngram/journal.md)
</details>

## M2-continuity

**Phase:** plan


## Live-stack changes

| time | op | result | 2-slot tok/s |
|---|---|---|---|
| 2026-10-11T23:01:49-04:00 | baseline | ok | 44.3 |
