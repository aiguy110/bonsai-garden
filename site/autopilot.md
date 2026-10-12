---
title: Autopilot status
kind: Live status
updated: 2026-10-12
---

*Updated 2026-10-12T11:13:27-04:00. Written by `autopilot/autopilot.py`; see the [roadmap](https://github.com/aiguy110/bonsai-garden/blob/main/docs/roadmap.md) for how it works.*

Cloud advisor calls left today: **17** of 30.

## M1-ngram

**Phase:** work

- ⚠️ **Inventory spec flags, mmproj compatibility and the recorded traffic**
- ✅ **Convert recordings into agent and mem0 replay requests, checked against tap prompt sizes**
- ▶️ **Replay probe on :8089: spec off vs ≥2 n-gram settings, 1 and 2 slots busy** (round 7)
- ⬜ **Summarize, decide, and deploy via infra only if the rule is met**
- ⬜ **Experiment page, series and project summaries, docs**

<details><summary>Recent journal entries</summary>

- 2026-10-12T10:30:13-04:00 · worker (gpt-5.6-terra), round 5
- 2026-10-12T10:31:34-04:00 · advisor (run request)
- 2026-10-12T10:31:34-04:00 · orchestrator
- 2026-10-12T10:33:16-04:00 · orchestrator
- 2026-10-12T10:33:40-04:00 · worker (gpt-5.6-terra), round 5
- 2026-10-12T10:35:02-04:00 · advisor (run request)
- 2026-10-12T10:35:16-04:00 · worker (gpt-5.6-terra), round 6
- 2026-10-12T10:35:45-04:00 · advisor (run request)
- 2026-10-12T10:50:27-04:00 · orchestrator
- 2026-10-12T10:52:14-04:00 · worker (gpt-5.6-terra), round 7
- 2026-10-12T10:52:46-04:00 · advisor (run request)
- 2026-10-12T11:13:27-04:00 · orchestrator

Full journal: [branch auto/M1-ngram](https://github.com/aiguy110/bonsai-garden/blob/auto/M1-ngram/autopilot/state/M1-ngram/journal.md)
</details>

## W1-worker-eval

**Phase:** plan


## Live-stack changes

| time | op | result | 2-slot tok/s |
|---|---|---|---|
| 2026-10-11T23:01:49-04:00 | baseline | ok | 44.3 |
