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
| A | single-agent | 3/30 | 10.0% | inventory-baseline-r0/0/0:None, inventory-baseline-r0/0/2:None, inventory-baseline-r0/0/5:None, inventory-baseline-r0/0/8:None, inventory-baseline-r0/0/10:None, inventory-baseline-r1/0/0:None, inventory-baseline-r1/0/2:None, inventory-baseline-r1/0/4:None, inventory-baseline-r1/0/5:None, inventory-baseline-r1/2/0:None, inventory-baseline-r1/2/3:None, inventory-baseline-r1/2/6:None, inventory-mem0-r0/0/0:None, inventory-mem0-r0/0/2:None, inventory-mem0-r0/0/4:None, inventory-mem0-r0/0/7:None, inventory-mem0-r0/0/9:None, inventory-mem0-r1/0/0:None, inventory-mem0-r1/0/2:None, inventory-mem0-r1/0/4:None, inventory-mem0-r1/0/5:None, inventory-mem0-r1/0/7:None, inventory-mem0-r2/0/0:None, inventory-mem0-r2/0/2:None, inventory-mem0-r2/0/4:None, inventory-mem0-r2/0/6:None, inventory-mem0-r2/0/8:None |
| A | single-mem | 10/12 | 83.3% | inventory-mem0-r0/1/0:None, inventory-mem0-r1/1/0:None |
| A | dual-agent | 0/30 | 0.0% | inventory-baseline-r0/0/0:None, inventory-baseline-r0/0/2:None, inventory-baseline-r0/0/5:None, inventory-baseline-r0/0/8:None, inventory-baseline-r0/0/10:None, inventory-baseline-r1/0/0:None, inventory-baseline-r1/0/2:None, inventory-baseline-r1/0/4:None, inventory-baseline-r1/0/5:None, inventory-baseline-r1/0/7:None, inventory-baseline-r1/2/0:None, inventory-baseline-r1/2/3:None, inventory-baseline-r1/2/6:None, inventory-baseline-r1/2/8:None, inventory-baseline-r1/2/11:None, inventory-mem0-r0/0/0:None, inventory-mem0-r0/0/2:None, inventory-mem0-r0/0/4:None, inventory-mem0-r0/0/7:None, inventory-mem0-r0/0/9:None, inventory-mem0-r1/0/0:None, inventory-mem0-r1/0/2:None, inventory-mem0-r1/0/4:None, inventory-mem0-r1/0/5:None, inventory-mem0-r1/0/7:None, inventory-mem0-r2/0/0:None, inventory-mem0-r2/0/2:None, inventory-mem0-r2/0/4:None, inventory-mem0-r2/0/6:None, inventory-mem0-r2/0/8:None |
| A | dual-mem | 11/12 | 91.7% | inventory-mem0-r1/1/0:None |
| B | single-agent | 2/30 | 6.7% | inventory-baseline-r0/0/0:None, inventory-baseline-r0/0/2:None, inventory-baseline-r0/0/5:None, inventory-baseline-r0/0/8:None, inventory-baseline-r0/0/10:None, inventory-baseline-r1/0/0:None, inventory-baseline-r1/0/2:None, inventory-baseline-r1/0/4:None, inventory-baseline-r1/0/5:None, inventory-baseline-r1/2/0:None, inventory-baseline-r1/2/3:None, inventory-baseline-r1/2/6:None, inventory-baseline-r1/2/8:None, inventory-mem0-r0/0/0:None, inventory-mem0-r0/0/2:None, inventory-mem0-r0/0/4:None, inventory-mem0-r0/0/7:None, inventory-mem0-r0/0/9:None, inventory-mem0-r1/0/0:None, inventory-mem0-r1/0/2:None, inventory-mem0-r1/0/4:None, inventory-mem0-r1/0/5:None, inventory-mem0-r1/0/7:None, inventory-mem0-r2/0/0:None, inventory-mem0-r2/0/2:None, inventory-mem0-r2/0/4:None, inventory-mem0-r2/0/6:None, inventory-mem0-r2/0/8:None |
| B | single-mem | 10/12 | 83.3% | inventory-mem0-r0/0/0:None, inventory-mem0-r1/1/0:None |
| B | dual-agent | 0/30 | 0.0% | inventory-baseline-r0/0/0:None, inventory-baseline-r0/0/2:None, inventory-baseline-r0/0/5:None, inventory-baseline-r0/0/8:None, inventory-baseline-r0/0/10:None, inventory-baseline-r1/0/0:None, inventory-baseline-r1/0/2:None, inventory-baseline-r1/0/4:None, inventory-baseline-r1/0/5:None, inventory-baseline-r1/0/7:None, inventory-baseline-r1/2/0:None, inventory-baseline-r1/2/3:None, inventory-baseline-r1/2/6:None, inventory-baseline-r1/2/8:None, inventory-baseline-r1/2/11:None, inventory-mem0-r0/0/0:None, inventory-mem0-r0/0/2:None, inventory-mem0-r0/0/4:None, inventory-mem0-r0/0/7:None, inventory-mem0-r0/0/9:None, inventory-mem0-r1/0/0:None, inventory-mem0-r1/0/2:None, inventory-mem0-r1/0/4:None, inventory-mem0-r1/0/5:None, inventory-mem0-r1/0/7:None, inventory-mem0-r2/0/0:None, inventory-mem0-r2/0/2:None, inventory-mem0-r2/0/4:None, inventory-mem0-r2/0/6:None, inventory-mem0-r2/0/8:None |
| B | dual-mem | 11/12 | 91.7% | inventory-mem0-r1/1/0:None |
| off | single-agent | 30/30 | 100.0% | — |
| off | single-mem | 12/12 | 100.0% | — |
| off | dual-agent | 30/30 | 100.0% | — |
| off | dual-mem | 12/12 | 100.0% | — |

