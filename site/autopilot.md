---
title: Autopilot status
kind: Live status
updated: 2026-10-12
---

*Updated 2026-10-12T16:35:20-04:00. Written by `autopilot/autopilot.py`; see the [roadmap](https://github.com/aiguy110/bonsai-garden/blob/main/docs/roadmap.md) for how it works.*

Cloud advisor calls left today: **3** of 50.

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

**Phase:** blocked — triage of `replay-harness` (the worker is stuck: The acceptance smoke test cannot safely be retried until the repeated abrupt host resets correlated with launching the replay are diagnosed or a host-level mitigation is applied.): Human host-level action is required before more inference. Four smoke invocations launched real bench-route requests and were followed by abrupt host resets; none completed. The retained journals show no orderly shutdown, OOM, NVIDIA Xid, panic, watchdog, or thermal event. Please diagnose/stabilize bifrost—especially PSU/GPU power delivery, cabling, BIOS/firmware, and root-only crash evidence—or approve a reversible mitigation such as a conservative RTX 3080 power cap and validate it under controlled load. Then unblock W1 and permit one smoke retry. Do not launch the full N=2 baseline meanwhile.

- ✅ **Extract a provenance-checked cloud-worker case set**
- ⬜ **Define worker arms and implement the resumable replay harness**
- ⬜ **Run Bonsai at N=2 and summarize deterministic outcomes**
- ⬜ **Grade a deterministic sample of valid Bonsai requests**
- ⬜ **Publish the W1 experiment and update parent summaries**

<details><summary>Recent journal entries</summary>

- 2026-10-12T16:22:30-04:00 · advisor (run request)
- 2026-10-12T16:27:04-04:00 · orchestrator
- 2026-10-12T16:28:42-04:00 · fixer (cloud)
- 2026-10-12T16:28:58-04:00 · worker (gpt-5.6-terra), round 9
- 2026-10-12T16:30:33-04:00 · advisor (run request)
- 2026-10-12T16:30:33-04:00 · orchestrator
- 2026-10-12T16:31:20-04:00 · worker (gpt-5.6-terra), round 10
- 2026-10-12T16:31:53-04:00 · advisor (run request)
- 2026-10-12T16:32:09-04:00 · orchestrator
- 2026-10-12T16:33:41-04:00 · worker (gpt-5.6-terra), round 11
- 2026-10-12T16:35:20-04:00 · advisor (triage)
- 2026-10-12T16:35:20-04:00 · orchestrator

Full journal: [branch auto/W1-worker-eval](https://github.com/aiguy110/bonsai-garden/blob/auto/W1-worker-eval/autopilot/state/W1-worker-eval/journal.md)
</details>

## Live-stack changes

| time | op | result | 2-slot tok/s |
|---|---|---|---|
| 2026-10-11T23:01:49-04:00 | baseline | ok | 44.3 |
