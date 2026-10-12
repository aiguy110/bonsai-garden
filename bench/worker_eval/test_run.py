"""Fixture tests for bench/worker_eval/run.py: no GPU, docker, network or pi needed.

  python3 -m pytest bench/worker_eval/test_run.py
"""
import importlib.util
import json
import pathlib

import pytest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("worker_eval_run", HERE / "run.py")
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

OLD = "claude-sonnet-5-5, a cloud model"
NEW = "Bonsai 2 27B (Ternary-Bonsai-2-27B, 2-bit), a local model on this machine's GPU"
PROMPT = f"You are the research worker for bonsai-garden, running as {NEW}. The project\nstudies a stack.\n"


def case(cid="c1", kind="run"):
    return {"case_id": cid, "prompt": PROMPT, "worker_description_to": NEW, "item": "x",
            "advisor_verdict": "approve", "request": {"request": kind}}


def ev_lines(*events):
    return "\n".join(json.dumps(e) if not isinstance(e, str) else e for e in events) + "\n"


def msg_end(stop, text="", err=None):
    m = {"role": "assistant", "content": [{"type": "text", "text": text}], "stopReason": stop}
    if err:
        m["errorMessage"] = err
    return {"type": "message_end", "message": m}


# ---- arms ----

def test_baseline_arm_valid_and_pinned():
    arm, h = w.load_arm("bonsai-2026-10-12")
    assert len(h) == 64
    assert arm["worker_memory"] is None
    assert arm["session_timeout_min"] == 20
    assert arm["compaction_reserve_tokens"] == 28672
    assert arm["max_output_tokens"] == 16384
    assert arm["thinking"] == "low"
    assert arm["extensions"] == ["autopilot/extensions/submit_request.ts"]
    assert (w.ROOT / arm["extensions"][0]).is_file()
    reg = json.loads((w.ROOT / "agent/models.bonsai-agent.json").read_text())
    assert (reg["maxTokens"], reg["contextWindow"]) == (arm["max_output_tokens"], arm["context_window"])


def test_arm_validation_errors():
    schema = json.loads((w.ARMS / "schema.json").read_text())
    arm, _ = w.load_arm("bonsai-2026-10-12")
    assert w.validate_arm(arm, schema) == []
    bad = dict(arm, thinking="extreme", session_timeout_min=0, extra=1)
    del bad["model"]
    errs = " ".join(w.validate_arm(bad, schema))
    for frag in ("missing model", "unknown field extra", "thinking must be one of", "session_timeout_min must be above"):
        assert frag in errs
    assert w.validate_arm(dict(arm, max_output_tokens=True), schema)  # bool is not an integer


def test_agent_files_follow_arm():
    arm, _ = w.load_arm("bonsai-2026-10-12")
    settings, models = w.agent_files(arm, "http://127.0.0.1:8091")
    assert settings["compaction"] == {"reserveTokens": 28672}
    assert settings["defaultThinkingLevel"] == "low"
    entry = models["providers"]["garden"]["models"][0]
    assert entry["id"] == "bonsai-agent" and entry["maxTokens"] == 16384


# ---- model substitution ----

def test_render_prompt_replaces_line_once():
    arm, _ = w.load_arm("bonsai-2026-10-12")
    other = dict(arm, worker_description="Other 1B, a toy")
    out = w.render_prompt(case(), other)
    assert "running as Other 1B, a toy. The project" in out and NEW not in out
    assert out.replace("Other 1B, a toy", NEW) == PROMPT


def test_render_prompt_rejects_wrong_or_missing_line():
    arm, _ = w.load_arm("bonsai-2026-10-12")
    c = case()
    c["prompt"] = PROMPT.replace(NEW, OLD)
    with pytest.raises(ValueError):
        w.render_prompt(c, arm)
    c["prompt"] = "no model line here"
    with pytest.raises(ValueError):
        w.render_prompt(c, arm)
    c["prompt"] = PROMPT + PROMPT
    with pytest.raises(ValueError):
        w.render_prompt(c, arm)


