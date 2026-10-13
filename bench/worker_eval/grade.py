#!/usr/bin/env python3
"""Prepare and obtain reproducible advisor grades for valid W1 replay requests.

The selection is deliberately mechanical: take the SHA-256 ordering within each
request-kind stratum, up to five run and five done attempts (infra is included if
present; this baseline has none).  Cloud review is deliberately two-stage: the
first call returns all grades, and the second verifies their transcription.
"""
import argparse, hashlib, json, pathlib, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT = ROOT / "bench/results/2026-10-13/worker-eval/bonsai-2026-10-12"
KINDS = ("run", "infra", "done")


def sha(data): return hashlib.sha256(data).hexdigest()
def read_jsonl(p): return [json.loads(x) for x in pathlib.Path(p).read_text().splitlines() if x.strip()]
def run_id(r): return f"{r['case_id']}/r{r['repeat']}"
def safe(s): return s.replace("/", "__")

def selected(result_dir):
    rows = [r for r in read_jsonl(result_dir / "results.jsonl") if r.get("valid_request")]
    out = []
    # Fixed quota is documented here and in the manifest.  Empty strata stay empty.
    for kind in KINDS:
        bucket = [r for r in rows if r.get("replay_kind") == kind]
        bucket.sort(key=lambda r: (sha(run_id(r).encode()), run_id(r)))
        out.extend(bucket[:5])
    return out

def item_context(prompt):
    # Preserve the original task context, but exclude the standing-facts/journal
    # sections, which can contain the cloud worker's original advisor verdict.
    stops = ("## Standing facts", "## Journal")
    cut = min([prompt.find(x) for x in stops if prompt.find(x) >= 0] or [len(prompt)])
    return prompt[:cut].strip()

