# Hashline package review (W2 candidate 3)

Source: `bench/results/2026-10-13/worker-eval-w2/recon/packages/` (npm pack
`--ignore-scripts`; sha256 and registry integrity are in `manifest.json`). pi installed:
0.86.1. This is a source review, not a claim that the upstream package is safe in
other hosts.

## Gate rules

The W2 gate requires imports that resolve from pi, no network/child process/outside-cwd
access beyond the built-ins' edit surface, no runtime dependencies outside pi, and a
license permitting vendoring.

## pi-hashline-edit 0.8.3 — rejected

- `src/grep.ts` imports `child_process` and starts `rg`.
- It needs `diff`, `file-type`, and `xxhashjs`; the latter two are not in pi's tree.
- It adds a grep tool as well as read/edit.
- MIT license is not enough to overcome those failures.

## pi-hashline-context-edit 0.11.0 — chosen exception, patched

The original is MIT (vendored `LICENSE`). It has no `child_process`, network, or fetch
calls; it reads/writes the model-provided path like pi's built-in tools, and expands `~`
through `os.homedir()`. It originally imports pi packages, `@sinclair/typebox`, `diff`,
and `file-type`. Consequently it does **not** pass the dependency gate unmodified.
The advisor approved this particular patched exception. `vendor/PATCH.diff` is the
complete reproducible change record, and must be read with the vendored copy.

The patch makes all of these changes:

1. replaces `file-type` with a local PNG/JPEG/GIF/WebP magic-byte check while retaining
   the null-byte binary check;
2. adds `src/diff-lite.ts` and changes `edit-diff.ts` and `merge.ts` from `diff` to it;
3. changes `@sinclair/typebox` imports to `typebox`, which pi 0.86.1's own
   `submit_request.ts` imports;
4. removes runtime dependencies and package banner/image metadata, and omits the binary
   `assets/banner.png` from the vendored tree.

`diff-lite.ts` is custom correctness-sensitive code, not a documented import rename.
It implements only the required `diffLines` and `diffArrays` API shape: ordered common,
removed, then added parts. It uses LCS below 4,000,000 cells and conservatively treats a
larger middle as one removal plus one addition. Deterministic tests in
`bench/worker_eval/test_w2.py` exercise representative line replacement/insertion and
array replacement operations, plus `threeWayMerge` for disjoint merge and overlap
rejection. They execute the vendored TypeScript with Node's
`--experimental-strip-types`. The smoke run also loaded the patched extension under pi
0.86.1 and tool audit identified its `read` and `edit` source paths.

The extension registers `read` and `edit`, overriding pi's built-ins by name. Pi permits
that, but does not inherit the built-ins' prompt snippets/guidelines. Default reads add
`NNN#HH:` anchors, approximately 4–8 characters (about 1–3 estimated tokens) per line;
`raw: true` is plain text. Its prompt files total about 4.2 KB (~1k estimated tokens).
Those are estimates from source, not performance measurements.

## Verdict

No reviewed package passes the gate unchanged. `pi-hashline-context-edit@0.11.0` is the
advisor-approved exception only while the vendored patch, LICENSE, deterministic tests,
and smoke-load evidence remain present. If it stops loading under pi 0.86.1, omit the
hashline arm.
