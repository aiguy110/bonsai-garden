#!/usr/bin/env python3
"""Pack stock oh-my-pi for W2 recon without installing it.

This uses only ``npm view`` and ``npm pack --ignore-scripts``.  It resolves and
checks the canonical coding-agent package before packing its exact name@version,
then stages extraction in /tmp and only moves a verified artifact into recon.
"""
import base64
import binascii
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
PACKAGE = "@oh-my-pi/pi-coding-agent"


def run(*argv, cwd=None):
    p = subprocess.run(argv, cwd=cwd, text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError("%s failed (%s):\n%s\n%s" % (" ".join(argv), p.returncode, p.stdout, p.stderr))
    return p.stdout.strip()


def npm_view(spec):
    value = json.loads(run("npm", "view", spec, "--json"))
    if not isinstance(value, dict):
        raise RuntimeError(f"unexpected npm view output for {spec}: {value!r}")
    return value


def require_canonical(meta):
    """Establish this is the intended OMP CLI, not a similarly named package."""
    if meta.get("name") != PACKAGE or not isinstance(meta.get("version"), str):
        raise RuntimeError(f"registry did not resolve canonical {PACKAGE}: {meta!r}")
    repository = meta.get("repository")
    if not repository:
        raise RuntimeError("canonical package has no repository metadata")
    binary = meta.get("bin")
    if isinstance(binary, str):
        binary = {PACKAGE.rsplit("/", 1)[-1]: binary}
    if not isinstance(binary, dict) or "omp" not in binary:
        raise RuntimeError(f"canonical package does not expose an omp bin: {binary!r}")
    dist = meta.get("dist")
    if not isinstance(dist, dict) or not isinstance(dist.get("integrity"), str) or not dist.get("tarball"):
        raise RuntimeError("canonical package has no dist.integrity/tarball metadata")
    return binary


def verify_integrity(tarball, integrity):
    """Verify npm's SRI before preserving the package."""
    algorithm, sep, encoded = integrity.partition("-")
    if not sep or algorithm != "sha512":
        raise RuntimeError(f"expected sha512 registry integrity, got {integrity!r}")
    try:
        expected = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as e:
        raise RuntimeError(f"malformed registry integrity {integrity!r}") from e
    actual = hashlib.sha512(tarball.read_bytes()).digest()
    if actual != expected:
        raise RuntimeError("packed tarball does not match registry dist.integrity")


def update_manifest(entry):
    path = OUT / "packages" / "manifest.json"
    rows = json.loads(path.read_text()) if path.exists() else []
    if not isinstance(rows, list):
        raise RuntimeError(f"{path} must contain a JSON list")
    if any(isinstance(row, dict) and row.get("name") == entry["name"] and row.get("version") == entry["version"]
           for row in rows):
        raise RuntimeError(f"packages manifest already contains {entry['name']}@{entry['version']}; refusing to replace it")
    rows.append(entry)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rows, indent=2) + "\n")
    tmp.replace(path)


