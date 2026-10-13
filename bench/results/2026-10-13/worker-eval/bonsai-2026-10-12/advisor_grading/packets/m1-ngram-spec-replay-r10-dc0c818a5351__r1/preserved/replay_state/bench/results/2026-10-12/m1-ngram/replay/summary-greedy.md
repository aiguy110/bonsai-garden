| phase | arm | fg tok/s | fg tok/s no-length | n fg | length rows (ids) | draft_n | accepted | bg tok | same sha as off-greedy |
|---|---|---|---|---|---|---|---|---|---|
| single-agent | off-greedy | 55.1 | 56.2 | 30 | 1 (baseline-r1/2/8) | 0 | 0 | 0 | 30/30 |
| single-agent | A-greedy | 86.0 | 54.3 | 30 | 3 (baseline-r1/2/8, mem0-r0/0/2, mem0-r2/0/2) | 8229 | 6212 | 0 | 3/30 |
| single-agent | B-greedy | 53.4 | 55.0 | 30 | 1 (baseline-r1/2/8) | 2757 | 1194 | 0 | 2/30 |
| single-mem | off-greedy | 55.6 | 55.6 | 12 | 0 () | 0 | 0 | 0 | 12/12 |
| single-mem | A-greedy | 53.1 | 53.1 | 12 | 0 () | 740 | 69 | 0 | 10/12 |
| single-mem | B-greedy | 50.7 | 50.7 | 12 | 0 () | 592 | 142 | 0 | 10/12 |
| dual-agent | off-greedy | 26.3 | 26.3 | 30 | 0 () | 0 | 0 | 6618 | 30/30 |
| dual-agent | A-greedy | 25.5 | 26.1 | 30 | 2 (baseline-r1/2/6, baseline-r1/2/8) | 1856 | 259 | 8540 | 0/30 |
| dual-agent | B-greedy | 23.0 | 23.0 | 30 | 0 () | 1562 | 679 | 8540 | 0/30 |
| dual-mem | off-greedy | 25.0 | 25.0 | 12 | 0 () | 0 | 0 | 1397 | 12/12 |
| dual-mem | A-greedy | 23.8 | 23.8 | 12 | 0 () | 740 | 69 | 1418 | 11/12 |
| dual-mem | B-greedy | 22.4 | 22.4 | 12 | 0 () | 624 | 145 | 1416 | 11/12 |
