#!/bin/bash
# Smoke test for run.py: one case, then the same invocation again, which must skip it.
# Results stay under bench/results/; the worktree is otherwise unchanged.
set -u
OUT=bench/results/2026-10-12/worker_eval/smoke
CASE=$(head -n 1 bench/worker_eval/cases.jsonl | python3 -c 'import json,sys; print(json.loads(sys.stdin.readline())["case_id"])')
evals/.cache/venv-sandbox/bin/python -m pytest -q bench/worker_eval/test_run.py || exit 1
mkdir -p "$OUT"
git status --porcelain | grep -v "^.. $OUT" > "$OUT/status-before.txt"
echo "== first invocation"; python3 bench/worker_eval/run.py bonsai-2026-10-12 --only "$CASE" --repeat 1 --out "$OUT" --budget-min 30
echo "records after first: $(wc -l < "$OUT/results.jsonl")"
echo "== second invocation (must skip)"; python3 bench/worker_eval/run.py bonsai-2026-10-12 --only "$CASE" --repeat 1 --out "$OUT" --budget-min 30
echo "records after second: $(wc -l < "$OUT/results.jsonl")"
ls -R "$OUT" | head -40
python3 - "$OUT" <<'P'
import json, sys, pathlib
rec = [json.loads(l) for l in open(pathlib.Path(sys.argv[1]) / "results.jsonl")]
print(json.dumps(rec[0], indent=1)[:4000])
P
git status --porcelain | grep -v "^.. $OUT" > "$OUT/status-after.txt"
echo "== worktree diff outside results (empty = unchanged)"; diff "$OUT/status-before.txt" "$OUT/status-after.txt" && echo unchanged
echo "== leftover checkouts"; ls -d /tmp/w1-replay-* 2>/dev/null
