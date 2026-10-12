---
title: Autopilot status
kind: Live status
updated: 2026-10-12
---

*Updated 2026-10-12T06:08:02-04:00. Written by `autopilot/autopilot.py`; see the [roadmap](https://github.com/aiguy110/bonsai-garden/blob/main/docs/roadmap.md) for how it works.*

Cloud advisor calls left today: **18** of 25.

## M1-ngram

**Phase:** work

- ✖️ **Inventory spec flags, mmproj compatibility and the recorded traffic**
- ▶️ **Convert recordings into agent and mem0 replay requests, checked against tap prompt sizes** (round 1)
- ⬜ **Replay probe on :8089: spec off vs ≥2 n-gram settings, 1 and 2 slots busy**
- ⬜ **Summarize, decide, and deploy via infra only if the rule is met**
- ⬜ **Experiment page, series and project summaries, docs**

<details><summary>Recent journal entries</summary>

- 2026-10-12T04:11:03-04:00 · advisor (run request)
- 2026-10-12T04:11:04-04:00 · orchestrator
- 2026-10-12T04:56:07-04:00 · worker (Bonsai), round 10
- 2026-10-12T04:56:07-04:00 · orchestrator
- 2026-10-12T05:09:29-04:00 · worker (Bonsai), round 11
- 2026-10-12T05:09:54-04:00 · advisor (run request)
- 2026-10-12T05:09:56-04:00 · orchestrator
- 2026-10-12T05:21:39-04:00 · worker (Bonsai), round 12
- 2026-10-12T05:22:57-04:00 · advisor (finished item)
- 2026-10-12T05:23:00-04:00 · orchestrator
- 2026-10-12T06:08:02-04:00 · worker (Bonsai), round 1
- 2026-10-12T06:08:02-04:00 · orchestrator

Full journal: [branch auto/M1-ngram](https://github.com/aiguy110/bonsai-garden/blob/auto/M1-ngram/autopilot/state/M1-ngram/journal.md)
</details>

## M2-continuity

**Phase:** plan


## Live-stack changes

| time | op | result | 2-slot tok/s |
|---|---|---|---|
| 2026-10-11T23:01:49-04:00 | baseline | ok | 44.3 |
