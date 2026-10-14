# W2 comparison

| arm | records | valid | kind | kind/valid | median wall s | median turns | run/infra/continue/done/stuck/none |
|---|---|---|---|---|---|---|---|
| bonsai-2026-10-12-honest | 44 | 27 | 20 | 20/27 (0.7407407407407407) | 739.45 | 15.0 | 20/0/0/7/0/17 |
| bonsai-2026-10-12 | 44 | 25 | 21 | 21/25 (0.84) | 903.5 | 16.5 | 19/0/0/7/0/18 |
| w2-think-drop | 44 | 21 | 19 | 19/21 (0.9047619047619048) | 1198.3 | 18.0 | 14/0/0/7/0/23 |
| w2-reasoning-budget | 9 | 5 | 2 | 2/5 (0.4) | 1129.2 | 39 | 3/0/1/1/0/4 |

| arm | timeout | ctx overflow | output limit | no request | invalid | compactions | edit-like err rate |
|---|---|---|---|---|---|---|---|
| bonsai-2026-10-12-honest | 15 | 0 | 2 | 17 | 0 | 29 | 0.1786 |
| bonsai-2026-10-12 | 17 | 3 | 2 | 18 | 1 | 32 | 0.3051 |
| w2-think-drop | 22 | 0 | 0 | 23 | 0 | 5 | 0.339 |
| w2-reasoning-budget | 4 | 0 | 0 | 4 | 0 | 7 | 0.5667 |

| arm | decode s | prefill s | sum predicted_n | sum prompt_n | max prompt tokens |
|---|---|---|---|---|---|
| bonsai-2026-10-12-honest | 667.216 | 61.339 | 26953.0 | 55307.5 | 46506.5 |
| bonsai-2026-10-12 | 780.795 | 87.321 | 31329.0 | 78830.5 | 49037.5 |
| w2-think-drop | 523.356 | 312.901 | 21879.5 | 285636.5 | 38343.0 |
| w2-reasoning-budget | 974.612 | 97.752 | 39754 | 82962 | 52175 |

(tap columns are per-attempt medians)

## Tool calls / errors

- bonsai-2026-10-12-honest: bash 672/68 err, edit 56/10 err, read 277/2 err, submit_request 27/0 err, write 10/0 err
- bonsai-2026-10-12: bash 712/74 err, edit 59/18 err, read 309/1 err, submit_request 30/4 err, write 11/2 err
- w2-think-drop: bash 639/67 err, edit 59/20 err, read 210/2 err, submit_request 21/0 err, write 11/0 err
- w2-reasoning-budget: bash 257/35 err, edit 30/17 err, read 65/0 err, submit_request 5/0 err, write 7/0 err

## Extension actions

- bonsai-2026-10-12-honest: none
- bonsai-2026-10-12: none
- w2-think-drop: {'drop_old_thinking:removed_blocks': 5493, 'drop_old_thinking:removed_chars': 14828758, 'drop_old_thinking:request': 771}
- w2-reasoning-budget: {'reasoning_budget:request': 336}

## Against the baseline

(valid and kind-match comparisons are rates; median wall is seconds. Each arm is compared on its own cases: w2-think-drop 22, w2-reasoning-budget 9.)

| arm | metric | arm | baseline | delta | 95% CI | spread S | beyond spread |
|---|---|---|---|---|---|---|---|
| w2-think-drop | valid | 0.477 | 0.614 | -0.136 | [-0.273, -0.023] | 0.045 | True |
| w2-think-drop | kind_match | 0.432 | 0.455 | -0.023 | [-0.114, 0.068] | 0.091 | False |
| w2-think-drop | median_wall_s | 1198.3 | 739.45 | 458.85 | [0.0, 588.3] | 176.55 | False |
| w2-reasoning-budget | valid | 0.556 | 0.722 | -0.167 | [-0.444, 0.111] | 0.111 | False |
| w2-reasoning-budget | kind_match | 0.222 | 0.333 | -0.111 | [-0.389, 0.222] | 0.222 | False |
| w2-reasoning-budget | median_wall_s | 1129.2 | 789.55 | 339.65 | [-423.8, 648.3] | 293.3 | False |

## Screen interpretation and mechanism statistics

**Think-drop.** Across 44 attempts the extension removed 14,828,758 reasoning characters: median 257,376.5 characters per attempt (mean 337,017.2). The median uncached `prompt_n` per request rose from 905 for the honest baseline to 16,853 here (+15,948), consistent with the expected re-prefill cost after rewriting an earlier assistant message. It eliminated the two honest-baseline output-limit attempts but had 22 timeouts versus 15/44, and its valid-request rate fell by 0.136, which is beyond S=0.045 (CI excludes zero). Its kind-match delta (-0.023) is within twice that metric's S (0.182), so it remains a repeat-2 candidate for that noisy screen metric; this is not evidence of a win.

**Reasoning budget.** The budget fields were injected on all 336 requests, or median 40 requests per attempt (mean 37.3), at the fixed 1,024-token setting. It had zero output limits and four timeouts in its nine N=1 signal attempts; the honest baseline has zero output limits and six timeouts across its two repeats of those nine cases (3/9 when expressed per repeat). None of this arm's deltas is beyond spread, and all three CIs include zero. It is therefore a repeat-2 candidate: every absolute delta is within twice S on the nine-case screen, but its point estimates are unfavorable, so this is explicitly not a claimed benefit.

These N=1 findings are screens only. No repeat-2 run was started in this item. There are no model SHA-256 or llama-swap-entry mismatch warnings from `compare.py`.
