#!/usr/bin/env python3
"""Prepare and obtain reproducible advisor grades for valid W1 replay requests."""
import argparse
import hashlib
import io
import json
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT = ROOT / "bench/results/2026-10-13/worker-eval/bonsai-2026-10-12"
KINDS = ("run", "infra", "done")


def sha(data): return hashlib.sha256(data).hexdigest()
def read_jsonl(p): return [json.loads(x) for x in pathlib.Path(p).read_text().splitlines() if x.strip()]
def run_id(r): return f"{r['case_id']}/r{r['repeat']}"
def safe(s): return s.replace("/", "__")
def repo_path(p): return pathlib.Path(p).resolve().relative_to(ROOT).as_posix()


def selected(result_dir):
    rows = [r for r in read_jsonl(result_dir / "results.jsonl") if r.get("valid_request")]
    out = []
    for kind in KINDS:
        bucket = [r for r in rows if r.get("replay_kind") == kind]
        bucket.sort(key=lambda r: (sha(run_id(r).encode()), run_id(r)))
        out.extend(bucket[:5])
    return out


def item_context(prompt):
    stops = ("## Standing facts", "## Journal")
    cut = min([prompt.find(x) for x in stops if prompt.find(x) >= 0] or [len(prompt)])
    return prompt[:cut].strip()


def safe_rel_path(token):
    """Accept only a normal repository-relative path (never a traversal)."""
    p = pathlib.PurePosixPath(token)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise ValueError(f"unsafe repository path: {token!r}")
    return p


def safe_requested_path(token):
    """Accept only a normal repo-relative requested script under bench/ or evals/."""
    p = safe_rel_path(token)
    if p.parts[0] not in ("bench", "evals"):
        raise ValueError(f"unsafe requested script path: {token!r}")
    return p


def changed_paths(diff):
    paths = set()
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            paths.add(safe_rel_path(line[6:]))
    return sorted(paths, key=str)


