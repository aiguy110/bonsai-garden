#!/usr/bin/env python3
"""Speed of the live bonsai-2-27b entry under the GPU power/clock cap, and whether the
host survives the load that reset it (2026-10-12: four hard resets, each within a
second of a large Bonsai request starting).

Run under a turnstile lease; it talks to llama-swap on :11435 directly, like
`autopilot/infra.py baseline`:
    ~/Projects/local-llm-bench/turnstile_run.py -- python3 bench/power_cap_probe.py OUT_DIR

Measures decode (one slot, then both) with infra.py's prompts, and prefill of a
~24k-token prompt on one slot, then on both at once. Samples GPU power and SM clock
every 100 ms throughout.
"""
import concurrent.futures
import json
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "autopilot"))
import infra  # noqa: E402

out = pathlib.Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
smi = subprocess.Popen(["nvidia-smi", "--query-gpu=timestamp,power.draw,clocks.sm,temperature.gpu",
                        "--format=csv,noheader,nounits", "-lms", "100"],
                       stdout=open(out / "gpu-samples.csv", "w"))


def prefill(i, salt):
    # Distinct text per slot and run, so no prompt cache is reused.
    text = " ".join(f"item {salt}-{i}-{k}: the quick brown fox jumps over the lazy dog." for k in range(1700))
    r = infra.chat(infra.SWAP, infra.ENTRY, text + "\nReply with OK.", 4, id_slot=i, cache_prompt=False)
    return {"prompt_n": r["timings"]["prompt_n"], "prompt_tok_s": round(r["timings"]["prompt_per_second"], 1)}


res = {"decode": [], "prefill_single": [], "prefill_dual": []}
try:
    for run in range(3):
        res["decode"].append(infra.direct_health())
        res["prefill_single"].append(prefill(0, f"s{run}-{time.time_ns()}"))
        with concurrent.futures.ThreadPoolExecutor(2) as ex:
            salt = f"d{run}-{time.time_ns()}"
            res["prefill_dual"].append([f.result() for f in [ex.submit(prefill, i, salt) for i in range(2)]])
finally:
    smi.terminate()
    smi.wait()

rows = [l.split(", ") for l in (out / "gpu-samples.csv").read_text().splitlines() if l.count(",") == 3]
res["gpu"] = {"samples": len(rows), "max_power_w": max(float(r[1]) for r in rows),
              "max_sm_mhz": max(int(r[2]) for r in rows), "max_temp_c": max(int(r[3]) for r in rows)}
(out / "result.json").write_text(json.dumps(res, indent=2) + "\n")
print(json.dumps(res, indent=2))