def main():
    # First inspect the canonical registry record, including repository and omp bin.
    canonical = npm_view(PACKAGE)
    canonical_bin = require_canonical(canonical)
    version = canonical["version"]
    resolved = f"{PACKAGE}@{version}"

    with tempfile.TemporaryDirectory(prefix="omp-pack-") as td:
        work = pathlib.Path(td)
        packed = run("npm", "pack", resolved, "--ignore-scripts", "--json", cwd=work)
        rows = json.loads(packed)
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise RuntimeError("unexpected npm pack --json output: " + packed)
        row = rows[0]
        if row.get("name") != PACKAGE or row.get("version") != version:
            raise RuntimeError(f"npm pack resolved {row.get('name')}@{row.get('version')}, expected {resolved}")
        filename = row.get("filename")
        if not isinstance(filename, str) or pathlib.PurePath(filename).name != filename or filename in ("", ".", ".."):
            raise RuntimeError(f"unsafe npm tarball filename: {filename!r}")
        tarball = work / filename
        if not tarball.is_file():
            raise RuntimeError("npm did not create " + str(tarball))

        # Re-query the exact resolved package, then make npm's tarball answer prove
        # it is the registry artifact selected above.
        registry = npm_view(resolved)
        if registry.get("name") != PACKAGE or registry.get("version") != version:
            raise RuntimeError("exact npm view does not agree with canonical resolution")
        require_canonical(registry)
        if registry["dist"] != canonical["dist"]:
            raise RuntimeError("canonical and exact registry dist metadata differ")
        verify_integrity(tarball, registry["dist"]["integrity"])
        if row.get("integrity") and row["integrity"] != registry["dist"]["integrity"]:
            raise RuntimeError("npm pack integrity does not match registry dist.integrity")

        safe_name = PACKAGE.replace("/", "__") + "@" + version
        package_dir = OUT / "packages" / safe_name
        if package_dir.exists():
            raise RuntimeError(f"destination already exists: {package_dir}; refusing to replace recon evidence")

        # All extraction remains in /tmp until metadata, package identity, and SRI
        # have passed.  Reject links/path traversal rather than relying on tarfile.
        stage = work / "stage"
        stage.mkdir()
        shutil.copy2(tarball, stage / filename)
        with tarfile.open(tarball, "r:gz") as tf:
            members = tf.getmembers()
            if any(m.issym() or m.islnk() or pathlib.PurePosixPath(m.name).is_absolute()
                   or ".." in pathlib.PurePosixPath(m.name).parts for m in members):
                raise RuntimeError("unsafe tar member")
            tf.extractall(stage / "unpacked", filter="data")
        pkg_path = stage / "unpacked/package/package.json"
        pkg = json.loads(pkg_path.read_text())
        if pkg.get("name") != PACKAGE or pkg.get("version") != version:
            raise RuntimeError("packed package.json identity differs from registry")
        pkg_bin = pkg.get("bin")
        if isinstance(pkg_bin, str):
            pkg_bin = {PACKAGE.rsplit("/", 1)[-1]: pkg_bin}
        if not isinstance(pkg_bin, dict) or "omp" not in pkg_bin:
            raise RuntimeError("packed package.json has no omp bin")

        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "packages").mkdir(exist_ok=True)
        # The move is deliberately the first persistent package-artifact write.
        shutil.move(str(stage), str(package_dir))

    digest = hashlib.sha256((package_dir / filename).read_bytes()).hexdigest()
    entry = {
        "name": PACKAGE, "version": version,
        "tarball": str((package_dir / filename).relative_to(OUT / "packages")),
        "tarball_sha256": digest,
        "registry_integrity": registry["dist"]["integrity"],
        "registry_tarball": registry["dist"]["tarball"],
        "repository": registry["repository"], "license": pkg.get("license"),
        "engines": pkg.get("engines"), "packageManager": pkg.get("packageManager"),
        "bin": pkg_bin, "scripts": pkg.get("scripts", {}),
        "install_scripts_present": {k: v for k, v in (pkg.get("scripts") or {}).items()
                                    if k in ("preinstall", "install", "postinstall", "prepack", "prepare")},
        "dependencies": pkg.get("dependencies", {}),
        "unpacked_dir": str((package_dir / "unpacked/package").relative_to(OUT / "packages")),
    }
    update_manifest(entry)
    report = {
        "package_requested": PACKAGE, "package_resolved": resolved,
        "npm_pack_command": ["npm", "pack", resolved, "--ignore-scripts", "--json"],
        "canonical_registry": canonical, "exact_registry": registry,
        "npm_pack": row, **entry,
    }
    (OUT / "omp-pack.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    lines = ["# Stock oh-my-pi package manifest", "",
             f"- requested and canonical package: `{PACKAGE}`", f"- resolved package: `{resolved}`",
             f"- repository: `{json.dumps(registry['repository'], sort_keys=True)}`",
             f"- bin (must include omp): `{json.dumps(canonical_bin, sort_keys=True)}`",
             f"- tarball SHA-256: `{digest}`", f"- registry integrity: `{registry['dist']['integrity']}`",
             f"- registry tarball: `{registry['dist']['tarball']}`", f"- license: `{pkg.get('license')}`",
             f"- engines: `{json.dumps(pkg.get('engines'), sort_keys=True)}`",
             f"- packageManager: `{pkg.get('packageManager')}`",
             f"- install/prepack scripts: `{json.dumps(entry['install_scripts_present'], sort_keys=True)}`", "",
             f"Packed with `npm pack {resolved} --ignore-scripts --json`; no npm install was run.",
             f"Unpacked artifact: `{package_dir.relative_to(ROOT)}/unpacked/package`.", ""]
    (OUT / "omp.txt").write_text("\n".join(lines))
    print(OUT / "omp-pack.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # keep a failed registry/package lookup diagnosable
        print(f"recon_omp: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
