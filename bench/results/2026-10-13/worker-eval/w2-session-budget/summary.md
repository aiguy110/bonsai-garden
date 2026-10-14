# Worker-eval deterministic summary

Rates: valid requests and first kind-match rate use all attempts; the second kind-match rate uses valid requests. Timeout, context-overflow, and output-limit flags (and the other failure flags in detailed metrics) use all attempts as their denominator and may overlap.

| Case | Attempts | Valid requests | Kind matches / all | Kind matches / valid | Median wall s | Median turns |
|---|---:|---:|---:|---:|---:|---:|
| Pooled | 9 | 6 (66.7%) | 3 (33.3%) | 3 (50.0%) | 834.0 | 17 |
| m1-ngram-replay-set-r9-870367a83103 | 1 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.3 | 21 |
| m1-ngram-replay-set-r10-0046c6599fd4 | 1 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 853.1 | 9 |
| m1-ngram-replay-set-r11-fe779856b52c | 1 | 1 (100.0%) | 0 (0.0%) | 0 (0.0%) | 1067.8 | 22 |
| m1-ngram-spec-replay-r3-b72fe4dade49 | 1 | 1 (100.0%) | 1 (100.0%) | 1 (100.0%) | 773.7 | 14 |
| m1-ngram-spec-replay-r4-1147202353a6 | 1 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.3 | 13 |
| m1-ngram-spec-replay-r10-dc0c818a5351 | 1 | 1 (100.0%) | 1 (100.0%) | 1 (100.0%) | 670.2 | 22 |
| m1-ngram-decide-r2-e17c18c1927d | 1 | 1 (100.0%) | 0 (0.0%) | 0 (0.0%) | 834.0 | 18 |
| m1-ngram-decide-r3-85bb90579f2f | 1 | 1 (100.0%) | 0 (0.0%) | 0 (0.0%) | 592.8 | 17 |
| m1-ngram-write-up-r3-aee7d1507663 | 1 | 1 (100.0%) | 1 (100.0%) | 1 (100.0%) | 312.7 | 7 |

## Failure modes

Flag denominator: all attempts; flags may overlap.

| Flag | Count |
|---|---:|
| timeout | 2 |
| context_overflow | 0 |
| output_limit | 1 |
| rate_limit | 0 |
| pi_exit_nonzero | 0 |
| unclassified no-request failures | 0 |
| unclassified invalid-request failures | 0 |

## Invalid or absent requests

| Case | Repeat | Type | Source | Flags | Validation errors | Last stop |
|---|---:|---|---|---|---|---|
| m1-ngram-replay-set-r9-870367a83103 | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r10-0046c6599fd4 | 1 | no_request | none | output_limit | no request | length |
| m1-ngram-spec-replay-r4-1147202353a6 | 1 | no_request | none | timeout | no request | error |

## Detailed deterministic metrics

