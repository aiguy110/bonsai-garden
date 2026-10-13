#!/usr/bin/env python3
"""Summarize M1 self-speculation replay artifacts.

Usage: python3 bench/spec_summarize.py [REPLAY_DIR]

Writes summary.md, summary.json, and the no-deploy decision deploy.json beside
REPLAY_DIR.  It deliberately uses only foreground rows: background loops are a
load generator, rather than independently comparable replay requests.
"""
import hashlib
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

PHASES = ("single-agent", "single-mem", "dual-agent", "dual-mem")


def read_jsonl(path):
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def message_blob(message):
    return ((message.get("reasoning_content") or "") + (message.get("content") or "") +
            json.dumps(message.get("tool_calls") or [], sort_keys=True))


def output_texts(replay, arm):
    """Recover the exact hashed response representation from gitignored output."""
    result = {}
    path = Path(__file__).resolve().parent / ".replay" / "m1" / "outputs" / f"{arm}.jsonl"
    if not path.exists():
        return result
    for row in read_jsonl(path):
        if "message" in row:
            result[(row["phase"], row["id"], row["fg_bg"])] = message_blob(row["message"])
    return result


def vram_mib(path):
    """Read the per-phase first-foreground VRAM samples written by the probe."""
    if not path.exists():
        return {}
    samples = {}
    phase = None
    for line in path.read_text().splitlines():
        match = re.match(r"== (.+) \(after first fg request\)", line)
        if match:
            phase = match.group(1)
            continue
        match = re.match(r"(\d+) MiB,", line)
        if match and phase:
            samples[phase] = int(match.group(1))
    return samples


