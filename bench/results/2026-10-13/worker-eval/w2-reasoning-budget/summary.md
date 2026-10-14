# Worker-eval deterministic summary

Rates: valid requests and first kind-match rate use all attempts; the second kind-match rate uses valid requests. Timeout, context-overflow, and output-limit flags (and the other failure flags in detailed metrics) use all attempts as their denominator and may overlap.

| Case | Attempts | Valid requests | Kind matches / all | Kind matches / valid | Median wall s | Median turns |
|---|---:|---:|---:|---:|---:|---:|
| Pooled | 9 | 5 (55.6%) | 2 (22.2%) | 2 (40.0%) | 1129.2 | 39 |
| m1-ngram-replay-set-r9-870367a83103 | 1 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.3 | 47 |
| m1-ngram-replay-set-r10-0046c6599fd4 | 1 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.3 | 51 |
| m1-ngram-replay-set-r11-fe779856b52c | 1 | 1 (100.0%) | 0 (0.0%) | 0 (0.0%) | 512.4 | 26 |
| m1-ngram-spec-replay-r3-b72fe4dade49 | 1 | 1 (100.0%) | 1 (100.0%) | 1 (100.0%) | 443.4 | 25 |
| m1-ngram-spec-replay-r4-1147202353a6 | 1 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.3 | 51 |
| m1-ngram-spec-replay-r10-dc0c818a5351 | 1 | 1 (100.0%) | 0 (0.0%) | 0 (0.0%) | 316.3 | 24 |
| m1-ngram-decide-r2-e17c18c1927d | 1 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.3 | 39 |
| m1-ngram-decide-r3-85bb90579f2f | 1 | 1 (100.0%) | 1 (100.0%) | 1 (100.0%) | 1129.2 | 53 |
| m1-ngram-write-up-r3-aee7d1507663 | 1 | 1 (100.0%) | 0 (0.0%) | 0 (0.0%) | 231.2 | 16 |

## Failure modes

Flag denominator: all attempts; flags may overlap.

| Flag | Count |
|---|---:|
| timeout | 4 |
| context_overflow | 0 |
| output_limit | 0 |
| rate_limit | 0 |
| pi_exit_nonzero | 0 |
| unclassified no-request failures | 0 |
| unclassified invalid-request failures | 0 |

## Invalid or absent requests