def prepare(result_dir):
    out = result_dir / "advisor_grading"
    packets = out / "packets"
    packets.mkdir(parents=True, exist_ok=True)
    cases = {c["case_id"]: c for c in read_jsonl(HERE / "cases.jsonl")}
    rows = selected(result_dir)
    manifest = {"selection_version": 1,
      "rule": "Filter valid_request=true; stratify by replay_kind in [run, infra, done]; sort each stratum by SHA-256(case_id + '/r' + repeat), then run_id; retain first five from each nonempty stratum. Exclude continue and stuck because the real orchestrator does not send them to advisor review.",
      "source_results": str(result_dir / "results.jsonl"),
      "source_results_sha256": sha((result_dir / "results.jsonl").read_bytes()),
      "sample_size": len(rows), "strata": {k: 0 for k in KINDS}, "attempts": []}
    for r in rows:
        rid = run_id(r); case = cases[r["case_id"]]; ad = ROOT / r["attempt_dir"]
        diff = (ad / "workspace.diff").read_text() if (ad / "workspace.diff").exists() else "(no workspace diff preserved)\n"
        request = r["request"]
        files = packets / safe(rid) / "preserved"
        files.mkdir(parents=True, exist_ok=True)
        # The request artifact, final reply, and exact patch are preserved. Also
        # reconstruct requested source files from the replay start commit plus its
        # patch, rather than copying today's (possibly later) repository version.
        for name in ("request.json", "final.txt", "workspace.diff", "record.json", "manifest.json"):
            src = ad / name
            if src.exists(): shutil.copy2(src, files / name)
        command = request.get("command", "") if isinstance(request, dict) else ""
        paths = sorted(set(__import__("re").findall(r"(?:^|\\s)((?:bench|evals|serving|site)/[^\\s'\"]+)", command)))
        if paths:
            import tempfile
            with tempfile.TemporaryDirectory(prefix="w1-grade-") as td:
                td = pathlib.Path(td)
                # git archive gives an exact start-tree without a worktree or index.
                archive = subprocess.run(["git", "archive", case["start_commit"]], cwd=ROOT, stdout=subprocess.PIPE, check=True).stdout
                import tarfile, io
                tarfile.open(fileobj=io.BytesIO(archive)).extractall(td, filter="data")
                if diff != "(no workspace diff preserved)\n":
                    patch = td / "replay.patch"; patch.write_text(diff)
                    subprocess.run(["patch", "-p1", "-i", str(patch)], cwd=td, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                for rel in paths:
                    src = td / rel
                    if src.is_file():
                        dst = files / "requested" / rel; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst)
        instruction = {"run": "The worker wants to run this on the host (outside its sandbox). Read the script(s). Approve only if it is safe (no destructive commands, writes only under the repo or /tmp, private llama-server on port 8089 if it starts one, never touches the live services on :8080/:11435), and it plausibly measures what the item needs. Otherwise say exactly what to fix.",
          "infra": "The worker wants to apply this entry to the live server it runs on. The orchestrator will health-check and auto-rollback, but approve only if the measurements in the repo justify it and the change is limited to what they support.",
          "done": "The worker says this item is done. Check its acceptance criteria against the files in the repo (read them). Approve only if met and the numbers are real (traceable to results files)."}[r["replay_kind"]]
        packet = f"# W1 replay advisor grading packet\n\n- Run ID: `{rid}`\n- Request kind: `{r['replay_kind']}`\n- Deterministically valid: true\n- Replay artifact: `{r['attempt_dir']}`\n- Case start commit: `{case['start_commit']}`\n\n## Original milestone/item context (journal and original advisor verdict excluded)\n\n{item_context(case['prompt'])}\n\n## Bonsai request\n\n```json\n{json.dumps(request, indent=2, sort_keys=True)}\n```\n\n## Kind-specific review instruction\n\n{instruction}\n\n## Replay-worktree diff\n\n```diff\n{diff}\n```\n\n## Preserved evidence\n\n`preserved/` contains copied request.json (where recovered), final.txt, workspace.diff, record.json, and manifest.json.\n"
        pp = packets / (safe(rid) + ".md"); pp.write_text(packet)
        manifest["strata"][r["replay_kind"]] += 1
        manifest["attempts"].append({"run_id": rid, "case_id": r["case_id"], "repeat": r["repeat"], "kind": r["replay_kind"], "ordering_sha256": sha(rid.encode()), "packet": str(pp.relative_to(result_dir)), "packet_sha256": sha(packet.encode()), "artifact": r["attempt_dir"]})
    (out / "sample_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(out / "sample_manifest.json")

def cloud_prompt(result_dir, verify=False):
    base = result_dir / "advisor_grading"; manifest = json.loads((base / "sample_manifest.json").read_text())
    listing = "\n".join(f"- {a['run_id']} ({a['kind']}): `{a['packet']}`" for a in manifest["attempts"])
    if verify:
        prior = (base / "advisor_first_response.txt").read_text()
        return f"""You are the research advisor for bonsai-garden. This is a transcription verification of your prior independent grading response below. Read the named packets and prior response. Return ONLY a fenced JSON object with a `grades` array, one object per run_id, containing exactly run_id, kind, verdict (approve/revise/reject), and rationale. Preserve the prior verdicts and rationales verbatim except to correct a demonstrable transcription error.\n\nPRIOR RESPONSE (verbatim):\n{prior}\n\nPACKETS (read these files with your tools):\n{listing}"""
    return f"""You are the research advisor for bonsai-garden, reviewing replayed local-worker requests. This is a batch finished-item review using autopilot/prompts/review.md and the normal finished-item gate. Apply that gate independently to every named packet: read each packet and its preserved evidence with your tools. Do not use the original cloud worker verdict (it is intentionally absent), and do not infer quality from deterministic validity. Return a single fenced JSON object: {{\"grades\":[{{\"run_id\":...,\"kind\":...,\"verdict\":\"approve|revise|reject\",\"rationale\":...}}]}}. Include every run exactly once.\n\nFinished-item gate: Check acceptance criteria against the supplied files; approve only if met and claimed numbers are real and traceable to results files.\n\nPACKETS (read these files with your tools):\n{listing}"""

def call(result_dir, verify=False):
    sys.path.insert(0, str(ROOT / "autopilot")); import autopilot
    final, events = autopilot.call_cloud("advisor", cloud_prompt(result_dir, verify), "worker-eval-grades-verify" if verify else "worker-eval-grades")
    base = result_dir / "advisor_grading"; target = base / ("advisor_verification_response.txt" if verify else "advisor_first_response.txt")
    target.write_text(final)
    (base / ("advisor_verification_events.json" if verify else "advisor_first_events.json")).write_text(json.dumps(events, indent=2, default=str) + "\n")
    print(target)

def finalize(result_dir):
    import re
    base = result_dir / "advisor_grading"; text = (base / "advisor_verification_response.txt").read_text()
    blocks = re.findall(r"```json\\s*(.*?)```", text, re.S)
    data = json.loads(blocks[-1])
    manifest = json.loads((base / "sample_manifest.json").read_text())
    expected = {a["run_id"]: a for a in manifest["attempts"]}
    grades = data.get("grades", [])
    if {g.get("run_id") for g in grades} != set(expected) or len(grades) != len(expected):
        raise ValueError("verification response does not give exactly one grade per sampled run")
    model = json.loads((ROOT / "autopilot/config.json").read_text())["roles"]["advisor"]["model"]
    records = []
    for g in grades:
        a = expected[g["run_id"]]
        if g.get("kind") != a["kind"] or g.get("verdict") not in ("approve", "revise", "reject") or not g.get("rationale"):
            raise ValueError("malformed grade for " + g["run_id"])
        records.append({"advisor_model": model, "run_id": g["run_id"], "request_kind": g["kind"], "verdict": g["verdict"], "rationale": g["rationale"], "packet": a["packet"], "first_response_sha256": sha((base / "advisor_first_response.txt").read_bytes()), "verification_response_sha256": sha(text.encode())})
    (base / "advisor_grades.jsonl").write_text("".join(json.dumps(x, sort_keys=True) + "\\n" for x in records))
    counts = {x: sum(g["verdict"] == x for g in records) for x in ("approve", "revise", "reject")}
    (base / "advisor_summary.md").write_text(f"# W1 advisor-graded sample\\n\\nSmall judged sample only: {len(records)} deterministically valid replay attempts selected by the rule in `sample_manifest.json`; it is separate from deterministic valid-request and kind-match rates. No `infra` attempts were valid, so that stratum is empty.\\n\\nAdvisor model: `{model}`. Approval: {counts['approve']}/{len(records)} ({counts['approve']/len(records):.1%}); revise: {counts['revise']}; reject: {counts['reject']}.\\n\\nThe verbatim first finished-item batch review is `advisor_first_response.txt`; its transcription-verification resubmission is `advisor_verification_response.txt`. Per-attempt grades and response hashes are in `advisor_grades.jsonl`.\\n")
    print(base / "advisor_summary.md")

def main():
 p=argparse.ArgumentParser(); p.add_argument("action", choices=("prepare","grade","verify","finalize")); p.add_argument("--out", type=pathlib.Path, default=DEFAULT); a=p.parse_args()
 if a.action=="prepare": prepare(a.out)
 elif a.action=="grade": call(a.out)
 elif a.action=="verify": call(a.out, True)
 else: finalize(a.out)
if __name__ == "__main__": main()
