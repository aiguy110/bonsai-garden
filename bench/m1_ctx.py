#!/usr/bin/env python3
"""M1 recon: capture the EXACT server-context.cpp lines around speculation.

The recon spec_lines_full.txt only contains lines matching 'speculative|spec',
so lines that do NOT match those keywords — the gating if(...) around spec init,
the surrounding mmproj block, and the checkpoint-mode guard context — were
missing. This script dumps numbered windows from the host's
llama.cpp-bonsai2 tools/server/server-context.cpp and greps for the gating
tokens, so we can cross-check the §3 claims in m1-notes.md and only keep the
'cross-checked' wording after verification.

Read-only on the host. No GPU, no network. Writes recon/spec_ctx.txt.
"""
import pathlib
import os
import subprocess

HOME = pathlib.Path(os.environ.get("HOME", "/home/dev"))
# Candidate build trees (host home differs from sandbox home).
candidates = [
    HOME / "Projects" / "llama.cpp-bonsai2",
    pathlib.Path("/home/josiah/Projects/llama.cpp-bonsai2"),
    pathlib.Path("/home/dev/Projects/llama.cpp-bonsai2"),
]
LLAMA = next(c for c in candidates if (c / "tools" / "server" / "server-context.cpp").exists())
SC = LLAMA / "tools" / "server" / "server-context.cpp"
OUT = (pathlib.Path(os.environ.get("RECON_DIR")
                     or (pathlib.Path(__file__).resolve().parents[0]
                          / "results" / "2026-10-12" / "m1-ngram" / "recon"))) / "spec_ctx.txt"

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(LLAMA))
    return r.stdout, r.stderr

def main():
    with SC.open() as f:
        lines = f.readlines()
    n = len(lines)
    out = []
    out.append(f"# server-context.cpp  {SC}  (total lines: {n})\n")

    # Two windows: the mmproj/multimodal block (~1115-1145) and the
    # spec-init / slot.spec block (~1150-1230).
    for a, b in ((1115, 1145), (1150, min(1230, n + 1))):
        lo, hi = a, min(b, n + 1)
        out.append(f"\n# numbered window {lo}-{hi}\n")
        for i in range(lo - 1, hi - 1):
            out.append(f"{i + 1}: {lines[i].rstrip(chr(10))}\n")

    out.append("\n# grep ctx_tgt_seq_rm_type (entire file)\n")
    so, _ = run(["grep", "-n", "ctx_tgt_seq_rm_type", "tools/server/server-context.cpp"])
    out.append(so.rstrip() + "\n")

    out.append("\n# grep spec.reset / common_speculative_init / slot.spec (entire file)\n")
    so, _ = run(["grep", "-n",
                 "spec.reset\\|common_speculative_init\\|slot\\.spec\\|spec.get\\|spec = ",
                 "tools/server/server-context.cpp"])
    out.append(so.rstrip() + "\n")

    out.append("\n# grep checkpoint / this context guard (for the 1168 line context)\n")
    so, _ = run(["grep", "-n",
                 "speculative decoding not supported by this context\\|checkpoint\\|n_ctx",
                 "tools/server/server-context.cpp"])
    out.append(so.rstrip() + "\n")

    OUT.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(out))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes) from {SC}")

if __name__ == "__main__":
    main()
