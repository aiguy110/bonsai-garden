# Worker-eval deterministic summary

Rates: valid requests and first kind-match rate use all attempts; the second kind-match rate uses valid requests. Timeout, context-overflow, and output-limit flags (and the other failure flags in detailed metrics) use all attempts as their denominator and may overlap.

| Case | Attempts | Valid requests | Kind matches / all | Kind matches / valid | Median wall s | Median turns |
|---|---:|---:|---:|---:|---:|---:|
| Pooled | 44 | 25 (56.8%) | 21 (47.7%) | 21 (84.0%) | 903.5 | 16.5 |
| m1-ngram-replay-set-r6-9cf273aef422 | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.35 | 47.0 |
| m1-ngram-replay-set-r7-52b0d2b42358 | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.45 | 35.0 |
| m1-ngram-replay-set-r8-4324817a7216 | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.4 | 34.0 |
| m1-ngram-replay-set-r9-870367a83103 | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 669.05 | 18.5 |
| m1-ngram-replay-set-r10-0046c6599fd4 | 2 | 1 (50.0%) | 1 (50.0%) | 1 (100.0%) | 1022.2 | 24.0 |
| m1-ngram-replay-set-r11-fe779856b52c | 2 | 1 (50.0%) | 0 (0.0%) | 0 (0.0%) | 1110.95 | 13.5 |
| m1-ngram-replay-set-r12-e62a974c8e88 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 425.25 | 14.0 |
| m1-ngram-spec-replay-r1-7be283086913 | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.3 | 18.5 |
| m1-ngram-spec-replay-r2-aa8e7eef2474 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 771.9000000000001 | 20.0 |
| m1-ngram-spec-replay-r3-b72fe4dade49 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 1043.5 | 31.5 |
| m1-ngram-spec-replay-r4-1147202353a6 | 2 | 1 (50.0%) | 1 (50.0%) | 1 (100.0%) | 1155.25 | 32.5 |
| m1-ngram-spec-replay-r5-144acae8e198 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 179.5 | 6.0 |
| m1-ngram-spec-replay-r5-5c5d98bf3537 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 197.6 | 10.0 |
| m1-ngram-spec-replay-r6-ee9150033cd8 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 228.89999999999998 | 11.0 |
| m1-ngram-spec-replay-r7-74c6eafebda5 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 397.6 | 11.5 |
| m1-ngram-spec-replay-r10-dc0c818a5351 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 555.6 | 26.5 |
| m1-ngram-spec-replay-r11-f096b0e52769 | 2 | 2 (100.0%) | 2 (100.0%) | 2 (100.0%) | 367.75 | 21.0 |
| m1-ngram-decide-r1-480691022b4e | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.5 | 11.0 |
| m1-ngram-decide-r2-e17c18c1927d | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1131.9 | 30.0 |
| m1-ngram-decide-r3-85bb90579f2f | 2 | 2 (100.0%) | 1 (50.0%) | 1 (50.0%) | 661.75 | 14.0 |
| m1-ngram-write-up-r2-cebbd5fef63b | 2 | 0 (0.0%) | 0 (0.0%) | 0 (n/a) | 1200.5 | 24.0 |
| m1-ngram-write-up-r3-aee7d1507663 | 2 | 2 (100.0%) | 0 (0.0%) | 0 (0.0%) | 524.4 | 13.0 |

## Failure modes

Flag denominator: all attempts; flags may overlap.

| Flag | Count |
|---|---:|
| timeout | 17 |
| context_overflow | 3 |
| output_limit | 2 |
| rate_limit | 0 |
| pi_exit_nonzero | 0 |
| unclassified no-request failures | 1 |
| unclassified invalid-request failures | 1 |

## Invalid or absent requests

