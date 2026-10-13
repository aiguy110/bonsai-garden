"""W2 tests: arm files, agent-dir fixture, prompt rewrite, queue rollover, compare.py.

  python3 -m pytest bench/worker_eval/test_w2.py
"""
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


w = _load("worker_eval_run", "run.py")
rq = _load("worker_eval_run_queue", "run_queue.py")
cmp_ = _load("worker_eval_compare", "compare.py")

# fields an arm may change relative to the honest baseline
MECHANISM = {"name", "description", "hypothesis", "sources", "extensions", "extension_config",
             "settings_overrides", "compaction_reserve_tokens", "session_timeout_min"}
W2_ARMS = sorted(p.stem for p in (HERE / "arms").glob("w2-*.json"))


def test_w1_arm_builds_fixture_files():
    arm, _ = w.load_arm("bonsai-2026-10-12")
    fx = json.loads((HERE / "fixtures" / "w1_agent_dir.json").read_text())
    settings, models = w.agent_files(arm, fx["tap"])
    assert settings == fx["settings.json"]
    assert models == fx["models.json"]
    assert [pathlib.Path(e).name for e in arm["extensions"]] == fx["extensions"]


def test_w1_arm_make_agent_dir_has_no_w2_files(tmp_path):
    arm, _ = w.load_arm("bonsai-2026-10-12")
    agent = w.make_agent_dir(arm, tmp_path, "http://127.0.0.1:8091")
    assert not (agent / "w2-config.json").exists()
    assert sorted(p.name for p in (agent / "extensions").iterdir()) == ["submit_request.ts"]


@pytest.mark.parametrize("name", W2_ARMS)
def test_w2_arm_valid_with_hypothesis(name):
    arm, _ = w.load_arm(name)
    assert arm["hypothesis"].strip()
    assert arm["prompt_timeout_min"] == arm["session_timeout_min"] or name.startswith("w2-smoke")


@pytest.mark.parametrize("name", [n for n in W2_ARMS if not n.startswith("w2-smoke")])
def test_w2_arm_differs_from_honest_only_in_mechanism(name):
    base, _ = w.load_arm("bonsai-2026-10-12-honest")
    arm, _ = w.load_arm(name)
    diff = {k for k in set(base) | set(arm) if base.get(k) != arm.get(k)}
    assert diff <= MECHANISM, diff - MECHANISM
    assert diff & {"extensions", "compaction_reserve_tokens"}, "an arm must change its mechanism"


def test_honest_arm_differs_from_w1_only_in_prompt_timeout():
    w1, _ = w.load_arm("bonsai-2026-10-12")
    h, _ = w.load_arm("bonsai-2026-10-12-honest")
    diff = {k for k in set(w1) | set(h) if w1.get(k) != h.get(k)}
    assert diff == {"name", "description", "hypothesis", "prompt_timeout_min", "sources"}
    assert h["prompt_timeout_min"] == 20 == h["session_timeout_min"]


def test_hashline_vendor_has_license_and_patch():
    v = HERE / "vendor" / "pi-hashline-context-edit@0.11.0"
    assert (v / "LICENSE").exists() and (v / "PATCH.diff").exists()


def test_prompt_rewrite_changes_only_the_sentence():
    case = json.loads((HERE / "cases.jsonl").read_text().splitlines()[0])
    honest, _ = w.load_arm("bonsai-2026-10-12-honest")
    w1, _ = w.load_arm("bonsai-2026-10-12")
    a, b = w.render_prompt(case, w1), w.render_prompt(case, honest)
    assert "killed after 45 minutes" in a and "killed after 20 minutes" in b
    assert a.replace("killed after 45 minutes", "killed after 20 minutes") == b


def test_prompt_rewrite_fails_when_sentence_absent():
    with pytest.raises(ValueError):
        w.rewrite_timeout("no such sentence", "c", 20)
    assert w.rewrite_timeout("same", "c", None) == "same"


def test_extension_dir_config_and_overrides(tmp_path):
    arm, _ = w.load_arm("w2-hashline")
    arm = dict(arm, extension_config={"x": {"y": 1}}, settings_overrides={"compaction": {"keepRecentTokens": 5}})
    agent = w.make_agent_dir(arm, tmp_path, "http://127.0.0.1:8091")
    assert (agent / "extensions" / "pi-hashline-context-edit@0.11.0" / "index.ts").exists()
    assert json.loads((agent / "w2-config.json").read_text()) == {"x": {"y": 1}}
    s = json.loads((agent / "settings.json").read_text())
    assert s["compaction"] == {"reserveTokens": arm["compaction_reserve_tokens"], "keepRecentTokens": 5}


# ---- queue ----