# ---- events ----

def test_parse_events_counts(tmp_path):
    f = tmp_path / "e.jsonl"
    f.write_text(ev_lines(
        {"type": "session"},
        {"type": "tool_execution_start", "toolCallId": "a", "toolName": "bash"},
        {"type": "tool_execution_end", "toolCallId": "a", "toolName": "bash", "result": {"isError": True}},
        {"type": "tool_execution_start", "toolCallId": "b", "toolName": "read"},
        {"type": "tool_execution_end", "toolCallId": "b", "toolName": "read", "result": {"content": []}},
        {"type": "tool_execution_start", "toolCallId": "c", "toolName": "bash"},
        {"type": "tool_execution_end", "toolCallId": "c", "isError": True},
        {"type": "compaction_start"}, {"type": "compaction_end"}, {"type": "compaction_start"},
        msg_end("toolUse", "thinking out loud"),
        {"type": "turn_end"}, {"type": "turn_end"},
        "not json {",
        msg_end("stop", "all done"),
    ))
    r = w.parse_events(f)
    assert (r["turns"], r["tool_calls"]) == (2, 3)
    assert r["tools"] == {"bash": 2, "read": 1}
    assert r["tool_errors"] == {"bash": 2}
    assert (r["compaction_start"], r["compaction_end"]) == (2, 1)
    assert r["stop_reasons"] == ["toolUse", "stop"] and r["last_stop"] == "stop"
    assert r["final"] == "all done" and r["bad_lines"] == 1 and r["errors"] == []


def test_parse_events_errors_and_empty(tmp_path):
    f = tmp_path / "e.jsonl"
    f.write_text(ev_lines(msg_end("error", "", "400 context_length_exceeded: 90000 > 81920")))
    r = w.parse_events(f)
    assert r["errors"] == ["400 context_length_exceeded: 90000 > 81920"] and r["last_stop"] == "error"
    f.write_text("")
    assert w.parse_events(f)["last_stop"] is None


# ---- error classification ----

@pytest.mark.parametrize("stops,errors,timed_out,flag", [
    (["length"], [], False, "output_limit"),
    (["error"], ["context_length_exceeded"], False, "context_overflow"),
    (["error"], ["request (91234 tokens) exceeds the available context size (81920)"], False, "context_overflow"),
    (["stop"], [], True, "timeout"),
    (["error"], ["429 usage limit reached"], False, "rate_limit"),
])
def test_classify(stops, errors, timed_out, flag):
    ev = {"stop_reasons": stops, "errors": errors}
    flags = w.classify(ev, timed_out)
    assert flags[flag] is True
    assert [k for k, v in flags.items() if v and k != flag and k != "pi_exit_nonzero"] == []


def test_classify_clean_and_exit_code():
    ev = {"stop_reasons": ["toolUse", "stop"], "errors": []}
    assert not any(w.classify(ev, False, 0).values())
    assert w.classify(ev, False, 1)["pi_exit_nonzero"] is True
    assert w.classify(ev, True, -9)["pi_exit_nonzero"] is False  # a timeout kill is not a crash


# ---- request detection and validation ----

def repo(tmp_path):
    (tmp_path / "bench").mkdir()
    (tmp_path / "bench" / "x.py").write_text("print(1)\n")
    (tmp_path / "serving" / "candidates").mkdir(parents=True)
    (tmp_path / "serving" / "candidates" / "e.yaml").write_text("a: 1\n")
    return tmp_path


def test_detect_request_prefers_tool_then_fallback_then_none(tmp_path):
    rf = tmp_path / "request.json"
    final = 'done.\n```json\n{"request": "continue", "note": "n", "report": "r"}\n```'
    assert w.detect_request(rf, final) == ("json_fallback", {"request": "continue", "note": "n", "report": "r"})
    rf.write_text(json.dumps({"request": "done", "summary": "s", "report": "r"}))
    assert w.detect_request(rf, final)[0] == "tool"
    rf.write_text("{broken")
    assert w.detect_request(rf, final)[0] == "json_fallback"
    assert w.detect_request(tmp_path / "none.json", "no json here") == ("none", None)
    assert w.last_json('x {"a": 1} then {"b": 2}') == {"b": 2}


