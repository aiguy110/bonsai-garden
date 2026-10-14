# Worker-eval deterministic summary

Rates: valid requests and first kind-match rate use all attempts; the second kind-match rate uses valid requests. Timeout, context-overflow, and output-limit flags (and the other failure flags in detailed metrics) use all attempts as their denominator and may overlap.

| Case | Attempts | Valid requests | Kind matches / all | Kind matches / valid | Median wall s | Median turns |
|---|---:|---:|---:|---:|---:|---:|
| Pooled | 44 | 21 (47.7%) | 19 (43.2%) | 19 (90.5%) | 1198.3 | 18.0 |
| m1-ngram-replay-set-r6-9cf273aef422 | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.3 | 16.5 |
| m1-ngram-replay-set-r7-52b0d2b42358 | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.3 | 19.5 |
| m1-ngram-replay-set-r8-4324817a7216 | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.35 | 21.5 |
| m1-ngram-replay-set-r9-870367a83103 | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 874.4 | 14.0 |
| m1-ngram-replay-set-r10-0046c6599fd4 | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.3 | 15.5 |
| m1-ngram-replay-set-r11-fe779856b52c | 2 | 1 (50.0%) | 1 (50.0%) | 1 (100.0%) | 950.7 | 12.5 |
| m1-ngram-replay-set-r12-e62a974c8e88 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 711.9 | 21.0 |
| m1-ngram-spec-replay-r1-7be283086913 | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.3 | 19.5 |
| m1-ngram-spec-replay-r2-aa8e7eef2474 | 2 | 1 (50.0%) | 1 (50.0%) | 1 (100.0%) | 789.3 | 15.0 |
| m1-ngram-spec-replay-r3-b72fe4dade49 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 909.55 | 21.0 |
| m1-ngram-spec-replay-r4-1147202353a6 | 2 | 1 (50.0%) | 1 (50.0%) | 1 (100.0%) | 889.5500000000001 | 16.0 |
| m1-ngram-spec-replay-r5-144acae8e198 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 949.8 | 17.5 |
| m1-ngram-spec-replay-r5-5c5d98bf3537 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 222.60000000000002 | 9.0 |
| m1-ngram-spec-replay-r6-ee9150033cd8 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 242.05 | 8.0 |
| m1-ngram-spec-replay-r7-74c6eafebda5 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 498.85 | 13.5 |
| m1-ngram-spec-replay-r10-dc0c818a5351 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 719.5 | 21.0 |
| m1-ngram-spec-replay-r11-f096b0e52769 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 610.85 | 21.0 |
| m1-ngram-decide-r1-480691022b4e | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.4 | 21.0 |
| m1-ngram-decide-r2-e17c18c1927d | 2 | 1 (50.0%) | 0 (0.0%) | 0 (0.0%) | 948.2 | 11.0 |
| m1-ngram-decide-r3-85bb90579f2f | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.35 | 23.0 |
| m1-ngram-write-up-r2-cebbd5fef63b | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.4 | 22.0 |
| m1-ngram-write-up-r3-aee7d1507663 | 2 | 1 (50.0%) | 0 (0.0%) | 0 (0.0%) | 808.5 | 16.5 |

## Failure modes

Flag denominator: all attempts; flags may overlap.

| Flag | Count |
|---|---:|
| timeout | 22 |
| context_overflow | 0 |
| output_limit | 0 |
| rate_limit | 0 |
| pi_exit_nonzero | 0 |
| unclassified no-request failures | 1 |
| unclassified invalid-request failures | 0 |

## Invalid or absent requests

| Case | Repeat | Type | Source | Flags | Validation errors | Last stop |
|---|---:|---|---|---|---|---|
| m1-ngram-replay-set-r6-9cf273aef422 | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r7-52b0d2b42358 | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r8-4324817a7216 | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r9-870367a83103 | 1 | no_request | none | none | no request | stop |
| m1-ngram-replay-set-r10-0046c6599fd4 | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r11-fe779856b52c | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-spec-replay-r1-7be283086913 | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-spec-replay-r4-1147202353a6 | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-decide-r1-480691022b4e | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-decide-r3-85bb90579f2f | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-write-up-r2-cebbd5fef63b | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-write-up-r3-aee7d1507663 | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r6-9cf273aef422 | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r7-52b0d2b42358 | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r8-4324817a7216 | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r9-870367a83103 | 2 | no_request | none | timeout | no request | error |
| m1-ngram-replay-set-r10-0046c6599fd4 | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-spec-replay-r1-7be283086913 | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-spec-replay-r2-aa8e7eef2474 | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-decide-r1-480691022b4e | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-decide-r2-e17c18c1927d | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-decide-r3-85bb90579f2f | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-write-up-r2-cebbd5fef63b | 2 | no_request | none | timeout | no request | toolUse |