def copy_file(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {"path": repo_path(dst), "sha256": sha(dst.read_bytes())}


def prepare(result_dir):
    result_dir = result_dir.resolve()
    out = result_dir / "advisor_grading"
    packets = out / "packets"
    # A regenerated sample must not retain evidence from a prior packet format.
    shutil.rmtree(packets, ignore_errors=True)
    packets.mkdir(parents=True)
    cases = {c["case_id"]: c for c in read_jsonl(HERE / "cases.jsonl")}
    rows = selected(result_dir)
    review_template = (ROOT / "autopilot/prompts/review.md").read_text()
    manifest = {
        "selection_version": 2,
        "review_template": "autopilot/prompts/review.md",
        "review_template_sha256": sha(review_template.encode()),
        "rule": "Filter valid_request=true; stratify by replay_kind in [run, infra, done]; sort each stratum by SHA-256(case_id + '/r' + repeat), then run_id; retain first five from each nonempty stratum. Exclude continue and stuck because the real orchestrator does not send them to advisor review.",
        "source_results": repo_path(result_dir / "results.jsonl"),
        "source_results_sha256": sha((result_dir / "results.jsonl").read_bytes()),
        "sample_size": len(rows), "strata": {k: 0 for k in KINDS}, "attempts": []}
    for r in rows:
        rid = run_id(r)
        case = cases[r["case_id"]]
        ad = ROOT / r["attempt_dir"]
        request = r["request"]
        packet_dir = packets / safe(rid)
        evidence = packet_dir / "preserved"
        evidence.mkdir(parents=True)
        copied = []
        for name in ("request.json", "final.txt", "workspace.diff", "record.json", "manifest.json", "events.jsonl"):
            src = ad / name
            if src.exists(): copied.append(copy_file(src, evidence / name))
        diff = (ad / "workspace.diff").read_text() if (ad / "workspace.diff").exists() else "(no workspace diff preserved)\n"
        # Reconstruct exact replay state. Patch failure is fatal: partial evidence is invalid.
        with tempfile.TemporaryDirectory(prefix="w1-grade-") as td:
            tree = pathlib.Path(td)
            archive = subprocess.run(["git", "archive", case["start_commit"]], cwd=ROOT,
                                     stdout=subprocess.PIPE, check=True).stdout
            with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
                tf.extractall(tree, filter="data")
            if diff != "(no workspace diff preserved)\n":
                patch = tree / "replay.patch"
                patch.write_text(diff)
                subprocess.run(["patch", "-p1", "-i", str(patch)], cwd=tree, check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            # Preserve all non-deleted files represented by the diff, so done claims
            # can be judged against replay state rather than today's checkout.
            replay_files = []
            for rel in changed_paths(diff):
                src = tree / rel
                if src.is_file():
                    replay_files.append(copy_file(src, evidence / "replay_state" / rel))
            command = request.get("command", "") if isinstance(request, dict) else ""
            requested = []
            if command:
                argv = shlex.split(command)
                if len(argv) >= 2 and argv[0] in ("python3", "bash"):
                    rel = safe_requested_path(argv[1])
                    src = tree / rel
                    if not src.is_file():
                        raise ValueError(f"requested script absent from replay state: {rel}")
                    requested.append(copy_file(src, evidence / "requested" / rel))
        instruction = {"run": "The worker wants to run this on the host (outside its sandbox). Read the script(s). Approve only if it is safe (no destructive commands, writes only under the repo or /tmp, private llama-server on port 8089 if it starts one, never touches the live services on :8080/:11435), and it plausibly measures what the item needs. Otherwise say exactly what to fix.",
          "infra": "The worker wants to apply this entry to the live server it runs on. The orchestrator will health-check and auto-rollback, but approve only if the measurements in the repo justify it and the change is limited to what they support.",
          "done": "The worker says this item is done. Check its acceptance criteria against the files in the repo (read them). Approve only if met and the numbers are real (traceable to results files)."}[r["replay_kind"]]
        packet = f"# W1 replay advisor grading packet\n\n- Run ID: `{rid}`\n- Request kind: `{r['replay_kind']}`\n- Deterministically valid: true\n- Replay artifact: `{r['attempt_dir']}`\n- Case start commit: `{case['start_commit']}`\n- Preserved evidence: `{repo_path(evidence)}`\n\n## Original milestone/item context (journal and original advisor verdict excluded)\n\n{item_context(case['prompt'])}\n\n## Bonsai request\n\n```json\n{json.dumps(request, indent=2, sort_keys=True)}\n```\n\n## Kind-specific review instruction\n\n{instruction}\n\n## Autopilot review gate template\n\n```text\n{review_template}\n```\n\n## Replay-worktree diff\n\n```diff\n{diff}\n```\n\n## Preserved evidence\n\nThe preserved directory contains raw replay artifacts plus `replay_state/` (every non-deleted file changed by the replay diff after applying it to the start commit) and `requested/` (the exact host script named by a run request). File hashes are recorded in `sample_manifest.json`.\n"
        pp = packets / (safe(rid) + ".md")
        pp.write_text(packet)
        manifest["strata"][r["replay_kind"]] += 1
        manifest["attempts"].append({"run_id": rid, "case_id": r["case_id"], "repeat": r["repeat"],
            "kind": r["replay_kind"], "ordering_sha256": sha(rid.encode()), "packet": repo_path(pp),
            "packet_sha256": sha(packet.encode()), "artifact": r["attempt_dir"],
            "preserved_files": copied, "replay_state_files": replay_files, "requested_files": requested})
    (out / "sample_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(out / "sample_manifest.json")


def cloud_prompt(result_dir, verify=False):
    base = result_dir / "advisor_grading"
    manifest = json.loads((base / "sample_manifest.json").read_text())
    listing = "\n".join(f"- {a['run_id']} ({a['kind']}): `{a['packet']}`" for a in manifest["attempts"])
    if verify:
        prior = (base / "advisor_first_response.txt").read_text()
        return f"""This is transcription verification of the prior independent batch grading below. Read the packets and prior response. Return ONLY a fenced JSON object with a `grades` array, one object per run_id, containing exactly run_id, kind, verdict (approve/revise/reject), and rationale. Preserve prior verdicts and rationales verbatim except to correct a demonstrable transcription error.\n\nPRIOR RESPONSE (verbatim):\n{prior}\n\nPACKETS (read these repo-relative files with your tools):\n{listing}"""
    return f"""Independently grade every named replayed local-worker request. Read each packet and its preserved evidence with your tools. Do not use the original cloud worker verdict (it is intentionally absent), and do not infer quality from deterministic validity. Return a single fenced JSON object: {{\"grades\":[{{\"run_id\":...,\"kind\":...,\"verdict\":\"approve|revise|reject\",\"rationale\":...}}]}}. Include every run exactly once.\n\nPACKETS (read these repo-relative files with your tools):\n{listing}"""


def call(result_dir, verify=False):
    """Invoke autopilot.review(), preserving its normal review.md/journal gate verbatim."""
    sys.path.insert(0, str(ROOT / "autopilot"))
    import autopilot
    autopilot.WT = ROOT
    m = autopilot.Milestone("W1-worker-eval")
    item = next(x for x in m.plan() if x["id"] == "advisor-grades")
    captured = {}
    original = autopilot.call_cloud
    def wrapped(*args, **kwargs):
        final, events = original(*args, **kwargs)
        captured["final"], captured["events"] = final, events
        return final, events
    autopilot.call_cloud = wrapped
    kind = "finished item"
    subject = cloud_prompt(result_dir, verify)
    verdict = autopilot.review(m, item, kind, subject, autopilot.REVIEW_DONE, m.status())
    base = result_dir / "advisor_grading"
    suffix = "verification" if verify else "first"
    target = base / f"advisor_{suffix}_response.txt"
    target.write_text(captured["final"])
    (base / f"advisor_{suffix}_events.json").write_text(json.dumps(captured["events"], indent=2, default=str) + "\n")
    model = autopilot.CFG["roles"]["advisor"]["model"]
    call_meta = {"advisor_model": model, "review_kind": kind, "review_verdict": verdict,
                 "journal": str(m.dir / "journal.md"), "response_sha256": sha(captured["final"].encode())}
    (base / f"advisor_{suffix}_call.json").write_text(json.dumps(call_meta, indent=2) + "\n")
    # The normal gate wrote its parsed decision; retain the exact reply in the same
    # advisor journal as a traceable companion entry.
    m.journal(f"advisor ({kind} grading response)", captured["final"])
    print(target)


def parse_response(text):
    blocks = re.findall(r"```json\s*(.*?)```", text, re.S)
    if not blocks: raise ValueError("advisor response has no fenced JSON")
    return json.loads(blocks[-1])


def finalize(result_dir):
    base = result_dir / "advisor_grading"
    text = (base / "advisor_verification_response.txt").read_text()
    data = parse_response(text)
    manifest = json.loads((base / "sample_manifest.json").read_text())
    expected = {a["run_id"]: a for a in manifest["attempts"]}
    grades = data.get("grades", [])
    if {g.get("run_id") for g in grades} != set(expected) or len(grades) != len(expected):
        raise ValueError("verification response does not give exactly one grade per sampled run")
    first_meta = json.loads((base / "advisor_first_call.json").read_text())
    records = []
    for g in grades:
        a = expected[g["run_id"]]
        if g.get("kind") != a["kind"] or g.get("verdict") not in ("approve", "revise", "reject") or not g.get("rationale"):
            raise ValueError("malformed grade for " + g["run_id"])
        records.append({"advisor_model": first_meta["advisor_model"], "run_id": g["run_id"], "request_kind": g["kind"], "verdict": g["verdict"], "rationale": g["rationale"], "packet": a["packet"], "first_response_sha256": sha((base / "advisor_first_response.txt").read_bytes()), "verification_response_sha256": sha(text.encode()), "advisor_journal": first_meta["journal"]})
    (base / "advisor_grades.jsonl").write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in records))
    counts = {x: sum(g["verdict"] == x for g in records) for x in ("approve", "revise", "reject")}
    (base / "advisor_summary.md").write_text(f"# W1 advisor-graded sample\n\nSmall judged sample only: {len(records)} deterministically valid replay attempts selected by the rule in `sample_manifest.json`; it is separate from deterministic valid-request and kind-match rates. No `infra` attempts were valid, so that stratum is empty.\n\nAdvisor model: `{first_meta['advisor_model']}`. Approval: {counts['approve']}/{len(records)} ({counts['approve']/len(records):.1%}); revise: {counts['revise']}; reject: {counts['reject']}.\n\nThe verbatim first normal finished-item review is `advisor_first_response.txt`; its normal finished-item transcription-verification resubmission is `advisor_verification_response.txt`. Their journal trace is recorded per grade in `advisor_grades.jsonl`.\n")
    print(base / "advisor_summary.md")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("prepare", "grade", "verify", "finalize"))
    p.add_argument("--out", type=pathlib.Path, default=DEFAULT)
    a = p.parse_args()
    if a.action == "prepare": prepare(a.out)
    elif a.action == "grade": call(a.out)
    elif a.action == "verify": call(a.out, True)
    else: finalize(a.out)

if __name__ == "__main__": main()