| Case | Repeat | Type | Source | Flags | Validation errors | Last stop |
|---|---:|---|---|---|---|---|
| m1-ngram-replay-set-r6-9cf273aef422 | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r7-52b0d2b42358 | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r8-4324817a7216 | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r9-870367a83103 | 1 | no_request | none | none | no request | stop |
| m1-ngram-spec-replay-r1-7be283086913 | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-decide-r1-480691022b4e | 1 | no_request | none | timeout, output_limit | no request | length |
| m1-ngram-decide-r2-e17c18c1927d | 1 | invalid_request | tool | none | script /home/dev/garden/bench/spec_summarize.py must be under bench/ or evals/; orchestrator: script must be under bench/ or evals/ | toolUse |
| m1-ngram-write-up-r2-cebbd5fef63b | 1 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r6-9cf273aef422 | 2 | no_request | none | timeout, context_overflow | no request | error |
| m1-ngram-replay-set-r7-52b0d2b42358 | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r8-4324817a7216 | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r9-870367a83103 | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-replay-set-r10-0046c6599fd4 | 2 | no_request | none | timeout, context_overflow | no request | toolUse |
| m1-ngram-replay-set-r11-fe779856b52c | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-spec-replay-r1-7be283086913 | 2 | no_request | none | timeout, output_limit | no request | length |
| m1-ngram-spec-replay-r4-1147202353a6 | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-decide-r1-480691022b4e | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-decide-r2-e17c18c1927d | 2 | no_request | none | timeout | no request | toolUse |
| m1-ngram-write-up-r2-cebbd5fef63b | 2 | no_request | none | timeout | no request | toolUse |

## Detailed deterministic metrics

