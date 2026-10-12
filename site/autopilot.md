---
title: Autopilot status
kind: Live status
updated: 2026-10-12
---

*Updated 2026-10-12T04:56:08-04:00. Written by `autopilot/autopilot.py`; see the [roadmap](https://github.com/aiguy110/bonsai-garden/blob/main/docs/roadmap.md) for how it works.*

Cloud advisor calls left today: **20** of 25.

## M1-ngram

**Phase:** work

- ▶️ **Inventory spec flags, mmproj compatibility and the recorded traffic** (round 10)
- ⬜ **Convert recordings into agent and mem0 replay requests, checked against tap prompt sizes**
- ⬜ **Replay probe on :8089: spec off vs ≥2 n-gram settings, 1 and 2 slots busy**
- ⬜ **Summarize, decide, and deploy via infra only if the rule is met**
- ⬜ **Experiment page, series and project summaries, docs**

<details><summary>Recent journal entries</summary>

- 2026-10-12T03:25:05-04:00 · advisor (run request)
- 2026-10-12T03:25:08-04:00 · orchestrator
- 2026-10-12T03:41:38-04:00 · orchestrator (operator)
- 2026-10-12T03:42:08-04:00 · worker (Bonsai), round 7
- 2026-10-12T03:42:08-04:00 · orchestrator
- 2026-10-12T04:09:11-04:00 · worker (Bonsai), round 8
- 2026-10-12T04:09:11-04:00 · orchestrator
- 2026-10-12T04:10:37-04:00 · worker (Bonsai), round 9
- 2026-10-12T04:11:03-04:00 · advisor (run request)
- 2026-10-12T04:11:04-04:00 · orchestrator
- 2026-10-12T04:56:07-04:00 · worker (Bonsai), round 10
- 2026-10-12T04:56:07-04:00 · orchestrator

Full journal: [branch auto/M1-ngram](https://github.com/aiguy110/bonsai-garden/blob/auto/M1-ngram/autopilot/state/M1-ngram/journal.md)
</details>

## M2-continuity

**Phase:** plan


## Live-stack changes

| time | op | result | 2-slot tok/s |
|---|---|---|---|
| 2026-10-11T23:01:49-04:00 | baseline | ok | 44.3 |