Off dual-vs-single batch-numerics control:

| role | identical/compared | rate | first-divergence indices for mismatches |
|---|---:|---:|---|
| agent | 0/30 | 0.0% | inventory-baseline-r0/0/0:None, inventory-baseline-r0/0/2:None, inventory-baseline-r0/0/5:None, inventory-baseline-r0/0/8:None, inventory-baseline-r0/0/10:None, inventory-baseline-r1/0/0:None, inventory-baseline-r1/0/2:None, inventory-baseline-r1/0/4:None, inventory-baseline-r1/0/5:None, inventory-baseline-r1/0/7:None, inventory-baseline-r1/2/0:None, inventory-baseline-r1/2/3:None, inventory-baseline-r1/2/6:None, inventory-baseline-r1/2/8:None, inventory-baseline-r1/2/11:None, inventory-mem0-r0/0/0:None, inventory-mem0-r0/0/2:None, inventory-mem0-r0/0/4:None, inventory-mem0-r0/0/7:None, inventory-mem0-r0/0/9:None, inventory-mem0-r1/0/0:None, inventory-mem0-r1/0/2:None, inventory-mem0-r1/0/4:None, inventory-mem0-r1/0/5:None, inventory-mem0-r1/0/7:None, inventory-mem0-r2/0/0:None, inventory-mem0-r2/0/2:None, inventory-mem0-r2/0/4:None, inventory-mem0-r2/0/6:None, inventory-mem0-r2/0/8:None |
| mem | 10/12 | 83.3% | inventory-mem0-r0/0/0:None, inventory-mem0-r1/1/0:None |

## Deployment decision

Candidate: `A-prod` (`--spec-type ngram-mod`). Deploy only if every rule passes.

| rule | criterion | result | value |
|---:|---|---|---|
| 1 | pinned --mmproj projector actually loaded: all four A-prod server logs record `load_model: loaded multimodal model, ...mmproj...` for the live entry's pinned path | PASS | pinned mmproj load line in 4/4 A-prod server logs |
| 2 | dual-agent decode tok/s >= 1.10x off at the same sampling and phase | FAIL | dual-agent 26.7 tok/s, 0.853x off |
| 3 | dual-mem, single-agent and single-mem each >= 0.97x off | FAIL | dual-mem/single-agent/single-mem 0.920x/1.001x/0.962x |
| 4 | VRAM in every phase <= off + 64 MiB | PASS | max delta +1 MiB |
| 5 | tool_call_json_valid rate >= off's rate in every phase | FAIL | candidate/off valid rates (dual-agent, dual-mem, single-agent, single-mem): 100.0%/100.0%/91.7%/100.0%/100.0%/100.0%/100.0%/100.0% |
| 6 | A-greedy dual-phase identical-output rate >= off dual-vs-single control rate - 10 percentage points | PASS | A dual 26.2%; off dual-vs-single control 23.8% |

**Decision: do not deploy.** rule 2: dual-agent 26.7 tok/s, 0.853x off; rule 3: dual-mem/single-agent/single-mem 0.920x/1.001x/0.962x; rule 5: candidate/off valid rates (dual-agent, dual-mem, single-agent, single-mem): 100.0%/100.0%/91.7%/100.0%/100.0%/100.0%/100.0%/100.0%.
