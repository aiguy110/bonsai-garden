# M1 n-gram self-speculation summary

Foreground replay requests only. Decode rate is `sum(predicted_n) / sum(predicted_ms) * 1000`; background traffic is load, not a measured row.

## Foreground performance

| config | sampling | phase | role | n | decode tok/s | median req tok/s | acceptance | draft/gen | speedup vs off | tool JSON valid | VRAM vs off |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | greedy | single-agent | agent | 30 | 86.0 | 53.6 | 75.5% | 0.586 | 1.560x | 100.0% | 0.0 MiB |
| A | greedy | single-mem | mem | 12 | 53.1 | 35.9 | 9.3% | 0.553 | 0.956x | 91.7% | 0.0 MiB |
| A | greedy | dual-agent | agent | 30 | 25.5 | 30.0 | 14.0% | 0.232 | 0.969x | 100.0% | 0.0 MiB |
| A | greedy | dual-mem | mem | 12 | 23.8 | 17.0 | 9.3% | 0.557 | 0.953x | 83.3% | 0.0 MiB |
| A | prod | single-agent | agent | 30 | 56.0 | 54.3 | 20.7% | 0.223 | 1.001x | 100.0% | 1.0 MiB |
| A | prod | single-mem | mem | 12 | 53.5 | 35.9 | 11.2% | 0.657 | 0.962x | 100.0% | 1.0 MiB |
| A | prod | dual-agent | agent | 30 | 26.7 | 27.6 | 15.3% | 0.132 | 0.853x | 100.0% | 1.0 MiB |
| A | prod | dual-mem | mem | 12 | 23.4 | 17.0 | 11.5% | 0.680 | 0.920x | 91.7% | -1.0 MiB |
| B | greedy | single-agent | agent | 30 | 53.4 | 54.8 | 43.3% | 0.371 | 0.968x | 100.0% | 0.0 MiB |
| B | greedy | single-mem | mem | 12 | 50.7 | 38.3 | 24.0% | 0.450 | 0.912x | 91.7% | 0.0 MiB |
| B | greedy | dual-agent | agent | 30 | 23.0 | 24.8 | 43.5% | 0.206 | 0.876x | 100.0% | 0.0 MiB |
| B | greedy | dual-mem | mem | 12 | 22.4 | 20.3 | 23.2% | 0.474 | 0.897x | 83.3% | 0.0 MiB |
| off | greedy | single-agent | agent | 30 | 55.1 | 55.7 | — | 0.000 | 1.000x | 100.0% | 0.0 MiB |
| off | greedy | single-mem | mem | 12 | 55.6 | 48.9 | — | 0.000 | 1.000x | 83.3% | 0.0 MiB |
| off | greedy | dual-agent | agent | 30 | 26.3 | 30.7 | — | 0.000 | 1.000x | 100.0% | 0.0 MiB |
| off | greedy | dual-mem | mem | 12 | 25.0 | 31.6 | — | 0.000 | 1.000x | 91.7% | 0.0 MiB |
| off | prod | single-agent | agent | 30 | 56.0 | 55.9 | — | 0.000 | 1.000x | 100.0% | 0.0 MiB |
| off | prod | single-mem | mem | 12 | 55.6 | 48.8 | — | 0.000 | 1.000x | 100.0% | 0.0 MiB |
| off | prod | dual-agent | agent | 30 | 31.3 | 33.8 | — | 0.000 | 1.000x | 100.0% | 0.0 MiB |
| off | prod | dual-mem | mem | 12 | 25.4 | 31.4 | — | 0.000 | 1.000x | 100.0% | 0.0 MiB |

## Greedy output identity

Compared against off at the same phase and request id. First divergence is a character index in the hashed response representation (reasoning + content + canonical tool calls).

