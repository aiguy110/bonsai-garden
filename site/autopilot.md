---
title: Autopilot status
kind: Live status
updated: 2026-10-12
---

*Updated 2026-10-12T00:10:23-04:00. Written by `autopilot/autopilot.py`; see the [roadmap](https://github.com/aiguy110/bonsai-garden/blob/main/docs/roadmap.md) for how it works.*

Cloud advisor calls left today: **25** of 25.

## M1-ngram

**Phase:** work

- ▶️ **Inventory spec flags, mmproj compatibility and the recorded traffic** (round 2)
- ⬜ **Convert recordings into agent and mem0 replay requests, checked against tap prompt sizes**
- ⬜ **Replay probe on :8089: spec off vs ≥2 n-gram settings, 1 and 2 slots busy**
- ⬜ **Summarize, decide, and deploy via infra only if the rule is met**
- ⬜ **Experiment page, series and project summaries, docs**

<details><summary>Recent journal entries</summary>

- 2026-10-11T23:11:16-04:00 · advisor (plan)
- 2026-10-12T00:10:22-04:00 · worker (Bonsai), round 2

Full journal: [branch auto/M1-ngram](https://github.com/aiguy110/bonsai-garden/blob/auto/M1-ngram/autopilot/state/M1-ngram/journal.md)
</details>

## Live-stack changes

| time | op | result | 2-slot tok/s |
|---|---|---|---|
| 2026-10-11T23:01:49-04:00 | baseline | ok | 44.3 |