def first_divergence(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return min(len(a), len(b)) if a != b else None


def metric(rows):
    n = sum(r.get("predicted_n") or 0 for r in rows)
    ms = sum(r.get("predicted_ms") or 0 for r in rows)
    draft = sum(r.get("draft_n") or 0 for r in rows)
    accepted = sum(r.get("draft_n_accepted") or 0 for r in rows)
    valid = [r for r in rows if r.get("tool_call_json_valid") is not None]
    rates = [r.get("predicted_per_second") for r in rows if r.get("predicted_per_second") is not None]
    return {"n": len(rows), "tokens": n, "decode_tok_s": 1000 * n / ms if ms else None,
            "median_request_tok_s": statistics.median(rates) if rates else None,
            "draft_acceptance": accepted / draft if draft else None,
            "draft_n": draft, "draft_n_accepted": accepted,
            "draft_tokens_per_generated_token": draft / n if n else None,
            "tool_call_json_valid_rate": sum(bool(r["tool_call_json_valid"]) for r in valid) / len(valid) if valid else None}


def pinned_mmproj_path():
    """The --mmproj path pinned by the live bonsai entry, or None if unknown."""
    y = Path(__file__).resolve().parent.parent / "serving" / "llama-swap.bonsai-2-27b.yaml"
    if not y.exists():
        return None
    for line in y.read_text().splitlines():
        m = re.match(r"\s*--mmproj\s+(\S+)", line)
        if m:
            return m.group(1)
    return None


def mmproj_loaded_rows(replay, arm):
    """Per-phase server logs must record the pinned projector loading.

    Checks the actual server output (`load_model: loaded multimodal model,
    <pinned path>`), not notes or the absence of the word 'refused'.
    Returns (ok, rows) with rows = [{phase, load_lines, refused}] and ok True
    only if every one of the four A-prod server logs has a matching load line.
    """
    pinned = pinned_mmproj_path()
    rows, ok = [], True
    cand = replay / arm
    for phase in PHASES:
        log = cand / f"server_{phase}.log"
        text = log.read_text() if log.exists() else ""
        need = pinned if pinned is not None else "mmproj"
        lines = [ln for ln in text.splitlines()
                 if "loaded multimodal model" in ln and need in ln]
        rows.append({"phase": phase, "load_lines": len(lines), "refused": "refused" in text})
        ok = ok and bool(lines)
    return ok, rows


def fnum(x, digits=1):
    return "—" if x is None else f"{x:.{digits}f}"


def fpct(x):
    return "—" if x is None else f"{100*x:.1f}%"


def main():
    replay = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("bench/results/2026-10-12/m1-ngram/replay")
    outdir = replay.parent
    arms = sorted(p.name for p in replay.iterdir() if p.is_dir() and (p / "requests.jsonl").exists())
    data = {a: [r for r in read_jsonl(replay / a / "requests.jsonl")
                if r.get("fg_bg") == "fg" and not r.get("error")] for a in arms}
    texts = {a: output_texts(replay, a) for a in arms}
    metrics, vrams = {}, {}
    for arm in arms:
        vrams[arm] = vram_mib(replay / arm / "vram.txt")
        for phase in PHASES:
            role = phase.split("-", 1)[1]
            metrics[(arm, phase, role)] = metric([r for r in data[arm] if r["phase"] == phase and r["role"] == role])

    # Same sampling/phase/role off arm is the performance and VRAM control.
    for (arm, phase, role), m in metrics.items():
        sampling = arm.rsplit("-", 1)[1]
        off = f"off-{sampling}"
        ref = metrics.get((off, phase, role))
        m["speedup_vs_off"] = m["decode_tok_s"] / ref["decode_tok_s"] if ref and ref["decode_tok_s"] else None
        m["vram_mib"] = vrams[arm].get(phase)
        ref_vram = vrams.get(off, {}).get(phase)
        m["vram_vs_off_mib"] = m["vram_mib"] - ref_vram if m["vram_mib"] is not None and ref_vram is not None else None

    identity = []
    for arm in arms:
        if not arm.endswith("-greedy"):
            continue
        for phase in PHASES:
            mine = {r["id"]: r for r in data[arm] if r["phase"] == phase}
            off = {r["id"]: r for r in data["off-greedy"] if r["phase"] == phase}
            compared, same, mismatches = 0, 0, []
            for ident, r in mine.items():
                if ident not in off:
                    continue
                compared += 1
                if r.get("out_sha256") == off[ident].get("out_sha256"):
                    same += 1
                else:
                    mismatches.append({"id": ident, "first_divergence_char": first_divergence(
                        texts[arm].get((phase, ident, "fg"), ""),
                        texts["off-greedy"].get((phase, ident, "fg"), ""))})
            identity.append({"arm": arm, "phase": phase, "compared": compared, "identical": same,
                             "identical_rate": same / compared if compared else None, "mismatches": mismatches})

    # Batch-numerics control: off dual foreground output versus off single output.
    control = []
    for role in ("agent", "mem"):
        single = {r["id"]: r for r in data["off-greedy"] if r["phase"] == "single-" + role}
        dual = {r["id"]: r for r in data["off-greedy"] if r["phase"] == "dual-" + role}
        same, mismatches = 0, []
        for ident, row in dual.items():
            if row.get("out_sha256") == single.get(ident, {}).get("out_sha256"):
                same += 1
            else:
                mismatches.append({"id": ident, "first_divergence_char": first_divergence(
                    texts["off-greedy"].get(("dual-" + role, ident, "fg"), ""),
                    texts["off-greedy"].get(("single-" + role, ident, "fg"), ""))})
        control.append({"role": role, "compared": len(dual), "identical": same,
                        "identical_rate": same / len(dual) if dual else None, "mismatches": mismatches})

    # The only complete production speculative candidate is A-prod.
    candidate = "A-prod"
    ca = metrics[(candidate, "dual-agent", "agent")]
    cm = metrics[(candidate, "dual-mem", "mem")]
    cs_a = metrics[(candidate, "single-agent", "agent")]
    cs_m = metrics[(candidate, "single-mem", "mem")]
    candidate_id = [x for x in identity if x["arm"] == "A-greedy" and x["phase"].startswith("dual-")]
    control_rate = sum(x["identical"] for x in control) / sum(x["compared"] for x in control)
    identity_rate = sum(x["identical"] for x in candidate_id) / sum(x["compared"] for x in candidate_id)
    mmproj_ok, mmproj_rows = mmproj_loaded_rows(replay, candidate)
    mmproj_loaded_count = sum(r["load_lines"] for r in mmproj_rows)
    rules = [
        {"rule": 1, "criterion": "pinned --mmproj projector actually loaded: all four A-prod server logs record `load_model: loaded multimodal model, ...mmproj...` for the live entry's pinned path", "pass": mmproj_ok, "value": f"pinned mmproj load line in {mmproj_loaded_count}/{len(mmproj_rows)} A-prod server logs"},
        {"rule": 2, "criterion": "dual-agent decode tok/s >= 1.10x off at the same sampling and phase", "pass": ca["speedup_vs_off"] >= 1.10, "value": f"dual-agent {fnum(ca['decode_tok_s'])} tok/s, {fnum(ca['speedup_vs_off'], 3)}x off"},
        {"rule": 3, "criterion": "dual-mem, single-agent and single-mem each >= 0.97x off", "pass": all(x["speedup_vs_off"] >= .97 for x in (cm, cs_a, cs_m)), "value": "dual-mem/single-agent/single-mem " + "/".join(fnum(x["speedup_vs_off"], 3) + "x" for x in (cm, cs_a, cs_m))},
        {"rule": 4, "criterion": "VRAM in every phase <= off + 64 MiB", "pass": all(x["vram_vs_off_mib"] <= 64 for x in (ca, cm, cs_a, cs_m)), "value": f"max delta {max(x['vram_vs_off_mib'] for x in (ca, cm, cs_a, cs_m)):+.0f} MiB"},
        {"rule": 5, "criterion": "tool_call_json_valid rate >= off's rate in every phase", "pass": all(x["tool_call_json_valid_rate"] >= metrics[("off-prod", ph, ro)]["tool_call_json_valid_rate"] for x, ph, ro in ((ca,"dual-agent","agent"),(cm,"dual-mem","mem"),(cs_a,"single-agent","agent"),(cs_m,"single-mem","mem"))), "value": "candidate/off valid rates (dual-agent, dual-mem, single-agent, single-mem): " + "/".join(f"{fpct(x['tool_call_json_valid_rate'])}/{fpct(metrics[('off-prod', ph, ro)]['tool_call_json_valid_rate'])}" for x, ph, ro in ((ca,"dual-agent","agent"),(cm,"dual-mem","mem"),(cs_a,"single-agent","agent"),(cs_m,"single-mem","mem")))},
        {"rule": 6, "criterion": "A-greedy dual-phase identical-output rate >= off dual-vs-single control rate - 10 percentage points", "pass": identity_rate >= control_rate - .10, "value": f"A dual {fpct(identity_rate)}; off dual-vs-single control {fpct(control_rate)}"},
    ]
    result = {"replay_dir": str(replay), "foreground_only": True, "metrics": [dict(arm=a, phase=p, role=r, **m) for (a,p,r),m in metrics.items()], "identity": identity, "off_dual_vs_single_control": control, "decision_candidate": candidate, "rules": rules}
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = ["# M1 n-gram self-speculation summary", "", "Foreground replay requests only. Decode rate is `sum(predicted_n) / sum(predicted_ms) * 1000`; background traffic is load, not a measured row.", "", "## Foreground performance", "", "| config | sampling | phase | role | n | decode tok/s | median req tok/s | acceptance | draft/gen | speedup vs off | tool JSON valid | VRAM vs off |", "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for (arm, phase, role), m in metrics.items():
        config, sampling = arm.rsplit("-", 1)
        lines.append(f"| {config} | {sampling} | {phase} | {role} | {m['n']} | {fnum(m['decode_tok_s'])} | {fnum(m['median_request_tok_s'])} | {fpct(m['draft_acceptance'])} | {fnum(m['draft_tokens_per_generated_token'],3)} | {fnum(m['speedup_vs_off'],3)}x | {fpct(m['tool_call_json_valid_rate'])} | {fnum(m['vram_vs_off_mib']):s} MiB |")
    lines += ["", "## Greedy output identity", "", "Compared against off at the same phase and request id. First divergence is a character index in the hashed response representation (reasoning + content + canonical tool calls).", "", "| config | phase | identical/compared | rate | first-divergence indices for mismatches |", "|---|---|---:|---:|---|"]
    for x in identity:
        ds = ", ".join(f"{m['id']}:{m['first_divergence_char']}" for m in x["mismatches"])
        lines.append(f"| {x['arm'].rsplit('-',1)[0]} | {x['phase']} | {x['identical']}/{x['compared']} | {fpct(x['identical_rate'])} | {ds or '—'} |")
    lines += ["", "Off dual-vs-single batch-numerics control:", "", "| role | identical/compared | rate | first-divergence indices for mismatches |", "|---|---:|---:|---|"]
    for x in control:
        ds = ", ".join(f"{m['id']}:{m['first_divergence_char']}" for m in x["mismatches"])
        lines.append(f"| {x['role']} | {x['identical']}/{x['compared']} | {fpct(x['identical_rate'])} | {ds or '—'} |")
    lines += ["", "## Deployment decision", "", "Candidate: `A-prod` (`--spec-type ngram-mod`). Deploy only if every rule passes.", "", "| rule | criterion | result | value |", "|---:|---|---|---|"]
    lines += [f"| {x['rule']} | {x['criterion']} | {'PASS' if x['pass'] else 'FAIL'} | {x['value']} |" for x in rules]
    failed = [f"rule {x['rule']}: {x['value']}" for x in rules if not x["pass"]]
    lines += ["", "**Decision: do not deploy.** " + "; ".join(failed) + "."]
    (outdir / "summary.md").write_text("\n".join(lines) + "\n")
    (outdir / "deploy.json").write_text(json.dumps({"deployed": False, "why": failed}, indent=2) + "\n")

if __name__ == "__main__":
    main()
