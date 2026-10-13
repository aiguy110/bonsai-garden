#!/usr/bin/env python3
"""Run a queue of worker-eval arms in one shared time budget (W2).

  python3 bench/worker_eval/run_queue.py --queue FILE --budget-min 145 [--repeat 2] [--only CASE]

FILE is a JSON list of {"arm": NAME, "out": DIR}. The first arm with attempts still missing runs
(resuming from DIR/results.jsonl); when it is complete the next one starts, drawing on what is left
of the budget. run.py's run_all never starts an attempt whose session timeout does not fit, so the
queue stops cleanly at the budget. It prints records done/total per arm.
"""
import argparse
import importlib.util
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("worker_eval_run", HERE / "run.py")
run = importlib.util.module_from_spec(spec)
sys.modules["worker_eval_run"] = run
spec.loader.exec_module(run)


def out_dir(entry):
    p = pathlib.Path(entry["out"])
    return p if p.is_absolute() else run.ROOT / p


def progress(entry, cases, repeats):
    """Attempts recorded for the selected cases and repeats, and how many there should be."""
    done = run.completed(run.load_records(out_dir(entry) / "results.jsonl"))
    want = {run.attempt_key(entry["arm"], c["case_id"], r) for c in cases for r in range(1, repeats + 1)}
    return len(want & set(done)), len(want)


def run_queue(queue, cases, repeats, budget_min, run_arm, clock=time.monotonic, log=print):
    """`run_arm(entry, remaining_min) -> None` runs one arm (resuming). Returns {arm: (done, total)}."""
    t0 = clock()
    status = {}
    for entry in queue:
        done, total = progress(entry, cases, repeats)
        status[entry["arm"]] = (done, total)
        if done < total:
            left = budget_min - (clock() - t0) / 60
            if left <= 0:
                log(f"{entry['arm']}: no budget left")
                break
            run_arm(entry, left)
            status[entry["arm"]] = progress(entry, cases, repeats)
            if status[entry["arm"]][0] < status[entry["arm"]][1]:
                break  # budget used up (or attempts failing): later arms wait
    for entry in queue:
        status.setdefault(entry["arm"], progress(entry, cases, repeats))
    for name, (d, t) in status.items():
        log(f"{name}: records {d}/{t}")
    return status


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--queue", required=True)
    ap.add_argument("--budget-min", type=float, default=145)
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--cases", default=str(HERE / "cases.jsonl"))
    args = ap.parse_args(argv)
    if args.budget_min > 150:
        sys.exit("--budget-min must leave room inside a 150-minute run request")
    queue = json.loads(pathlib.Path(args.queue).read_text())
    cases = run.load_cases(args.cases)
    if args.only:
        missing = set(args.only) - {c["case_id"] for c in cases}
        if missing:
            sys.exit(f"unknown case ids: {sorted(missing)}")
        cases = [c for c in cases if c["case_id"] in args.only]
    for e in queue:
        run.load_arm(e["arm"])  # fail before launching anything

    def run_arm(entry, left):
        argv = [entry["arm"], "--cases", args.cases, "--repeat", str(args.repeat),
                "--out", str(out_dir(entry)), "--budget-min", str(left)]
        for c in args.only:
            argv += ["--only", c]
        print(f"== {entry['arm']} ({left:.1f} min of budget left)", flush=True)
        run.main(argv)

    run_queue(queue, cases, args.repeat, args.budget_min, run_arm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
