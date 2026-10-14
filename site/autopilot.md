---
title: Autopilot status
kind: Live status
updated: 2026-10-14
---

*Updated 2026-10-14T11:51:46-04:00. Written by `autopilot/autopilot.py`; see the [roadmap](https://github.com/aiguy110/bonsai-garden/blob/main/docs/roadmap.md) for how it works.*

Cloud advisor calls left today: **95** of 100.

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

**Phase:** done

- ✅ **Extract a provenance-checked cloud-worker case set**
- ⚠️ **Define worker arms and implement the resumable replay harness**
- ✅ **Run Bonsai at N=2 and summarize deterministic outcomes**
- ✅ **Grade a deterministic sample of valid Bonsai requests**
- ⚠️ **Publish the W1 experiment and update parent summaries**

<details><summary>Recent journal entries</summary>

- 2026-10-13T09:14:14-04:00 · advisor (write-up)
- 2026-10-13T09:15:28-04:00 · worker (gpt-5.6-terra), round 5
- 2026-10-13T09:15:45-04:00 · advisor (run request)
- 2026-10-13T09:15:45-04:00 · orchestrator
- 2026-10-13T09:16:31-04:00 · worker (gpt-5.6-terra), round 6
- 2026-10-13T09:18:07-04:00 · advisor (write-up)
- 2026-10-13T09:18:07-04:00 · orchestrator
- 2026-10-13T09:18:07-04:00 · orchestrator
- 2026-10-13T09:18:43-04:00 · advisor (triage)
- 2026-10-13T09:18:43-04:00 · orchestrator
- 2026-10-13T09:18:43-04:00 · orchestrator
- 2026-10-13T09:19:16-04:00 · orchestrator

Full journal: [branch auto/W1-worker-eval](https://github.com/aiguy110/bonsai-garden/blob/auto/W1-worker-eval/autopilot/state/W1-worker-eval/journal.md)
</details>

## W2-worker-harness

**Phase:** work

- ✅ **Recon of pi/llama.cpp mechanisms, W1 trace analysis, and fixed W2 decisions**
- ✅ **Harness support, W2 extensions, arm files, queue/compare tools, smoke run**
- ▶️ **Full runs: finish w2-think-drop at N=2; w2-reasoning-budget at N=1 on the signal cases** (round 1)
- ⬜ **Stock oh-my-pi as a whole-harness arm (recon, harness support, smoke, full run)**
- ⬜ **Full runs: remaining single-factor arms and the all-singles comparison**
- ⬜ **Combination arm, advisor grading of the best arm, recommended configuration**
- ⬜ **W2 experiment page and parent page updates**

<details><summary>Recent journal entries</summary>

- 2026-10-14T04:14:29-04:00 · advisor (run request)
- 2026-10-14T06:34:33-04:00 · orchestrator
- 2026-10-14T07:07:20-04:00 · worker (gpt-5.6-terra), round 10
- 2026-10-14T07:07:58-04:00 · advisor (run request)
- 2026-10-14T09:13:10-04:00 · orchestrator
- 2026-10-14T09:22:52-04:00 · worker (gpt-5.6-terra), round 11
- 2026-10-14T09:23:40-04:00 · advisor (run request)
- 2026-10-14T10:20:00-04:00 · user (via Claude Code)
- 2026-10-14T10:13:20-04:00 · orchestrator
- 2026-10-14T10:13:20-04:00 · worker (gpt-5.6-terra), round 1
- 2026-10-14T10:14:09-04:00 · advisor (run request)
- 2026-10-14T11:51:45-04:00 · orchestrator

Full journal: [branch auto/W2-worker-harness](https://github.com/aiguy110/bonsai-garden/blob/auto/W2-worker-harness/autopilot/state/W2-worker-harness/journal.md)
</details>

## N1-mnemopi

**Phase:** plan


## M2-continuity

**Phase:** plan


## Live-stack changes

| time | op | result | 2-slot tok/s |
|---|---|---|---|
| 2026-10-11T23:01:49-04:00 | baseline | ok | 44.3 |
