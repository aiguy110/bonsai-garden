#!/usr/bin/env python3
"""Pack stock oh-my-pi for W2 recon without installing it.

This intentionally uses only ``npm pack --ignore-scripts`` in a fresh directory.
It records registry metadata and unpacks the tarball with Python so the later harness
can inspect exactly the artifact it will mount, rather than a dependency-installed
working tree.
"""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "bench/results/2026-10-13/worker-eval-w2/recon"
PACKAGE = "oh-my-pi"


def run(*argv, cwd=None):
    p = subprocess.run(argv, cwd=cwd, text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError("%s failed (%s):\n%s\n%s" % (" ".join(argv), p.returncode, p.stdout, p.stderr))
    return p.stdout.strip()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="omp-pack-") as td:
        work = pathlib.Path(td)
        # npm reports the exact tarball basename on stdout. --ignore-scripts is
        # explicit even though npm pack normally does not install dependencies.
        packed = run("npm", "pack", PACKAGE, "--ignore-scripts", "--json", cwd=work)
        rows = json.loads(packed)
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise RuntimeError("unexpected npm pack --json output: " + packed)
        row = rows[0]
        tarball = work / row["filename"]
        if not tarball.is_file():
            raise RuntimeError("npm did not create " + str(tarball))
        digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
        package_dir = OUT / "packages" / (row["name"].replace("/", "__") + "@" + row["version"])
        if package_dir.exists():
            shutil.rmtree(package_dir)
        package_dir.mkdir(parents=True)
        saved_tar = package_dir / tarball.name
        shutil.copy2(tarball, saved_tar)
        with tarfile.open(tarball, "r:gz") as tf:
            members = tf.getmembers()
            if any(m.issym() or m.islnk() or pathlib.PurePosixPath(m.name).is_absolute() or ".." in pathlib.PurePosixPath(m.name).parts for m in members):
                raise RuntimeError("unsafe tar member")
            tf.extractall(package_dir / "unpacked", filter="data")
        pkg_path = package_dir / "unpacked/package/package.json"
        pkg = json.loads(pkg_path.read_text())
        registry = run("npm", "view", f"{PACKAGE}@{row['version']}", "dist.integrity", "dist.tarball", "--json")
        meta = json.loads(registry)
        report = {
            "package_requested": PACKAGE,
            "npm_pack_command": ["npm", "pack", PACKAGE, "--ignore-scripts", "--json"],
            "name": row["name"], "version": row["version"], "tarball_filename": tarball.name,
            "tarball_sha256": digest, "npm_pack": row,
            "registry": meta, "license": pkg.get("license"), "engines": pkg.get("engines"),
            "package_manager": pkg.get("packageManager"), "bin": pkg.get("bin"),
            "scripts": pkg.get("scripts", {}), "dependencies": pkg.get("dependencies", {}),
            "unpacked_dir": str(package_dir / "unpacked/package"),
            "install_scripts_present": {k: v for k, v in (pkg.get("scripts") or {}).items()
                                        if k in ("preinstall", "install", "postinstall", "prepack", "prepare")},
        }
        (OUT / "omp-pack.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        # A human-readable stable package manifest; source-level recon is appended
        # separately after the unpacked files are reviewed.
        lines = ["# Stock oh-my-pi package manifest", "",
                 f"- requested package: `{PACKAGE}`", f"- resolved package: `{row['name']}@{row['version']}`",
                 f"- tarball SHA-256: `{digest}`", f"- registry integrity: `{meta.get('integrity')}`",
                 f"- registry tarball: `{meta.get('tarball')}`", f"- license: `{pkg.get('license')}`",
                 f"- engines: `{json.dumps(pkg.get('engines'), sort_keys=True)}`",
                 f"- packageManager: `{pkg.get('packageManager')}`", f"- bin: `{json.dumps(pkg.get('bin'), sort_keys=True)}`",
                 f"- install/prepack scripts: `{json.dumps(report['install_scripts_present'], sort_keys=True)}`", "",
                 "Packed with `npm pack oh-my-pi --ignore-scripts --json`; no npm install was run.",
                 f"Unpacked artifact: `{package_dir.relative_to(ROOT)}/unpacked/package`.", ""]
        (OUT / "omp.txt").write_text("\n".join(lines))
        print(OUT / "omp-pack.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # keep a failed registry/package lookup diagnosable
        print(f"recon_omp: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
