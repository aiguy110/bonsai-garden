#!/bin/bash
# Build the corpus, then verify it against the same archive state.
set -e
python3 bench/worker_eval/build_cases.py
python3 bench/worker_eval/build_cases.py --check
