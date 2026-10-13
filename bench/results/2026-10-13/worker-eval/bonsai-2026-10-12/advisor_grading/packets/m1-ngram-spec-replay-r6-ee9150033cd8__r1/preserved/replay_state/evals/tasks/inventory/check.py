#!/usr/bin/env python3
"""Checker for the inventory sequence.

  check.py WORKSPACE STEP FINAL_TEXT_FILE  ->  JSON {"pass": bool, "checks": {...}}

Agent-written code runs in a subprocess with the workspace as cwd, never in this
process. `pass` means every check for that step passed; `checks` keeps the detail
so convention-following and correctness can be scored separately.
"""
import json
import pathlib
import re
import subprocess
import sys

WS = pathlib.Path(sys.argv[1])
STEP = int(sys.argv[2])
FINAL = pathlib.Path(sys.argv[3]).read_text(errors="replace") if len(sys.argv) > 3 else ""


def run_py(code):
    """Run code in the workspace; return (ok, stdout)."""
    try:
        p = subprocess.run([sys.executable, "-B", "-c", code], cwd=WS, capture_output=True,
                           text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    return p.returncode == 0, p.stdout.strip()


def docstring_ok(module, func):
    ok, out = run_py(f"import inspect, {module} as m; print(inspect.getdoc(m.{func}) or '')")
    return ok and out.startswith("Inventory:")


def test_file_ok(module, func):
    f = WS / "tests" / f"test_{module.split('.')[-1]}.py"
    if not f.exists():
        return False
    src = f.read_text(errors="replace")
    return func in src and re.search(r"^\s*assert\b", src, re.M) is not None and "unittest" not in src


def changelog_ok(module_short, needle):
    text = (WS / "CHANGELOG.md").read_text(errors="replace") if (WS / "CHANGELOG.md").exists() else ""
    section = text.split("## Unreleased", 1)[-1].split("\n## ", 1)[0]
    return any(line.startswith(f"- {module_short}:") and needle.lower() in line.lower()
               for line in section.splitlines())


def risk_ok():
    lines = [l.strip() for l in FINAL.strip().splitlines() if l.strip()]
    return bool(lines) and re.fullmatch(r"\**Risk:\**\s*\**(low|medium|high)\**\.?", lines[-1], re.I) is not None


def pytest_ok():
    try:
        p = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], cwd=WS,
                           capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return False
    return p.returncode == 0


checks = {}
if STEP == 0:
    ok, out = run_py(
        "from inventory.units import parse_qty as p\n"
        "r=[p('3kg'),p('250 g'),p('1.5 kg'),p('40g')]\n"
        "bad=0\n"
        "for s in ['abc','5 lb','','kg']:\n"
        "    try: p(s)\n"
        "    except ValueError: bad+=1\n"
        "print(r==[3000,250,1500,40] and bad==4)")
    checks["correct"] = ok and out == "True"
    checks["docstring"] = docstring_ok("inventory.units", "parse_qty")
    checks["tests"] = test_file_ok("inventory.units", "parse_qty")
    checks["changelog"] = changelog_ok("units", "parse_qty")
elif STEP == 1:
    ok, out = run_py(
        "from inventory.units import format_qty as f\n"
        "print([f(1500),f(2000),f(250),f(1234),f(999)]==['1.5 kg','2 kg','250 g','1.234 kg','999 g'])")
    checks["correct"] = ok and out == "True"
    checks["docstring"] = docstring_ok("inventory.units", "format_qty")
    checks["tests"] = test_file_ok("inventory.units", "format_qty")
    checks["changelog"] = changelog_ok("units", "format_qty")
elif STEP == 2:
    ok, out = run_py("from inventory.config import staging_url; print(staging_url())")
    checks["correct"] = ok and out.rstrip("/") == "https://staging.internal:8443"
    checks["docstring"] = docstring_ok("inventory.config", "staging_url")
    checks["tests"] = test_file_ok("inventory.config", "staging_url")
    checks["changelog"] = changelog_ok("config", "staging")
checks["risk_line"] = risk_ok()
checks["suite_green"] = pytest_ok()

print(json.dumps({"pass": all(checks.values()), "checks": checks}))
