---
title: Autopilot status
kind: Live status
updated: 2026-10-13
---

*Updated 2026-10-13T08:33:04-04:00. Written by `autopilot/autopilot.py`; see the [roadmap](https://github.com/aiguy110/bonsai-garden/blob/main/docs/roadmap.md) for how it works.*

Cloud advisor calls left today: **92** of 100.

## M1-ngram

**Phase:** done

- ⚠️ **Inventory spec flags, mmproj compatibility and the recorded traffic**
- ✅ **Convert recordings into agent and mem0 replay requests, checked against tap prompt sizes**
- ✅ **Replay probe on :8089: spec off vs ≥2 n-gram settings, 1 and 2 slots busy**
- ✅ **Summarize, decide, and deploy via infra only if the rule is met**
- ✅ **Experiment page, series and project summaries, docs**

<details><summary>Recent journal entries</summary>

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
- 2026-10-12T12:18:31-04:00 · orchestrator

Full journal: [branch auto/M1-ngram](https://github.com/aiguy110/bonsai-garden/blob/auto/M1-ngram/autopilot/state/M1-ngram/journal.md)
</details>

## W1-worker-eval

**Phase:** work

- ✅ **Extract a provenance-checked cloud-worker case set**
- ⚠️ **Define worker arms and implement the resumable replay harness**
- ✅ **Run Bonsai at N=2 and summarize deterministic outcomes**
- ▶️ **Grade a deterministic sample of valid Bonsai requests** (round 1)
- ⬜ **Publish the W1 experiment and update parent summaries**

<details><summary>Recent journal entries</summary>

- 2026-10-13T08:17:27-04:00 · advisor (run request)
- 2026-10-13T08:17:27-04:00 · orchestrator
- 2026-10-13T08:17:27-04:00 · orchestrator
- 2026-10-13T08:18:41-04:00 · worker (gpt-5.6-terra), round 9
- 2026-10-13T08:19:51-04:00 · advisor (run request)
- 2026-10-13T08:19:51-04:00 · orchestrator
- 2026-10-13T08:19:52-04:00 · orchestrator
- 2026-10-13T08:21:29-04:00 · worker (gpt-5.6-terra), round 10
- 2026-10-13T08:22:54-04:00 · advisor (finished item)
- 2026-10-13T08:22:54-04:00 · orchestrator
- 2026-10-13T08:28:10-04:00 · worker (gpt-5.6-terra), round 1
- 2026-10-13T08:33:04-04:00 · advisor (run request)

Full journal: [branch auto/W1-worker-eval](https://github.com/aiguy110/bonsai-garden/blob/auto/W1-worker-eval/autopilot/state/W1-worker-eval/journal.md)
</details>

## Live-stack changes

| time | op | result | 2-slot tok/s |
|---|---|---|---|
| 2026-10-11T23:01:49-04:00 | baseline | ok | 44.3 |