```json
{
  "per_case": {
    "m1-ngram-decide-r2-e17c18c1927d": {
      "attempts": 1,
      "compactions": {
        "end_total": 1,
        "start_total": 1
      },
      "failure_flags": {
        "counts": {
          "context_overflow": 0,
          "output_limit": 0,
          "pi_exit_nonzero": 0,
          "rate_limit": 0,
          "timeout": 0
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": 0.0,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 1
      },
      "median_turns": 18,
      "median_wall_s": 834.0,
      "tool_calls_by_tool": {
        "bash": 12,
        "edit": 3,
        "read": 6,
        "submit_request": 2
      },
      "tool_calls_total": 23,
      "tool_errors_by_tool": {
        "bash": 1,
        "edit": 1,
        "submit_request": 1
      },
      "tool_errors_total": 3,
      "valid_request_rate": 1.0,
      "valid_requests": 1
    },
    "m1-ngram-decide-r3-85bb90579f2f": {
      "attempts": 1,
      "compactions": {
        "end_total": 0,
        "start_total": 0
      },
      "failure_flags": {
        "counts": {
          "context_overflow": 0,
          "output_limit": 0,
          "pi_exit_nonzero": 0,
          "rate_limit": 0,
          "timeout": 0
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": 0.0,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 1
      },
      "median_turns": 17,
      "median_wall_s": 592.8,
      "tool_calls_by_tool": {
        "bash": 12,
        "edit": 5,
        "read": 3,
        "submit_request": 1
      },
      "tool_calls_total": 21,
      "tool_errors_by_tool": {
        "bash": 1,
        "edit": 2
      },
      "tool_errors_total": 3,
      "valid_request_rate": 1.0,
      "valid_requests": 1
    },
    "m1-ngram-replay-set-r10-0046c6599fd4": {
      "attempts": 1,
      "compactions": {
        "end_total": 1,
        "start_total": 1
      },
      "failure_flags": {
        "counts": {
          "context_overflow": 0,
          "output_limit": 1,
          "pi_exit_nonzero": 0,
          "rate_limit": 0,
          "timeout": 0
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": null,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "length": 1
      },
      "median_turns": 9,
      "median_wall_s": 853.1,
      "tool_calls_by_tool": {
        "bash": 10,
        "read": 3
      },
      "tool_calls_total": 13,
      "tool_errors_by_tool": {
        "bash": 3
      },
      "tool_errors_total": 3,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-replay-set-r11-fe779856b52c": {
      "attempts": 1,
      "compactions": {
        "end_total": 1,
        "start_total": 1
      },
      "failure_flags": {
        "counts": {
          "context_overflow": 0,
          "output_limit": 0,
          "pi_exit_nonzero": 0,
          "rate_limit": 0,
          "timeout": 0
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": 0.0,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 1
      },
      "median_turns": 22,
      "median_wall_s": 1067.8,
      "tool_calls_by_tool": {
        "bash": 8,
        "edit": 3,
        "read": 12,
        "submit_request": 1
      },
      "tool_calls_total": 24,
      "tool_errors_by_tool": {
        "bash": 2
      },
      "tool_errors_total": 2,
      "valid_request_rate": 1.0,
      "valid_requests": 1
    },
    "m1-ngram-replay-set-r9-870367a83103": {
      "attempts": 1,
      "compactions": {
        "end_total": 1,
        "start_total": 1
      },
      "failure_flags": {
        "counts": {
          "context_overflow": 0,
          "output_limit": 0,
          "pi_exit_nonzero": 0,
          "rate_limit": 0,
          "timeout": 1
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": null,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 1
      },
      "median_turns": 21,
      "median_wall_s": 1200.3,
      "tool_calls_by_tool": {
        "bash": 25,
        "read": 2
      },
      "tool_calls_total": 27,
      "tool_errors_by_tool": {
        "bash": 1
      },
      "tool_errors_total": 1,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-spec-replay-r10-dc0c818a5351": {
      "attempts": 1,
      "compactions": {
        "end_total": 0,
        "start_total": 0
      },
      "failure_flags": {
        "counts": {
          "context_overflow": 0,
          "output_limit": 0,
          "pi_exit_nonzero": 0,
          "rate_limit": 0,
          "timeout": 0
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 1.0,
      "kind_match_rate_valid_requests": 1.0,
      "kind_matches": 1,
      "kind_matches_among_valid_requests": 1,
      "last_stop_reasons": {
        "toolUse": 1
      },
      "median_turns": 22,
      "median_wall_s": 670.2,
      "tool_calls_by_tool": {
        "bash": 19,
        "read": 3,
        "submit_request": 1
      },
      "tool_calls_total": 23,
      "tool_errors_by_tool": {
        "bash": 3
      },
      "tool_errors_total": 3,
      "valid_request_rate": 1.0,
      "valid_requests": 1
    },
    "m1-ngram-spec-replay-r3-b72fe4dade49": {
      "attempts": 1,
      "compactions": {
        "end_total": 1,
        "start_total": 1
      },
      "failure_flags": {
        "counts": {
          "context_overflow": 0,
          "output_limit": 0,
          "pi_exit_nonzero": 0,
          "rate_limit": 0,
          "timeout": 0
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 1.0,
      "kind_match_rate_valid_requests": 1.0,
      "kind_matches": 1,
      "kind_matches_among_valid_requests": 1,
      "last_stop_reasons": {
        "toolUse": 1
      },
      "median_turns": 14,
      "median_wall_s": 773.7,
      "tool_calls_by_tool": {
        "bash": 15,
        "edit": 1,
        "read": 2,
        "submit_request": 1
      },
      "tool_calls_total": 19,
      "tool_errors_by_tool": {
        "bash": 1
      },
      "tool_errors_total": 1,
      "valid_request_rate": 1.0,
      "valid_requests": 1
    },
    "m1-ngram-spec-replay-r4-1147202353a6": {
      "attempts": 1,
      "compactions": {
        "end_total": 0,
        "start_total": 0
      },
      "failure_flags": {
        "counts": {
          "context_overflow": 0,
          "output_limit": 0,
          "pi_exit_nonzero": 0,
          "rate_limit": 0,
          "timeout": 1
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": null,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "error": 1
      },
      "median_turns": 13,
      "median_wall_s": 1200.3,
      "tool_calls_by_tool": {
        "bash": 8,
        "read": 6
      },
      "tool_calls_total": 14,
      "tool_errors_by_tool": {
        "bash": 1
      },
      "tool_errors_total": 1,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-write-up-r3-aee7d1507663": {
      "attempts": 1,
      "compactions": {
        "end_total": 0,
        "start_total": 0
      },
      "failure_flags": {
        "counts": {
          "context_overflow": 0,
          "output_limit": 0,
          "pi_exit_nonzero": 0,
          "rate_limit": 0,
          "timeout": 0
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 1.0,
      "kind_match_rate_valid_requests": 1.0,
      "kind_matches": 1,
      "kind_matches_among_valid_requests": 1,
      "last_stop_reasons": {
        "toolUse": 1
      },
      "median_turns": 7,
      "median_wall_s": 312.7,
      "tool_calls_by_tool": {
        "bash": 5,
        "read": 9,
        "submit_request": 1
      },
      "tool_calls_total": 15,
      "tool_errors_by_tool": {},
      "tool_errors_total": 0,
      "valid_request_rate": 1.0,
      "valid_requests": 1
    }
  },
  "pooled": {
    "attempts": 9,
    "compactions": {
      "end_total": 5,
      "start_total": 5
    },
    "failure_flags": {
      "counts": {
        "context_overflow": 0,
        "output_limit": 1,
        "pi_exit_nonzero": 0,
        "rate_limit": 0,
        "timeout": 2
      },
      "denominator": "all attempts; flags may overlap"
    },
    "kind_match_rate_all_attempts": 0.3333333333333333,
    "kind_match_rate_valid_requests": 0.5,
    "kind_matches": 3,
    "kind_matches_among_valid_requests": 3,
    "last_stop_reasons": {
      "error": 1,
      "length": 1,
      "toolUse": 7
    },
    "median_turns": 17,
    "median_wall_s": 834.0,
    "tool_calls_by_tool": {
      "bash": 114,
      "edit": 12,
      "read": 46,
      "submit_request": 7
    },
    "tool_calls_total": 179,
    "tool_errors_by_tool": {
      "bash": 13,
      "edit": 3,
      "submit_request": 1
    },
    "tool_errors_total": 17,
    "valid_request_rate": 0.6666666666666666,
    "valid_requests": 6
  }
}
```