| config | phase | identical/compared | rate | first-divergence indices for mismatches |
|---|---|---:|---:|---|
| A | single-agent | 3/30 | 10.0% | inventory-baseline-r0/0/0:253, inventory-baseline-r0/0/2:225, inventory-baseline-r0/0/5:1006, inventory-baseline-r0/0/8:449, inventory-baseline-r0/0/10:815, inventory-baseline-r1/0/0:253, inventory-baseline-r1/0/2:213, inventory-baseline-r1/0/4:504, inventory-baseline-r1/0/5:485, inventory-baseline-r1/2/0:472, inventory-baseline-r1/2/3:430, inventory-baseline-r1/2/6:1270, inventory-mem0-r0/0/0:253, inventory-mem0-r0/0/2:282, inventory-mem0-r0/0/4:466, inventory-mem0-r0/0/7:866, inventory-mem0-r0/0/9:1018, inventory-mem0-r1/0/0:253, inventory-mem0-r1/0/2:179, inventory-mem0-r1/0/4:311, inventory-mem0-r1/0/5:331, inventory-mem0-r1/0/7:231, inventory-mem0-r2/0/0:253, inventory-mem0-r2/0/2:3327, inventory-mem0-r2/0/4:280, inventory-mem0-r2/0/6:380, inventory-mem0-r2/0/8:495 |
| A | single-mem | 10/12 | 83.3% | inventory-mem0-r0/1/0:419, inventory-mem0-r1/1/0:1244 |
| A | dual-agent | 0/30 | 0.0% | inventory-baseline-r0/0/0:253, inventory-baseline-r0/0/2:226, inventory-baseline-r0/0/5:1005, inventory-baseline-r0/0/8:275, inventory-baseline-r0/0/10:820, inventory-baseline-r1/0/0:253, inventory-baseline-r1/0/2:25, inventory-baseline-r1/0/4:31, inventory-baseline-r1/0/5:109, inventory-baseline-r1/0/7:449, inventory-baseline-r1/2/0:412, inventory-baseline-r1/2/3:430, inventory-baseline-r1/2/6:39, inventory-baseline-r1/2/8:161, inventory-baseline-r1/2/11:852, inventory-mem0-r0/0/0:253, inventory-mem0-r0/0/2:322, inventory-mem0-r0/0/4:400, inventory-mem0-r0/0/7:210, inventory-mem0-r0/0/9:186, inventory-mem0-r1/0/0:130, inventory-mem0-r1/0/2:179, inventory-mem0-r1/0/4:75, inventory-mem0-r1/0/5:331, inventory-mem0-r1/0/7:231, inventory-mem0-r2/0/0:253, inventory-mem0-r2/0/2:255, inventory-mem0-r2/0/4:591, inventory-mem0-r2/0/6:382, inventory-mem0-r2/0/8:496 |
| A | dual-mem | 11/12 | 91.7% | inventory-mem0-r1/1/0:1306 |
| B | single-agent | 2/30 | 6.7% | inventory-baseline-r0/0/0:253, inventory-baseline-r0/0/2:225, inventory-baseline-r0/0/5:1006, inventory-baseline-r0/0/8:449, inventory-baseline-r0/0/10:224, inventory-baseline-r1/0/0:253, inventory-baseline-r1/0/2:49, inventory-baseline-r1/0/4:504, inventory-baseline-r1/0/5:485, inventory-baseline-r1/2/0:412, inventory-baseline-r1/2/3:430, inventory-baseline-r1/2/6:39, inventory-baseline-r1/2/8:282, inventory-mem0-r0/0/0:253, inventory-mem0-r0/0/2:594, inventory-mem0-r0/0/4:466, inventory-mem0-r0/0/7:866, inventory-mem0-r0/0/9:1018, inventory-mem0-r1/0/0:253, inventory-mem0-r1/0/2:179, inventory-mem0-r1/0/4:311, inventory-mem0-r1/0/5:331, inventory-mem0-r1/0/7:231, inventory-mem0-r2/0/0:253, inventory-mem0-r2/0/2:18, inventory-mem0-r2/0/4:280, inventory-mem0-r2/0/6:380, inventory-mem0-r2/0/8:258 |
| B | single-mem | 10/12 | 83.3% | inventory-mem0-r0/0/0:698, inventory-mem0-r1/1/0:1244 |
| B | dual-agent | 0/30 | 0.0% | inventory-baseline-r0/0/0:253, inventory-baseline-r0/0/2:62, inventory-baseline-r0/0/5:329, inventory-baseline-r0/0/8:275, inventory-baseline-r0/0/10:550, inventory-baseline-r1/0/0:253, inventory-baseline-r1/0/2:49, inventory-baseline-r1/0/4:31, inventory-baseline-r1/0/5:485, inventory-baseline-r1/0/7:629, inventory-baseline-r1/2/0:472, inventory-baseline-r1/2/3:430, inventory-baseline-r1/2/6:310, inventory-baseline-r1/2/8:294, inventory-baseline-r1/2/11:66, inventory-mem0-r0/0/0:253, inventory-mem0-r0/0/2:282, inventory-mem0-r0/0/4:249, inventory-mem0-r0/0/7:513, inventory-mem0-r0/0/9:242, inventory-mem0-r1/0/0:253, inventory-mem0-r1/0/2:179, inventory-mem0-r1/0/4:245, inventory-mem0-r1/0/5:331, inventory-mem0-r1/0/7:21, inventory-mem0-r2/0/0:253, inventory-mem0-r2/0/2:255, inventory-mem0-r2/0/4:591, inventory-mem0-r2/0/6:164, inventory-mem0-r2/0/8:79 |
| B | dual-mem | 11/12 | 91.7% | inventory-mem0-r1/1/0:1098 |
| off | single-agent | 30/30 | 100.0% | — |
| off | single-mem | 12/12 | 100.0% | — |
| off | dual-agent | 30/30 | 100.0% | — |
| off | dual-mem | 12/12 | 100.0% | — |