```json
{
  "per_case": {
    "m1-ngram-decide-r1-480691022b4e": {
      "attempts": 2,
      "compactions": {
        "end_total": 2,
        "start_total": 2
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
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": null,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "length": 1,
        "toolUse": 1
      },
      "median_turns": 11.0,
      "median_wall_s": 1200.5,
      "tool_calls_by_tool": {
        "bash": 24,
        "edit": 2,
        "read": 5,
        "write": 3
      },
      "tool_calls_total": 34,
      "tool_errors_by_tool": {
        "edit": 2,
        "write": 1
      },
      "tool_errors_total": 3,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-decide-r2-e17c18c1927d": {
      "attempts": 2,
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
        "toolUse": 2
      },
      "median_turns": 30.0,
      "median_wall_s": 1131.9,
      "tool_calls_by_tool": {
        "bash": 44,
        "edit": 13,
        "read": 9,
        "submit_request": 3
      },
      "tool_calls_total": 69,
      "tool_errors_by_tool": {
        "bash": 7,
        "edit": 3,
        "submit_request": 2
      },
      "tool_errors_total": 12,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-decide-r3-85bb90579f2f": {
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
          "timeout": 0
        },
        "denominator": "all attempts; flags may overlap"
      },
      "kind_match_rate_all_attempts": 0.5,
      "kind_match_rate_valid_requests": 0.5,
      "kind_matches": 1,
      "kind_matches_among_valid_requests": 1,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 14.0,
      "median_wall_s": 661.75,
      "tool_calls_by_tool": {
        "bash": 24,
        "edit": 3,
        "read": 8,
        "submit_request": 2
      },
      "tool_calls_total": 37,
      "tool_errors_by_tool": {
        "bash": 1,
        "edit": 1
      },
      "tool_errors_total": 2,
      "valid_request_rate": 1.0,
      "valid_requests": 2
    },
    "m1-ngram-replay-set-r10-0046c6599fd4": {
      "attempts": 2,
      "compactions": {
        "end_total": 2,
        "start_total": 2
      },
      "failure_flags": {
        "counts": {
          "context_overflow": 2,
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
      "median_turns": 24.0,
      "median_wall_s": 1022.2,
      "tool_calls_by_tool": {
        "bash": 33,
        "edit": 3,
        "read": 12,
        "submit_request": 2,
        "write": 1
      },
      "tool_calls_total": 51,
      "tool_errors_by_tool": {
        "bash": 3,
        "edit": 1,
        "submit_request": 1
      },
      "tool_errors_total": 5,
      "valid_request_rate": 0.5,
      "valid_requests": 1
    },
    "m1-ngram-replay-set-r11-fe779856b52c": {
      "attempts": 2,
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
      "kind_match_rate_valid_requests": 0.0,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 13.5,
      "median_wall_s": 1110.95,
      "tool_calls_by_tool": {
        "bash": 14,
        "edit": 5,
        "read": 19,
        "submit_request": 2
      },
      "tool_calls_total": 40,
      "tool_errors_by_tool": {
        "edit": 2,
        "submit_request": 1
      },
      "tool_errors_total": 3,
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
      "median_turns": 14.0,
      "median_wall_s": 425.25,
      "tool_calls_by_tool": {
        "bash": 20,
        "edit": 3,
        "read": 9,
        "submit_request": 2
      },
      "tool_calls_total": 34,
      "tool_errors_by_tool": {
        "bash": 3,
        "edit": 1
      },
      "tool_errors_total": 4,
      "valid_request_rate": 1.0,
      "valid_requests": 2
    },
    "m1-ngram-replay-set-r6-9cf273aef422": {
      "attempts": 2,
      "compactions": {
        "end_total": 3,
        "start_total": 4
      },
      "failure_flags": {
        "counts": {
          "context_overflow": 1,
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
        "error": 1,
        "toolUse": 1
      },
      "median_turns": 47.0,
      "median_wall_s": 1200.35,
      "tool_calls_by_tool": {
        "bash": 75,
        "read": 30
      },
      "tool_calls_total": 105,
      "tool_errors_by_tool": {
        "bash": 7
      },
      "tool_errors_total": 7,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-replay-set-r7-52b0d2b42358": {
      "attempts": 2,
      "compactions": {
        "end_total": 2,
        "start_total": 3
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
      "median_turns": 35.0,
      "median_wall_s": 1200.45,
      "tool_calls_by_tool": {
        "bash": 65,
        "edit": 1,
        "read": 16,
        "write": 1
      },
      "tool_calls_total": 83,
      "tool_errors_by_tool": {
        "bash": 8
      },
      "tool_errors_total": 8,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-replay-set-r8-4324817a7216": {
      "attempts": 2,
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
      "median_turns": 34.0,
      "median_wall_s": 1200.4,
      "tool_calls_by_tool": {
        "bash": 63,
        "read": 7
      },
      "tool_calls_total": 70,
      "tool_errors_by_tool": {
        "bash": 9
      },
      "tool_errors_total": 9,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-replay-set-r9-870367a83103": {
      "attempts": 2,
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
        "stop": 1,
        "toolUse": 1
      },
      "median_turns": 18.5,
      "median_wall_s": 669.05,
      "tool_calls_by_tool": {
        "bash": 29,
        "read": 14
      },
      "tool_calls_total": 43,
      "tool_errors_by_tool": {
        "bash": 2
      },
      "tool_errors_total": 2,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-spec-replay-r1-7be283086913": {
      "attempts": 2,
      "compactions": {
        "end_total": 2,
        "start_total": 3
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
      "kind_match_rate_all_attempts": 0.0,
      "kind_match_rate_valid_requests": null,
      "kind_matches": 0,
      "kind_matches_among_valid_requests": 0,
      "last_stop_reasons": {
        "length": 1,
        "toolUse": 1
      },
      "median_turns": 18.5,
      "median_wall_s": 1200.3,
      "tool_calls_by_tool": {
        "bash": 22,
        "read": 27,
        "write": 1
      },
      "tool_calls_total": 50,
      "tool_errors_by_tool": {
        "bash": 4,
        "read": 1,
        "write": 1
      },
      "tool_errors_total": 6,
      "valid_request_rate": 0.0,
      "valid_requests": 0
    },
    "m1-ngram-spec-replay-r10-dc0c818a5351": {
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
      "median_turns": 26.5,
      "median_wall_s": 555.6,
      "tool_calls_by_tool": {
        "bash": 46,
        "edit": 2,
        "read": 20,
        "submit_request": 2,
        "write": 1
      },
      "tool_calls_total": 71,
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
      "median_wall_s": 367.75,
      "tool_calls_by_tool": {
        "bash": 33,
        "edit": 6,
        "read": 10,
        "submit_request": 2
      },
      "tool_calls_total": 51,
      "tool_errors_by_tool": {
        "bash": 1,
        "edit": 2
      },
      "tool_errors_total": 3,
      "valid_request_rate": 1.0,
      "valid_requests": 2
    },
    "m1-ngram-spec-replay-r2-aa8e7eef2474": {
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
      "median_turns": 20.0,
      "median_wall_s": 771.9000000000001,
      "tool_calls_by_tool": {
        "bash": 19,
        "edit": 7,
        "read": 16,
        "submit_request": 2,
        "write": 1
      },
      "tool_calls_total": 45,
      "tool_errors_by_tool": {
        "bash": 1,
        "edit": 3
      },
      "tool_errors_total": 4,
      "valid_request_rate": 1.0,
      "valid_requests": 2
    },
    "m1-ngram-spec-replay-r3-b72fe4dade49": {
      "attempts": 2,
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
      "median_turns": 31.5,
      "median_wall_s": 1043.5,
      "tool_calls_by_tool": {
        "bash": 38,
        "edit": 4,
        "read": 20,
        "submit_request": 2,
        "write": 1
      },
      "tool_calls_total": 65,
      "tool_errors_by_tool": {
        "bash": 4
      },
      "tool_errors_total": 4,
      "valid_request_rate": 1.0,
      "valid_requests": 2
    },
    "m1-ngram-spec-replay-r4-1147202353a6": {
      "attempts": 2,
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
      "kind_match_rate_all_attempts": 0.5,
      "kind_match_rate_valid_requests": 1.0,
      "kind_matches": 1,
      "kind_matches_among_valid_requests": 1,
      "last_stop_reasons": {
        "toolUse": 2
      },
      "median_turns": 32.5,
      "median_wall_s": 1155.25,
      "tool_calls_by_tool": {
        "bash": 60,
        "edit": 3,
        "read": 5,
        "submit_request": 1,
        "write": 2
      },
      "tool_calls_total": 71,
      "tool_errors_by_tool": {
        "bash": 11,
        "edit": 1
      },
      "tool_errors_total": 12,
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
      "median_turns": 6.0,
      "median_wall_s": 179.5,
      "tool_calls_by_tool": {
        "bash": 9,
        "read": 6,
        "submit_request": 2
      },
      "tool_calls_total": 17,
      "tool_errors_by_tool": {},
      "tool_errors_total": 0,
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
      "median_turns": 10.0,
      "median_wall_s": 197.6,
      "tool_calls_by_tool": {
        "bash": 11,
        "read": 12,
        "submit_request": 2
      },
      "tool_calls_total": 25,
      "tool_errors_by_tool": {},
      "tool_errors_total": 0,
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
      "median_turns": 11.0,
      "median_wall_s": 228.89999999999998,
      "tool_calls_by_tool": {
        "bash": 19,
        "edit": 2,
        "read": 6,
        "submit_request": 2
      },
      "tool_calls_total": 29,
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
      "median_turns": 11.5,
      "median_wall_s": 397.6,
      "tool_calls_by_tool": {
        "bash": 26,
        "edit": 1,
        "read": 2,
        "submit_request": 2
      },
      "tool_calls_total": 31,
      "tool_errors_by_tool": {
        "bash": 2
      },
      "tool_errors_total": 2,
      "valid_request_rate": 1.0,
      "valid_requests": 2
    },
    "m1-ngram-write-up-r2-cebbd5fef63b": {
      "attempts": 2,
      "compactions": {
        "end_total": 3,
        "start_total": 3
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
      "median_turns": 24.0,
      "median_wall_s": 1200.5,
      "tool_calls_by_tool": {
        "bash": 26,
        "edit": 4,
        "read": 33
      },
      "tool_calls_total": 63,
      "tool_errors_by_tool": {
        "bash": 4,
        "edit": 2
      },
      "tool_errors_total": 6,
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
          "timeout": 0
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
      "median_turns": 13.0,
      "median_wall_s": 524.4,
      "tool_calls_by_tool": {
        "bash": 12,
        "read": 23,
        "submit_request": 2
      },
      "tool_calls_total": 37,
      "tool_errors_by_tool": {
        "bash": 3
      },
      "tool_errors_total": 3,
      "valid_request_rate": 1.0,
      "valid_requests": 2
    }
  },
  "pooled": {
    "attempts": 44,
    "compactions": {
      "end_total": 29,
      "start_total": 32
    },
    "failure_flags": {
      "counts": {
        "context_overflow": 3,
        "output_limit": 2,
        "pi_exit_nonzero": 0,
        "rate_limit": 0,
        "timeout": 17
      },
      "denominator": "all attempts; flags may overlap"
    },
    "kind_match_rate_all_attempts": 0.4772727272727273,
    "kind_match_rate_valid_requests": 0.84,
    "kind_matches": 21,
    "kind_matches_among_valid_requests": 21,
    "last_stop_reasons": {
      "error": 1,
      "length": 2,
      "stop": 1,
      "toolUse": 40
    },
    "median_turns": 16.5,
    "median_wall_s": 903.5,
    "tool_calls_by_tool": {
      "bash": 712,
      "edit": 59,
      "read": 309,
      "submit_request": 30,
      "write": 11
    },
    "tool_calls_total": 1121,
    "tool_errors_by_tool": {
      "bash": 74,
      "edit": 18,
      "read": 1,
      "submit_request": 4,
      "write": 2
    },
    "tool_errors_total": 99,
    "valid_request_rate": 0.5681818181818182,
    "valid_requests": 25
  }
}
```
