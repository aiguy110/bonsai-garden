# W1 advisor-graded sample

Small judged sample only: 10 deterministically valid replay attempts selected by the rule in `sample_manifest.json`; it is not a new deterministic performance rate. No `infra` attempts were valid, so that stratum is empty.

Advisor model (first grading): `openai-codex/gpt-5.6-sol`. Approval: 7/10 (70.0%); revise: 3; reject: 0.

Separately, the complete deterministic 44-attempt baseline had valid requests 25/44 (56.8%) and kind matches 21/44 (47.7%); these are not advisor grades.

The verbatim first normal finished-item review is `advisor_first_response.txt`; its normal finished-item transcription-verification resubmission is `advisor_verification_response.txt`. Finalization requires their per-attempt verdicts and rationales to agree exactly. Their journal trace is recorded per grade in `advisor_grades.jsonl`.
