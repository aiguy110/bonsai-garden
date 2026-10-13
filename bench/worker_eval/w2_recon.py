#!/usr/bin/env python3
"""W2 recon (host, no GPU): pi and llama.cpp mechanisms, hashline packages, provenance, drift.

Writes bench/results/<date>/worker-eval-w2/recon/{pi.txt,llama.txt,packages/,provenance/,drift.json}.
Read-only on the live stack. Packages are fetched with `npm pack --ignore-scripts` into fresh
directories and unpacked with tarfile; nothing is installed or executed.

  python3 bench/worker_eval/w2_recon.py [--out DIR]
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
W1 = ROOT / "bench/results/2026-10-13/worker-eval/bonsai-2026-10-12"
PACKAGES = ["pi-hashline-edit", "pi-hashline-context-edit"]
MAX_HITS = 120


def sh(*cmd, cwd=None, timeout=300):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    return (p.stdout + (("\n" + p.stderr) if p.stderr.strip() else "")).strip(), p.returncode


def grep(files, patterns, ctx=1, cap=MAX_HITS):
    """Lines matching any pattern, as 'path:line: text' with `ctx` lines of context ('-' separator)."""
    rx = re.compile("|".join(patterns))
    out, n = [], 0
    for f in files:
        try:
            lines = pathlib.Path(f).read_text(errors="replace").splitlines()
        except OSError:
            continue
        keep = set()
        for i, l in enumerate(lines):
            if rx.search(l):
                keep.update(range(max(0, i - ctx), min(len(lines), i + ctx + 1)))
                n += 1
        prev = None
        for i in sorted(keep):
            if prev is not None and i != prev + 1:
                out.append("--")
            out.append(f"{f}:{i + 1}{':' if rx.search(lines[i]) else '-'} {lines[i][:240]}")
            prev = i
        if n >= cap:
            out.append(f"... capped at {cap} matches")
            break
    return out


def find_files(base, names=(), suffixes=(".js", ".ts", ".md"), skip=("node_modules", ".map", ".d.ts.map")):
    base = pathlib.Path(base)
    res = []
    if not base.exists():
        return res
    for p in sorted(base.rglob("*")):
        rel = str(p.relative_to(base))
        if p.is_file() and p.suffix in suffixes and not any(s in rel for s in skip):
            if not names or any(re.search(n, str(p)) for n in names):
                res.append(str(p))
    return res


def package_dir(start, name_rx):
    p = pathlib.Path(start).resolve()
    for d in [p, *p.parents]:
        pj = d / "package.json"
        if pj.exists():
            try:
                if re.search(name_rx, json.loads(pj.read_text()).get("name", "")):
                    return d
            except ValueError:
                pass
    return None


def find_pi_ai(pi_pkg):
    for cand in [pi_pkg / "node_modules/@earendil-works/pi-ai", pi_pkg.parent / "pi-ai",
                 *pi_pkg.parents[1].glob("**/@earendil-works/pi-ai")]:
        if (cand / "package.json").exists():
            return cand
    return None


def section(title, lines):
    return [f"\n===== {title} =====", *(lines or ["(no matches)"])]


def pi_report(out):
    ver, _ = sh("pi", "--version")
    exe = shutil.which("pi")
    real = os.path.realpath(exe) if exe else None
    pkg = package_dir(real, r"pi-coding-agent") if real else None
    L = [f"pi --version: {ver}", f"which pi: {exe}", f"realpath: {real}", f"package dir: {pkg}"]
    if pkg:
        L.append(f"package.json: {json.dumps({k: v for k, v in json.loads((pkg / 'package.json').read_text()).items() if k in ('name', 'version')})}")
    dist = pkg / "dist" if pkg else None
    docs = pkg / "docs" if pkg else None
    allf = find_files(dist) + find_files(docs) if pkg else []
    docs_f = [f for f in allf if "/docs/" in f]
    L += section("docs listing", sorted(os.path.relpath(f, pkg) for f in docs_f))
    ext_ts = [f for f in allf if re.search(r"extensions/(types|runner|loader|index)\.", f)]
    ext_docs = [f for f in docs_f if re.search(r"extension", f, re.I)]
    L += section("extension API: handler names (pi.on / on(event:)) in types and docs",
                 grep(ext_ts + ext_docs, [r'on\(event: "', r'pi\.on\("', r'^#+ .*(event|hook)', r'type ExtensionEvent']))
    L += section("extension API: events that see/rewrite messages or the provider payload (context, before_provider_request, ...)",
                 grep(ext_ts + ext_docs, [r'context', r'before_provider', r'provider_request', r'ContextEventResult', r'messages\??:']), )
    L += section("extension API: tool_call blocking, tool_result rewriting, session_start, return types",
                 grep(ext_ts + ext_docs, [r'ToolCallEventResult', r'ToolResultEventResult', r'block\??:', r'reason\??:',
                                          r'session_start', r'SessionStartEvent', r'tool_result', r'tool_call']))
    L += section("registerTool and replacing built-in tools",
                 grep(ext_ts + ext_docs + [f for f in allf if re.search(r'agent-session|sdk|tool-registry', f)],
                      [r'registerTool', r'override', r'replace[sd]? (a )?built-?in', r'built-?in tool', r'same name']))
    tools = [f for f in allf if re.search(r"core/tools/(truncate|bash|read|edit)\.js$", f)]
    L += section("built-in truncation constants and notice text",
                 grep(tools, [r'DEFAULT_MAX_(LINES|BYTES)', r'MAX_(LINES|BYTES)\s*=', r'Showing (lines|last)', r'truncated', r'Full output', r'offset=']))
    comp = [f for f in allf if re.search(r"compaction|agent-session\.js$|settings-manager\.js$", f)]
    L += section("compaction: trigger, reserveTokens, keepRecentTokens, summary max_tokens, thinking",
                 grep(comp, [r'reserveTokens', r'keepRecentTokens', r'shouldCompact', r'maxTokens', r'max_tokens', r'reasoning',
                             r'thinkingLevel', r'DEFAULT_COMPACTION', r'contextTokens\s*>']))
    pi_ai = find_pi_ai(pkg) if pkg else None
    L.append(f"\npi-ai dir: {pi_ai}")
    if pi_ai:
        oc = [f for f in find_files(pi_ai / "dist", suffixes=(".js",)) if re.search(r"openai-completions\.js$", f)]
        L += section("pi-ai openai-completions: serialisation of earlier assistant thinking",
                     grep(oc, [r'reasoning_content', r'thinkingSignature', r'reasoning_text', r'"reasoning"', r"'reasoning'",
                               r'requiresThinkingAsText', r'type === "thinking"', r'max_tokens', r'maxTokensField']))
        L += section("pi-ai: transformMessages / thinking handling across turns",
                     grep([f for f in find_files(pi_ai / "dist", suffixes=(".js",)) if re.search(r"transform-messages\.js$", f)],
                          [r'thinking', r'redacted', r'signature']))
    (out / "pi.txt").write_text("\n".join(L) + "\n")


def llama_report(out):
    text = pathlib.Path("/etc/llama-swap/config.yaml").read_text()
    m = re.search(r'^  "?bonsai-2-27b"?:\s*\n((?:    .*\n|\s*\n)+)', text, re.M)
    entry = m.group(1) if m else None
    L = ["bonsai-2-27b llama-swap entry (read-only):", entry or "(not found)"]
    binary = None
    if entry:
        for tok in re.findall(r"\S+", entry):
            if tok.rstrip("\\").endswith("llama-server"):
                binary = tok.rstrip("\\").strip("\"'")
                break
    L.append(f"binary: {binary}")
    srcdir = None
    if binary:
        v, rc = sh(binary, "--version", timeout=120)
        L += [f"--version (rc={rc}):", v]
        h, _ = sh(binary, "--help", timeout=120)
        L += section("--help lines on reasoning", [l for l in h.splitlines() if re.search(r"reasoning|think", l, re.I)])
        b = pathlib.Path(os.path.realpath(binary))
        home = pathlib.Path.home()
        cands = [*b.parents[:6], home / "llama.cpp", home / "src/llama.cpp", home / "Projects/llama.cpp"]
        for c in cands:
            if (c / "tools/server").is_dir() or (c / "examples/server").is_dir():
                srcdir = c
                break
    L.append(f"\nsource dir: {srcdir}")
    if srcdir:
        files = [f for f in find_files(srcdir / "tools/server", suffixes=(".cpp", ".h", ".hpp")) +
                 find_files(srcdir / "examples/server", suffixes=(".cpp", ".hpp", ".h")) +
                 find_files(srcdir / "common", suffixes=(".cpp", ".h"))]
        L += section("source: reasoning budget fields, defaults, behaviour at the budget",
                     grep(files, [r'reasoning_budget', r'thinking_budget', r'budget_message', r'budget_tokens'], ctx=2, cap=200))
        L += section("git revision", [sh("git", "-C", str(srcdir), "rev-parse", "HEAD")[0]])
    else:
        L.append("(llama.cpp source tree not found next to the binary or under ~; the help lines above are all there is)")
    (out / "llama.txt").write_text("\n".join(L) + "\n")


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def safe_extract(tarball, dest):
    with tarfile.open(tarball) as t:
        for m in t.getmembers():
            target = (dest / m.name).resolve()
            if not str(target).startswith(str(dest.resolve()) + os.sep) or m.issym() or m.islnk() or m.isdev():
                raise SystemExit(f"unsafe tar member {m.name!r} in {tarball}")
        t.extractall(dest)


def packages(out):
    base = out / "packages"
    base.mkdir(exist_ok=True)
    manifest = []
    for name in PACKAGES:
        d = base / name
        d.mkdir()  # fresh and empty, or fail
        stage = pathlib.Path(tempfile.mkdtemp(prefix="w2-npm-"))
        o, rc = sh("npm", "pack", name, "--ignore-scripts", "--json", "--pack-destination", str(d), cwd=str(stage))
        shutil.rmtree(stage, ignore_errors=True)
        if rc:
            manifest.append({"name": name, "error": o[-500:]})
            continue
        info = json.loads(o[o.index("["):])[0]
        tgz = d / info["filename"]
        un = d / "unpacked"
        un.mkdir()
        safe_extract(tgz, un)
        pj = json.loads((un / "package/package.json").read_text())
        lic = [f.name for f in (un / "package").iterdir() if re.match(r"licen[sc]e", f.name, re.I)]
        manifest.append({"name": pj["name"], "version": pj["version"], "tarball": str(tgz.relative_to(out)),
                         "tarball_sha256": sha256_file(tgz), "registry_integrity": info.get("integrity"),
                         "registry_shasum": info.get("shasum"), "license": pj.get("license"), "license_files": lic,
                         "dependencies": pj.get("dependencies", {}), "peerDependencies": pj.get("peerDependencies", {}),
                         "files": [f["path"] for f in info.get("files", [])], "unpacked_dir": str(un.relative_to(out))})
    (base / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def provenance(out):
    d = out / "provenance"
    d.mkdir(exist_ok=True)
    o, rc = sh(sys.executable, str(HERE / "inspect_historical_arm.py"), cwd=str(ROOT), timeout=600)
    (d / "inspect_stdout.txt").write_text(o + "\n")
    path = next((l.strip() for l in o.splitlines() if l.strip().endswith(".json") and "historical-arm-provenance" in l), None)
    rep = {"rc": rc, "report": None}
    if path:
        src = pathlib.Path(path)
        src = src if src.is_absolute() else ROOT / src
        shutil.copy(src, d / src.name)
        data = json.loads(src.read_text())
        arm = (HERE / "arms/bonsai-2026-10-12.json").read_text()
        old_hashes = sorted(set(re.findall(r"\b[0-9a-f]{64}\b", arm)))
        raw = []
        for c in data.get("candidates", []):
            raw.append({"commit": c["commit"], "config_path": c["config_path"], "config_sha256_raw_blob": c["config_sha256"],
                        "model_registrations": [{"path": r["path"], "sha256_raw_blob": r["sha256"]} for r in c.get("model_registrations", [])]})
        all_raw = {x for r in raw for x in [r["config_sha256_raw_blob"], *[m["sha256_raw_blob"] for m in r["model_registrations"]]]}
        rep = {"rc": rc, "report": src.name, "raw_blob_hashes": raw, "old_arm_file_hashes": old_hashes,
               "old_hashes_equal_raw_blob_hashes": {h: h in all_raw for h in old_hashes},
               "note": "The old arm file (not edited) hashed stripped text; any False above means the arm file's hash is of text, "
                       "not of blob bytes."}
    (d / "report.json").write_text(json.dumps(rep, indent=2) + "\n")


def load(name, path, alias=None):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    if alias:
        sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


def drift(out):
    ev = load("garden_evals_run", ROOT / "evals/run.py", alias="run")
    w1run = load("w1_run", HERE / "run.py")
    sha, repaired = w1run.pinned_model_sha256(ev)
    cur = {"model_sha256": sha, "llama_swap_entry": ev.swap_entry("bonsai-2-27b"),
           "pi_version": ev.sh("pi", "--version"),
           "sandbox_image": ev.sh("docker", "image", "inspect", ev.SANDBOX_IMAGE, "--format", "{{.Id}}"),
           "turnstile_commit": ev.sh("git", "-C", str(ev.TURNSTILE_CONFIG.parent), "rev-parse", "HEAD")}
    mans = [json.loads(p.read_text()) for p in sorted(W1.glob("manifest-*.json"))]
    w1 = {k: sorted({m.get(k) for m in mans}, key=str) for k in cur}
    diff = {k: w1[k] != [cur[k]] for k in cur}
    (out / "drift.json").write_text(json.dumps({
        "drift": bool(diff["model_sha256"] or diff["llama_swap_entry"] or diff["pi_version"]),
        "rule": "drift is true if model_sha256, llama_swap_entry or pi_version differs from any of the W1 manifests",
        "w1_manifests": len(mans), "differs": diff, "current": cur, "w1_values": w1,
        "model_sha_cache_repaired": repaired}, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    a = ap.parse_args()
    out = pathlib.Path(a.out) if a.out else ROOT / "bench/results" / datetime.date.today().isoformat() / "worker-eval-w2/recon"
    out.mkdir(parents=True, exist_ok=True)
    for step in (pi_report, llama_report, packages, provenance, drift):
        try:
            step(out)
            print("ok", step.__name__)
        except BaseException as e:  # noqa: BLE001  keep going; each section is independent
            print("FAILED", step.__name__, type(e).__name__, e)
            (out / f"{step.__name__}.error.txt").write_text(f"{type(e).__name__}: {e}\n")
    print(out)


if __name__ == "__main__":
    main()