def fake_arm_runner(tmp_path, cases, calls, per_attempt_min=10, clock=None):
    def run_arm(entry, left):
        calls.append((entry["arm"], round(left, 1)))
        arm = {"name": entry["arm"], "session_timeout_min": 10}

        def attempt(case, rep):
            clock.t += per_attempt_min * 60
            return {"complete": True, "arm": entry["arm"], "case_id": case["case_id"], "repeat": rep}
        w.run_all(arm, cases, 1, rq.out_dir(entry) / "results.jsonl", left, attempt, clock=clock)
    return run_arm


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


def test_queue_rolls_over_and_resumes(tmp_path):
    cases = [{"case_id": "a"}, {"case_id": "b"}]
    q = [{"arm": "x", "out": str(tmp_path / "x")}, {"arm": "y", "out": str(tmp_path / "y")}]
    clock, calls = Clock(), []
    runner = fake_arm_runner(tmp_path, cases, calls, clock=clock)
    # budget fits 3 attempts of 10 min: x finishes (2), y gets one
    st = rq.run_queue(q, cases, 1, 35, runner, clock=clock, log=lambda *_: None)
    assert [c[0] for c in calls] == ["x", "y"]
    assert st == {"x": (2, 2), "y": (1, 2)}
    # a second chunk resumes y only
    calls.clear()
    clock.t = 0
    st = rq.run_queue(q, cases, 1, 35, runner, clock=clock, log=lambda *_: None)
    assert [c[0] for c in calls] == ["y"]
    assert st == {"x": (2, 2), "y": (2, 2)}


def test_queue_never_starts_attempt_that_does_not_fit(tmp_path):
    cases = [{"case_id": "a"}]
    q = [{"arm": "x", "out": str(tmp_path / "x")}]
    clock, calls = Clock(), []
    st = rq.run_queue(q, cases, 1, 5, fake_arm_runner(tmp_path, cases, calls, clock=clock), clock=clock, log=lambda *_: None)
    assert st["x"] == (0, 1)


def test_queue_progress_rejects_completed_records_from_old_arm_sha(tmp_path):
    entry = {"arm": "x", "out": str(tmp_path / "x"), "_arm_sha256": "current"}
    results = rq.out_dir(entry) / "results.jsonl"
    results.parent.mkdir(parents=True)
    results.write_text("\n".join(json.dumps(x) for x in [
        {"complete": True, "arm": "x", "case_id": "a", "repeat": 1, "arm_sha256": "old"},
        {"complete": True, "arm": "x", "case_id": "b", "repeat": 1, "arm_sha256": "current"},
    ]) + "\n")
    assert rq.progress(entry, [{"case_id": "a"}, {"case_id": "b"}], 1) == (1, 2)


# ---- compare ----

def write_run(d, arm, rows):
    """rows: (case, repeat, valid, kind_match, wall)"""
    d.mkdir(parents=True)
    (d / "manifest-1.json").write_text(json.dumps({"model_sha256": "m", "llama_swap_entry": "e"}))
    for case, rep, valid, km, wall in rows:
        ad = d / case / f"r{rep}"
        ad.mkdir(parents=True)
        rec = {"arm": arm, "case_id": case, "repeat": rep, "valid_request": valid, "kind_match": km, "wall_s": wall,
               "turns": 5, "tools": {"bash": 3, "edit": 1}, "tool_errors": {"edit": 1}, "compaction_start": 0,
               "replay_kind": "run" if valid else None, "request": {"request": "run"} if valid else None,
               "timeout": not valid, "context_overflow": False, "output_limit": False}
        (ad / "record.json").write_text(json.dumps(rec))
        (ad / "tap.jsonl").write_text(json.dumps({"timings": {"predicted_ms": 2000, "prompt_ms": 500, "predicted_n": 40, "prompt_n": 100},
                                                  "usage": {"prompt_tokens": 900}}) + "\n")
        if arm == "arm":
            (ad / "ext.jsonl").write_text(json.dumps({"ext": "drop_old_thinking", "event": "request", "removed_chars": 7}) + "\n")


def fixture_runs(tmp_path):
    cases = [f"c{i}" for i in range(6)]
    base = [(c, r, i % 2 == 0, i % 2 == 0, 100 + i) for i, c in enumerate(cases) for r in (1, 2)]
    arm = [(c, r, True, i % 3 != 0, 90 + i) for i, c in enumerate(cases) for r in (1, 2)]
    write_run(tmp_path / "base", "base", base)
    write_run(tmp_path / "arm", "arm", arm)
    return tmp_path / "base", tmp_path / "arm"