def test_validate_run_request(tmp_path):
    r = repo(tmp_path)
    good = {"request": "run", "report": "r", "command": "python3 bench/x.py --a 1", "gpu": False,
            "timeout_min": 10, "why": "w"}
    assert w.validate_request(good, r) == []
    cases = [
        (dict(good, command="python3 bench/missing.py"), "does not exist"),
        (dict(good, command="python3 tools/x.py"), "must be under bench/ or evals/"),
        (dict(good, command="python3 bench/x.py | cat"), "no shell operators"),
        (dict(good, command="python3 bench/../../etc/passwd"), "must be under bench/ or evals/"),
        (dict(good, command="ruby bench/x.py"), "python3"),
        (dict(good, gpu="no"), '"gpu" is required'),
        (dict(good, timeout_min=181), "timeout_min"),
        (dict(good, timeout_min=True), "timeout_min"),
        (dict(good, report=" "), '"report" is required'),
        (dict(good, why=""), '"why" is required'),
    ]
    for req, frag in cases:
        assert any(frag in e for e in w.validate_request(req, r)), (req, frag)


def test_validate_other_kinds(tmp_path):
    r = repo(tmp_path)
    ok = {"report": "r"}
    assert w.validate_request({**ok, "request": "continue", "note": "n"}, r) == []
    assert w.validate_request({**ok, "request": "done", "summary": "s"}, r) == []
    assert w.validate_request({**ok, "request": "stuck", "why": "w"}, r) == []
    assert w.validate_request({**ok, "request": "infra", "entry": "serving/candidates/e.yaml", "why": "w"}, r) == []
    assert w.validate_request({**ok, "request": "infra", "entry": "serving/other.yaml", "why": "w"}, r)
    assert w.validate_request({**ok, "request": "infra", "entry": "serving/candidates/nope.yaml", "why": "w"}, r)
    assert w.validate_request({**ok, "request": "continue"}, r)
    assert w.validate_request({**ok, "request": "bogus"}, r)
    assert w.validate_request(["not", "a", "dict"], r)


def test_orchestrator_check_hook_is_used(tmp_path):
    r = repo(tmp_path)
    good = {"request": "run", "report": "r", "command": "python3 bench/x.py", "gpu": True, "why": "w"}
    errs = w.validate_request(good, r, lambda cmd, repo: (None, "nope"))
    assert errs == ["orchestrator: nope"]


def test_record_kind_match_and_validity():
    arm, _ = w.load_arm("bonsai-2026-10-12")
    ev = {"turns": 3, "tool_calls": 2, "tools": {"bash": 2}, "tool_errors": {}, "compaction_start": 0,
          "compaction_end": 0, "stop_reasons": ["stop"], "last_stop": "stop", "errors": []}
    flags = w.classify(ev, False, 0)
    req = {"request": "run", "report": "r"}
    rec = w.build_record(arm, case(kind="run"), 1, "tool", req, [], ev, flags, 12.34)
    assert rec["valid_request"] and rec["kind_match"] and rec["wall_s"] == 12.3
    rec = w.build_record(arm, case(kind="done"), 1, "tool", req, ["x"], ev, flags, 1)
    assert not rec["valid_request"] and not rec["kind_match"]
    rec = w.build_record(arm, case(), 1, "none", None, ["no request"], ev, flags, 1)
    assert not rec["valid_request"] and rec["replay_kind"] is None and not rec["kind_match"]


# ---- resume and budget ----