| Case | Repeat | Type | Source | Flags | Validation errors | Last stop |
|---|---:|---|---|---|---|---|
| m1-ngram-replay-set-r9-870367a83103 | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r10-0046c6599fd4 | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-spec-replay-r4-1147202353a6 | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-decide-r2-e17c18c1927d | 1 | no_request | none | timeout | no request | toolUse |

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
      "median_turns": 39,
      "median_wall_s": 1200.3,
      "tool_calls_by_tool": {
        "bash": 28,
        "edit": 8,
        "read": 8,
        "write": 1
      },
      "tool_calls_total": 45,
      "tool_errors_by_tool": {
        "bash": 2,
        "edit": 5
      },
      "tool_errors_total": 7,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-decide-r3-85bb90579f2f": {
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
      "median_turns": 53,
      "median_wall_s": 1129.2,
      "tool_calls_by_tool": {
        "bash": 36,
        "edit": 12,
        "read": 6,
        "submit_request": 1,
        "write": 1
      },
      "tool_calls_total": 56,
      "tool_errors_by_tool": {
        "bash": 8,
        "edit": 8
      },
      "tool_errors_total": 16,
      "valid_request_rate": 1.0,
      "valid_requests": 1
    },
    "m1-ngram-replay-set-r10-0046c6599fd4": {
      "attempts": 1,
      "compactions": {
        "end_total": 2,
        "start_total": 2
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
      "median_turns": 51,
      "median_wall_s": 1200.3,
      "tool_calls_by_tool": {
        "bash": 56,
        "read": 5
      },
      "tool_calls_total": 61,
      "tool_errors_by_tool": {
        "bash": 5
      },
      "tool_errors_total": 5,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-replay-set-r11-fe779856b52c": {
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
      "median_turns": 26,
      "median_wall_s": 512.4,
      "tool_calls_by_tool": {
        "bash": 17,
        "edit": 2,
        "read": 6,
        "submit_request": 1
      },
      "tool_calls_total": 26,
      "tool_errors_by_tool": {
        "bash": 3
      },
      "tool_errors_total": 3,
      "valid_request_rate": 1.0,
      "valid_requests": 1
    },
    "m1-ngram-replay-set-r9-870367a83103": {
      "attempts": 1,
      "compactions": {
        "end_total": 2,
        "start_total": 2
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
      "median_turns": 47,
      "median_wall_s": 1200.3,
      "tool_calls_by_tool": {
        "bash": 49,
        "read": 9
      },
      "tool_calls_total": 58,
      "tool_errors_by_tool": {
        "bash": 5
      },
      "tool_errors_total": 5,
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
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": 0.0,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 1
      },
      "median_turns": 24,
      "median_wall_s": 316.3,
      "tool_calls_by_tool": {
        "bash": 15,
        "edit": 4,
        "read": 3,
        "submit_request": 1,
        "write": 1
      },
      "tool_calls_total": 24,
      "tool_errors_by_tool": {
        "bash": 1,
        "edit": 1
      },
      "tool_errors_total": 2,
      "valid_request_rate": 1.0,
      "valid_requests": 1
    },
    "m1-ngram-spec-replay-r3-b72fe4dade49": {
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
      "median_turns": 25,
      "median_wall_s": 443.4,
      "tool_calls_by_tool": {
        "bash": 23,
        "submit_request": 1,
        "write": 1
      },
      "tool_calls_total": 25,
      "tool_errors_by_tool": {
        "bash": 7
      },
      "tool_errors_total": 7,
      "valid_request_rate": 1.0,
      "valid_requests": 1
    },
    "m1-ngram-spec-replay-r4-1147202353a6": {
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
      "median_turns": 51,
      "median_wall_s": 1200.3,
      "tool_calls_by_tool": {
        "bash": 26,
        "edit": 4,
        "read": 19,
        "write": 3
      },
      "tool_calls_total": 52,
      "tool_errors_by_tool": {
        "bash": 3,
        "edit": 3
      },
      "tool_errors_total": 6,
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
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": 0.0,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 1
      },
      "median_turns": 16,
      "median_wall_s": 231.2,
      "tool_calls_by_tool": {
        "bash": 7,
        "read": 9,
        "submit_request": 1
      },
      "tool_calls_total": 17,
      "tool_errors_by_tool": {
        "bash": 1
      },
      "tool_errors_total": 1,
      "valid_request_rate": 1.0,
      "valid_requests": 1
    }
  },
  "pooled": {
    "attempts": 9,
    "compactions": {
      "end_total": 7,
      "start_total": 7
    },
    "failure_flags": {
      "counts": {
        "context_overflow": 0,
        "output_limit": 0,
        "pi_exit_nonzero": 0,
        "rate_limit": 0,
        "timeout": 4
      },
      "denominator": "all attempts; flags may overlap"
    },
    "kind_match_rate_all_attempts": 0.2222222222222222,
    "kind_match_rate_valid_requests": 0.4,
    "kind_matches": 2,
    "kind_matches_among_valid_requests": 2,
    "last_stop_reasons": {
      "toolUse": 9
    },
    "median_turns": 39,
    "median_wall_s": 1129.2,
    "tool_calls_by_tool": {
      "bash": 257,
      "edit": 30,
      "read": 65,
      "submit_request": 5,
      "write": 7
    },
    "tool_calls_total": 364,
    "tool_errors_by_tool": {
      "bash": 35,
      "edit": 17
    },
    "tool_errors_total": 52,
    "valid_request_rate": 0.5555555555555556,
    "valid_requests": 5
  }
}
```