## Detailed deterministic metrics

```json
{
  "per_case": {
    "m1-ngram-decide-r1-480691022b4e": {
      "attempts": 2,
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
          "timeout": 2
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": null,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 21.0,
      "median_wall_s": 1200.4,
      "tool_calls_by_tool": {
        "bash": 48,
        "edit": 1,
        "read": 1,
        "write": 2
      },
      "tool_calls_total": 52,
      "tool_errors_by_tool": {
        "bash": 8
      },
      "tool_errors_total": 8,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-decide-r2-e17c18c1927d": {
      "attempts": 2,
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
      "kind_match_rate_valid_requests": 0.0,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 11.0,
      "median_wall_s": 948.2,
      "tool_calls_by_tool": {
        "bash": 21,
        "edit": 1,
        "read": 9,
        "submit_request": 1,
        "write": 1
      },
      "tool_calls_total": 33,
      "tool_errors_by_tool": {
        "bash": 3
      },
      "tool_errors_total": 3,
      "valid_request_rate": 0.5,
      "valid_requests": 1
    },
    "m1-ngram-decide-r3-85bb90579f2f": {
      "attempts": 2,
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
          "timeout": 2
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": null,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 23.0,
      "median_wall_s": 1200.35,
      "tool_calls_by_tool": {
        "bash": 35,
        "edit": 11,
        "read": 7,
        "write": 1
      },
      "tool_calls_total": 54,
      "tool_errors_by_tool": {
        "bash": 4,
        "edit": 7
      },
      "tool_errors_total": 11,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-replay-set-r10-0046c6599fd4": {
      "attempts": 2,
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
          "timeout": 2
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": null,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 15.5,
      "median_wall_s": 1200.3,
      "tool_calls_by_tool": {
        "bash": 29,
        "edit": 1,
        "read": 8,
        "write": 1
      },
      "tool_calls_total": 39,
      "tool_errors_by_tool": {
        "bash": 3
      },
      "tool_errors_total": 3,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-replay-set-r11-fe779856b52c": {
      "attempts": 2,
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
      "kind_match_rate_all_attempts": 0.5,
      "kind_match_rate_valid_requests": 1.0,
      "kind_matches": 1,
      "kind_matches_among_valid_requests": 1,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 12.5,
      "median_wall_s": 950.7,
      "tool_calls_by_tool": {
        "bash": 15,
        "edit": 4,
        "read": 15,
        "submit_request": 1
      },
      "tool_calls_total": 35,
      "tool_errors_by_tool": {
        "edit": 2
      },
      "tool_errors_total": 2,
      "valid_request_rate": 0.5,
      "valid_requests": 1
    },
    "m1-ngram-replay-set-r12-e62a974c8e88": {
      "attempts": 2,
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
      "kind_matches": 2,
      "kind_matches_among_valid_requests": 2,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 21.0,
      "median_wall_s": 711.9,
      "tool_calls_by_tool": {
        "bash": 30,
        "edit": 5,
        "read": 7,
        "submit_request": 2
      },
      "tool_calls_total": 44,
      "tool_errors_by_tool": {
        "bash": 2,
        "edit": 2
      },
      "tool_errors_total": 4,
      "valid_request_rate": 1.0,
      "valid_requests": 2
    },
    "m1-ngram-replay-set-r6-9cf273aef422": {
      "attempts": 2,
      "compactions": {
        "end_total": 0,
        "start_total": 1
      },
      "failure_flags": {
        "counts": {
          "context_overflow": 0,
          "output_limit": 0,
          "pi_exit_nonzero": 0,
          "rate_limit": 0,
          "timeout": 2
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": null,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 16.5,
      "median_wall_s": 1200.3,
      "tool_calls_by_tool": {
        "bash": 37,
        "read": 11
      },
      "tool_calls_total": 48,
      "tool_errors_by_tool": {
        "bash": 3
      },
      "tool_errors_total": 3,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-replay-set-r7-52b0d2b42358": {
      "attempts": 2,
      "compactions": {
        "end_total": 1,
        "start_total": 2
      },
      "failure_flags": {
        "counts": {
          "context_overflow": 0,
          "output_limit": 0,
          "pi_exit_nonzero": 0,
          "rate_limit": 0,
          "timeout": 2
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": null,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 19.5,
      "median_wall_s": 1200.3,
      "tool_calls_by_tool": {
        "bash": 41,
        "read": 9
      },
      "tool_calls_total": 50,
      "tool_errors_by_tool": {
        "bash": 3
      },
      "tool_errors_total": 3,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-replay-set-r8-4324817a7216": {
      "attempts": 2,
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
          "timeout": 2
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": null,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 21.5,
      "median_wall_s": 1200.35,
      "tool_calls_by_tool": {
        "bash": 49,
        "read": 13
      },
      "tool_calls_total": 62,
      "tool_errors_by_tool": {
        "bash": 2
      },
      "tool_errors_total": 2,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-replay-set-r9-870367a83103": {
      "attempts": 2,
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
        "error": 1,
        "stop": 1
      },
      "median_turns": 14.0,
      "median_wall_s": 874.4,
      "tool_calls_by_tool": {
        "bash": 28,
        "read": 6
      },
      "tool_calls_total": 34,
      "tool_errors_by_tool": {
        "bash": 1
      },
      "tool_errors_total": 1,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-spec-replay-r1-7be283086913": {
      "attempts": 2,
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
          "timeout": 2
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": null,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 19.5,
      "median_wall_s": 1200.3,
      "tool_calls_by_tool": {
        "bash": 30,
        "read": 16
      },
      "tool_calls_total": 46,
      "tool_errors_by_tool": {
        "bash": 2
      },
      "tool_errors_total": 2,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-spec-replay-r10-dc0c818a5351": {
      "attempts": 2,
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
      "kind_matches": 2,
      "kind_matches_among_valid_requests": 2,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 21.0,
      "median_wall_s": 719.5,
      "tool_calls_by_tool": {
        "bash": 38,
        "edit": 2,
        "read": 4,
        "submit_request": 2,
        "write": 5
      },
      "tool_calls_total": 51,
      "tool_errors_by_tool": {
        "bash": 3
      },
      "tool_errors_total": 3,
      "valid_request_rate": 1.0,
      "valid_requests": 2
    },
    "m1-ngram-spec-replay-r11-f096b0e52769": {
      "attempts": 2,
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
      "kind_matches": 2,
      "kind_matches_among_valid_requests": 2,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 21.0,
      "median_wall_s": 610.85,
      "tool_calls_by_tool": {
        "bash": 30,
        "edit": 6,
        "read": 12,
        "submit_request": 2
      },
      "tool_calls_total": 50,
      "tool_errors_by_tool": {
        "bash": 3,
        "edit": 2
      },
      "tool_errors_total": 5,
      "valid_request_rate": 1.0,
      "valid_requests": 2
    },
    "m1-ngram-spec-replay-r2-aa8e7eef2474": {
      "attempts": 2,
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
      "kind_match_rate_all_attempts": 0.5,
      "kind_match_rate_valid_requests": 1.0,
      "kind_matches": 1,
      "kind_matches_among_valid_requests": 1,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 15.0,
      "median_wall_s": 789.3,
      "tool_calls_by_tool": {
        "bash": 17,
        "edit": 7,
        "read": 13,
        "submit_request": 1
      },
      "tool_calls_total": 38,
      "tool_errors_by_tool": {
        "bash": 1,
        "edit": 1
      },
      "tool_errors_total": 2,
      "valid_request_rate": 0.5,
      "valid_requests": 1
    },
    "m1-ngram-spec-replay-r3-b72fe4dade49": {
      "attempts": 2,
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
      "kind_matches": 2,
      "kind_matches_among_valid_requests": 2,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 21.0,
      "median_wall_s": 909.55,
      "tool_calls_by_tool": {
        "bash": 39,
        "edit": 4,
        "read": 5,
        "submit_request": 2
      },
      "tool_calls_total": 50,
      "tool_errors_by_tool": {
        "bash": 7
      },
      "tool_errors_total": 7,
      "valid_request_rate": 1.0,
      "valid_requests": 2
    },
    "m1-ngram-spec-replay-r4-1147202353a6": {
      "attempts": 2,
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
      "kind_match_rate_all_attempts": 0.5,
      "kind_match_rate_valid_requests": 1.0,
      "kind_matches": 1,
      "kind_matches_among_valid_requests": 1,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 16.0,
      "median_wall_s": 889.5500000000001,
      "tool_calls_by_tool": {
        "bash": 26,
        "edit": 5,
        "read": 8,
        "submit_request": 1
      },
      "tool_calls_total": 40,
      "tool_errors_by_tool": {
        "bash": 5,
        "edit": 4
      },
      "tool_errors_total": 9,
      "valid_request_rate": 0.5,
      "valid_requests": 1
    },
    "m1-ngram-spec-replay-r5-144acae8e198": {
      "attempts": 2,
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
      "kind_matches": 2,
      "kind_matches_among_valid_requests": 2,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 17.5,
      "median_wall_s": 949.8,
      "tool_calls_by_tool": {
        "bash": 20,
        "edit": 6,
        "read": 11,
        "submit_request": 2,
        "write": 1
      },
      "tool_calls_total": 40,
      "tool_errors_by_tool": {
        "bash": 1,
        "edit": 2
      },
      "tool_errors_total": 3,
      "valid_request_rate": 1.0,
      "valid_requests": 2
    },
    "m1-ngram-spec-replay-r5-5c5d98bf3537": {
      "attempts": 2,
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
      "kind_matches": 2,
      "kind_matches_among_valid_requests": 2,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 9.0,
      "median_wall_s": 222.60000000000002,
      "tool_calls_by_tool": {
        "bash": 15,
        "read": 3,
        "submit_request": 2
      },
      "tool_calls_total": 20,
      "tool_errors_by_tool": {
        "bash": 3
      },
      "tool_errors_total": 3,
      "valid_request_rate": 1.0,
      "valid_requests": 2
    },
    "m1-ngram-spec-replay-r6-ee9150033cd8": {
      "attempts": 2,
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
      "kind_matches": 2,
      "kind_matches_among_valid_requests": 2,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 8.0,
      "median_wall_s": 242.05,
      "tool_calls_by_tool": {
        "bash": 8,
        "edit": 2,
        "read": 8,
        "submit_request": 2
      },
      "tool_calls_total": 20,
      "tool_errors_by_tool": {
        "bash": 1
      },
      "tool_errors_total": 1,
      "valid_request_rate": 1.0,
      "valid_requests": 2
    },
    "m1-ngram-spec-replay-r7-74c6eafebda5": {
      "attempts": 2,
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
      "kind_matches": 2,
      "kind_matches_among_valid_requests": 2,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 13.5,
      "median_wall_s": 498.85,
      "tool_calls_by_tool": {
        "bash": 23,
        "read": 8,
        "submit_request": 2
      },
      "tool_calls_total": 33,
      "tool_errors_by_tool": {
        "bash": 1
      },
      "tool_errors_total": 1,
      "valid_request_rate": 1.0,
      "valid_requests": 2
    },
    "m1-ngram-write-up-r2-cebbd5fef63b": {
      "attempts": 2,
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
          "timeout": 2
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": null,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 22.0,
      "median_wall_s": 1200.4,
      "tool_calls_by_tool": {
        "bash": 41,
        "read": 9
      },
      "tool_calls_total": 50,
      "tool_errors_by_tool": {
        "bash": 7
      },
      "tool_errors_total": 7,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-write-up-r3-aee7d1507663": {
      "attempts": 2,
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
      "kind_match_rate_valid_requests": 0.0,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 16.5,
      "median_wall_s": 808.5,
      "tool_calls_by_tool": {
        "bash": 19,
        "edit": 4,
        "read": 27,
        "submit_request": 1
      },
      "tool_calls_total": 51,
      "tool_errors_by_tool": {
        "bash": 4,
        "read": 2
      },
      "tool_errors_total": 6,
      "valid_request_rate": 0.5,
      "valid_requests": 1
    }
  },
  "pooled": {
    "attempts": 44,
    "compactions": {
      "end_total": 3,
      "start_total": 5
    },
    "failure_flags": {
      "counts": {
        "context_overflow": 0,
        "output_limit": 0,
        "pi_exit_nonzero": 0,
        "rate_limit": 0,
        "timeout": 22
      },
      "denominator": "all attempts; flags may overlap"
    },
    "kind_match_rate_all_attempts": 0.4318181818181818,
    "kind_match_rate_valid_requests": 0.9047619047619048,
    "kind_matches": 19,
    "kind_matches_among_valid_requests": 19,
    "last_stop_reasons": {
      "error": 1,
      "stop": 1,
      "toolUse": 42
    },
    "median_turns": 18.0,
    "median_wall_s": 1198.3,
    "tool_calls_by_tool": {
      "bash": 639,
      "edit": 59,
      "read": 210,
      "submit_request": 21,
      "write": 11
    },
    "tool_calls_total": 940,
    "tool_errors_by_tool": {
      "bash": 67,
      "edit": 20,
      "read": 2
    },
    "tool_errors_total": 89,
    "valid_request_rate": 0.4772727272727273,
    "valid_requests": 21
  }
}
```