Off dual-vs-single batch-numerics control:

| role | identical/compared | rate | first-divergence indices for mismatches |
|---|---:|---:|---|
| agent | 0/30 | 0.0% | inventory-baseline-r0/0/0:253, inventory-baseline-r0/0/2:62, inventory-baseline-r0/0/5:223, inventory-baseline-r0/0/8:113, inventory-baseline-r0/0/10:224, inventory-baseline-r1/0/0:253, inventory-baseline-r1/0/2:49, inventory-baseline-r1/0/4:212, inventory-baseline-r1/0/5:485, inventory-baseline-r1/0/7:449, inventory-baseline-r1/2/0:472, inventory-baseline-r1/2/3:430, inventory-baseline-r1/2/6:497, inventory-baseline-r1/2/8:542, inventory-baseline-r1/2/11:66, inventory-mem0-r0/0/0:253, inventory-mem0-r0/0/2:282, inventory-mem0-r0/0/4:249, inventory-mem0-r0/0/7:513, inventory-mem0-r0/0/9:242, inventory-mem0-r1/0/0:253, inventory-mem0-r1/0/2:179, inventory-mem0-r1/0/4:39, inventory-mem0-r1/0/5:331, inventory-mem0-r1/0/7:231, inventory-mem0-r2/0/0:253, inventory-mem0-r2/0/2:18, inventory-mem0-r2/0/4:280, inventory-mem0-r2/0/6:164, inventory-mem0-r2/0/8:495 |
| mem | 10/12 | 83.3% | inventory-mem0-r0/0/0:191, inventory-mem0-r1/1/0:1098 |

## Deployment decision

Candidate: `A-prod` (`--spec-type ngram-mod`). Deploy only if every rule passes.

| rule | criterion | result | value |
|---:|---|---|---|
| 1 | Pinned live --mmproj projector is successfully loaded in all four A-prod server logs. | PASS | loaded 4/4: single-agent, single-mem, dual-agent, dual-mem (/home/josiah/models/Ternary-Bonsai-2-27B-mmproj-Q8_0.gguf) |
| 2 | At production sampling, dual-agent decode tok/s is at least 1.10x off. | FAIL | dual-agent 26.7 tok/s, 0.853x off |
| 3 | At production sampling, dual-mem, single-agent, and single-mem are each at least 0.97x off. | FAIL | dual-mem/single-agent/single-mem 0.920x/1.001x/0.962x |
| 4 | For every production phase, VRAM is no more than off + 64 MiB. | PASS | max delta +1 MiB |
| 5 | For every production phase, tool_call_json_valid rate is at least off's rate. | FAIL | candidate/off valid rates (dual-agent, dual-mem, single-agent, single-mem): 100.0%/100.0%/91.7%/100.0%/100.0%/100.0%/100.0%/100.0% |
| 6 | Greedy identical-output rate is not more than 10 percentage points below the off dual-vs-single control. | PASS | A dual 26.2%; off dual-vs-single control 23.8% |

**Decision: do not deploy.** rule 2: dual-agent 26.7 tok/s, 0.853x off; rule 3: dual-mem/single-agent/single-mem 0.920x/1.001x/0.962x; rule 5: candidate/off valid rates (dual-agent, dual-mem, single-agent, single-mem): 100.0%/100.0%/91.7%/100.0%/100.0%/100.0%/100.0%/100.0%.
