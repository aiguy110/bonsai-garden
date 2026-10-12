---
title: Autopilot status
kind: Live status
updated: 2026-10-12
---

*Updated 2026-10-12T09:33:01-04:00. Written by `autopilot/autopilot.py`; see the [roadmap](https://github.com/aiguy110/bonsai-garden/blob/main/docs/roadmap.md) for how it works.*

Cloud advisor calls left today: **8** of 25.

## M1-ngram

**Phase:** work

- ⚠️ **Inventory spec flags, mmproj compatibility and the recorded traffic**
- ✅ **Convert recordings into agent and mem0 replay requests, checked against tap prompt sizes**
- ▶️ **Replay probe on :8089: spec off vs ≥2 n-gram settings, 1 and 2 slots busy** (round 3)
- ⬜ **Summarize, decide, and deploy via infra only if the rule is met**
- ⬜ **Experiment page, series and project summaries, docs**

<details><summary>Recent journal entries</summary>

- 2026-10-12T08:48:12-04:00 · worker (claude-sonnet-5-5), round 1
- 2026-10-12T08:49:41-04:00 · advisor (run request)
- 2026-10-12T08:49:41-04:00 · orchestrator
- 2026-10-12T09:02:31-04:00 · orchestrator
- 2026-10-12T09:03:24-04:00 · worker (claude-sonnet-5-5), round 2
- 2026-10-12T09:04:38-04:00 · advisor (run request)
- 2026-10-12T09:04:38-04:00 · orchestrator
- 2026-10-12T09:17:52-04:00 · orchestrator
- 2026-10-12T09:18:43-04:00 · worker (claude-sonnet-5-5), round 3
- 2026-10-12T09:19:55-04:00 · advisor (run request)
- 2026-10-12T09:19:55-04:00 · orchestrator
- 2026-10-12T09:32:59-04:00 · orchestrator

Full journal: [branch auto/M1-ngram](https://github.com/aiguy110/bonsai-garden/blob/auto/M1-ngram/autopilot/state/M1-ngram/journal.md)
</details>

## M2-continuity

**Phase:** plan


## Live-stack changes

| time | op | result | 2-slot tok/s |
|---|---|---|---|
| 2026-10-11T23:01:49-04:00 | baseline | ok | 44.3 |