class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_resume_skips_only_completed(tmp_path):
    arm, _ = w.load_arm("bonsai-2026-10-12")
    cases = [case("a"), case("b")]
    results = tmp_path / "results.jsonl"
    calls = []

    def attempt(c, rep):
        calls.append((c["case_id"], rep))
        return {"complete": True, "arm": arm["name"], "case_id": c["case_id"], "repeat": rep}

    log = []
    s = w.run_all(arm, cases, 2, results, 145, attempt, log=log.append)
    assert calls == [("a", 1), ("b", 1), ("a", 2), ("b", 2)] and s["ran"] == 4
    calls.clear()
    s = w.run_all(arm, cases, 2, results, 145, attempt, log=log.append)
    assert calls == [] and s == {"skipped": 4, "ran": 0, "remaining": 0}
    assert len(w.load_records(results)) == 4  # no duplicates
    # an incomplete record and a torn line do not count as done
    results.write_text(json.dumps({"complete": True, "arm": arm["name"], "case_id": "a", "repeat": 1}) + "\n"
                       + json.dumps({"arm": arm["name"], "case_id": "b", "repeat": 1}) + "\n{torn")
    w.run_all(arm, cases, 1, results, 145, attempt, log=log.append)
    assert calls == [("b", 1)]
    # another arm's records do not satisfy this arm
    assert w.completed([{"complete": True, "arm": "other", "case_id": "a", "repeat": 1}]) == {("other", "a", 1)}


def test_budget_stops_when_timeout_does_not_fit(tmp_path):
    arm, _ = w.load_arm("bonsai-2026-10-12")  # 20 min timeout
    clock = Clock()

    def attempt(c, rep):
        clock.t += 60 * 60  # each attempt "takes" an hour
        return {"complete": True, "arm": arm["name"], "case_id": c["case_id"], "repeat": rep}

    log = []
    results = tmp_path / "r.jsonl"
    cases = [case("a"), case("b"), case("c")]
    s = w.run_all(arm, cases, 1, results, 145, attempt, clock=clock, log=log.append)
    # 145 -> 85 min left after one (fits 20), 25 left after two (fits), 0 after... third starts at 25 left
    assert s["ran"] == 3 and s["remaining"] == 0
    clock.t = 0
    s = w.run_all(arm, [case("d"), case("e")], 1, results, 100, attempt, clock=clock, log=log.append)
    assert s["ran"] == 2  # 100 min, then 40 left, still fits 20
    clock.t = 0
    s = w.run_all(arm, [case("f"), case("g")], 1, results, 70, attempt, clock=clock, log=log.append)
    assert s["ran"] == 1 and s["remaining"] == 1 and "stopping" in log[-1]


def test_infra_failures_are_not_recorded(tmp_path):
    arm, _ = w.load_arm("bonsai-2026-10-12")
    results = tmp_path / "r.jsonl"
    s = w.run_all(arm, [case(str(i)) for i in range(5)], 1, results, 145, lambda c, r: None, log=lambda m: None)
    assert s["ran"] == 0 and s["remaining"] == 3 + 2 and not results.exists()


def test_real_cases_render():
    arm, _ = w.load_arm("bonsai-2026-10-12")
    cases = w.load_cases(HERE / "cases.jsonl")
    assert len(cases) >= 20
    for c in cases:
        assert NEW in w.render_prompt(c, arm)


def test_run_command_check_matches_autopilot(tmp_path):
    """Where autopilot.py can be imported (the host), its check agrees with the local copy."""
    try:
        check = w.orchestrator_check()
    except Exception as e:  # noqa: BLE001
        pytest.skip(str(e))
    if check is w.check_run_command:
        pytest.skip("autopilot.py not importable here")
    r = repo(tmp_path)
    for cmd in ("python3 bench/x.py a", "python3 bench/none.py", "bash tools/x.sh", "python3 bench/x.py | cat", "ruby bench/x.py"):
        assert (check(cmd, r)[1] is None) == (w.check_run_command(cmd, r)[1] is None), cmd
