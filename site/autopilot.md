---
title: Autopilot status
kind: Live status
updated: 2026-10-12
---

*Updated 2026-10-12T12:18:30-04:00. Written by `autopilot/autopilot.py`; see the [roadmap](https://github.com/aiguy110/bonsai-garden/blob/main/docs/roadmap.md) for how it works.*

Cloud advisor calls left today: **29** of 50.

## M1-ngram

**Phase:** publish

- ⚠️ **Inventory spec flags, mmproj compatibility and the recorded traffic**
- ✅ **Convert recordings into agent and mem0 replay requests, checked against tap prompt sizes**
- ✅ **Replay probe on :8089: spec off vs ≥2 n-gram settings, 1 and 2 slots busy**
- ✅ **Summarize, decide, and deploy via infra only if the rule is met**
- ✅ **Experiment page, series and project summaries, docs**

<details><summary>Recent journal entries</summary>

- 2026-10-12T11:35:36-04:00 · advisor (finished item)
- 2026-10-12T11:37:57-04:00 · worker (gpt-5.6-terra), round 3
- 2026-10-12T11:39:30-04:00 · advisor (finished item)
- 2026-10-12T11:42:08-04:00 · orchestrator
- 2026-10-12T11:43:41-04:00 · fixer (cloud)
- 2026-10-12T11:46:52-04:00 · worker (gpt-5.6-terra), round 2
- 2026-10-12T11:47:08-04:00 · advisor (run request)
- 2026-10-12T11:47:08-04:00 · orchestrator
- 2026-10-12T11:47:37-04:00 · worker (gpt-5.6-terra), round 3
- 2026-10-12T11:48:51-04:00 · advisor (write-up)
- 2026-10-12T11:48:54-04:00 · orchestrator
- 2026-10-12T12:18:28-04:00 · orchestrator

Full journal: [branch auto/M1-ngram](https://github.com/aiguy110/bonsai-garden/blob/auto/M1-ngram/autopilot/state/M1-ngram/journal.md)
</details>

## W1-worker-eval

**Phase:** plan


## Live-stack changes

| time | op | result | 2-slot tok/s |
|---|---|---|---|
| 2026-10-11T23:01:49-04:00 | baseline | ok | 44.3 |