def test_compare_deterministic_and_correct(tmp_path):
    b, a = fixture_runs(tmp_path)
    for n in (1, 2):
        cmp_.main(["--baseline", str(b), "--arm", str(a), "--out", str(tmp_path / f"out{n}")])
    j1 = (tmp_path / "out1.json").read_text()
    assert j1 == (tmp_path / "out2.json").read_text()
    rep = json.loads(j1)
    assert rep["arms"]["base"]["valid"] == 6 and rep["arms"]["arm"]["valid"] == 12
    v = rep["vs_baseline"]["arm"]["valid"]
    assert v["delta"] == 0.5 and v["spread"] == 0  # rate; baseline repeats are identical
    assert v["ci95"][0] > 0 and v["beyond_spread"] is True
    assert rep["arms"]["arm"]["ext_actions"]["drop_old_thinking:removed_chars"] == 12 * 7
    assert rep["arms"]["base"]["edit_like_error_rate"] == 1.0
    assert rep["arms"]["arm"]["kind_match_of_valid"] == 8
    assert rep["arms"]["arm"]["valid_denominator"] == 12
    assert rep["arms"]["arm"]["kind_match_given_valid"] == pytest.approx(8 / 12)
    assert rep["arms"]["base"]["tap_median"]["decode_s"] == 2.0
    assert (tmp_path / "out1.md").read_text().startswith("# W2 comparison")


def test_compare_rates_keep_delta_and_spread_units_with_unequal_baselines(tmp_path):
    # Primary repeat rates are 0/2 and 1/2 (spread .5); the W1-like one-repeat
    # baseline is 3/4 (.75), widening S to .5.  Raw count arithmetic would yield
    # an incomparable multi-repeat delta and a much larger S.
    base = tmp_path / "base"
    arm = tmp_path / "arm"
    w1 = tmp_path / "w1"
    write_run(base, "base", [("a", 1, False, False, 10), ("b", 1, False, False, 10),
                               ("a", 2, True, True, 10), ("b", 2, False, False, 10)])
    write_run(arm, "arm", [(c, r, True, True, 9) for c in ("a", "b") for r in (1, 2)])
    write_run(w1, "bonsai-2026-10-12", [(str(i), 1, i < 3, i < 3, 11) for i in range(4)])
    cmp_.main(["--baseline", str(base), "--baseline", str(w1), "--arm", str(arm), "--out", str(tmp_path / "o")])
    valid = json.loads((tmp_path / "o.json").read_text())["vs_baseline"]["arm"]["valid"]
    assert valid == {"arm": 1.0, "baseline": 0.25, "delta": 0.75, "ci95": valid["ci95"],
                     "cases_in_bootstrap": 2, "spread": 0.5, "beyond_spread": True, "unit": "rate"}


def test_compare_warns_on_model_mismatch(tmp_path):
    b, a = fixture_runs(tmp_path)
    (a / "manifest-1.json").write_text(json.dumps({"model_sha256": "other", "llama_swap_entry": "e"}))
    w1 = tmp_path / "w1"
    write_run(w1, "bonsai-2026-10-12", [("c0", 1, True, True, 50)])
    cmp_.main(["--baseline", str(b), "--baseline", str(w1), "--arm", str(a), "--out", str(tmp_path / "o")])
    assert any("model_sha256" in x for x in json.loads((tmp_path / "o.json").read_text())["warnings"])


# ---- vendored diff replacement ----

def test_diff_lite_and_merge_are_deterministic(tmp_path):
    # Stage the TS source with explicit local extensions solely for Node's native
    # ESM loader; pi's extension loader accepts the package's extensionless imports.
    src = HERE / "vendor" / "pi-hashline-context-edit@0.11.0" / "src"
    staged = tmp_path / "src"
    shutil.copytree(src, staged)
    for p in staged.glob("*.ts"):
        p.write_text(re.sub(r"(from ['\"]\./[^'\".]+)(['\"])", r"\1.ts\2", p.read_text()))
    script = """import { diffLines, diffArrays } from './src/diff-lite.ts';
import { threeWayMerge } from './src/merge.ts';
console.log(JSON.stringify({
 lines: diffLines('a\\nb\\n', 'a\\nc\\n'), arrays: diffArrays(['a','b'], ['a','c','d']),
 merged: threeWayMerge('a\\nb\\nc', 'A\\nb\\nc', 'a\\nb\\nC'),
 conflict: threeWayMerge('a\\nb\\nc', 'a\\nB\\nc', 'a\\nC\\nc')
}));"""
    got = json.loads(subprocess.check_output(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script], cwd=tmp_path, text=True))
    assert got["lines"] == [{"value": "a\n", "count": 1}, {"value": "b\n", "count": 1, "removed": True},
                            {"value": "c\n", "count": 1, "added": True}]
    assert got["arrays"][-2:] == [{"value": ["b"], "count": 1, "removed": True},
                                   {"value": ["c", "d"], "count": 2, "added": True}]
    assert got["merged"]["ok"] is True and got["merged"]["content"] == "A\nb\nC"
    assert got["conflict"] == {"ok": False, "reason": "edited and current changes overlap in base coordinates"}
