# Hashline package review (W2 candidate 3)

Source: `bench/results/2026-10-13/worker-eval-w2/recon/packages/` (npm pack --ignore-scripts, never installed;
sha256 and registry integrity in `manifest.json`). pi installed: 0.86.1. Review is by grep of the unpacked
sources; it is not a line-by-line audit.

## Gate rules (from the W2 spec)
loads with the installed pi (imports resolve to `@earendil-works/*` or need only a documented rename); no network,
child-process or outside-cwd file access beyond editing; no runtime deps outside pi; license allows vendoring.

## pi-hashline-edit 0.8.3 — REJECTED
- `src/grep.ts` imports `child_process` and spawns `rg` (spawn/spawnSync): fails the child-process rule.
- Runtime deps `diff`, `file-type`, `xxhashjs`: `xxhashjs` and `file-type` are not in pi's tree.
- Registers a grep tool as well as read/edit (more surface than the candidate needs).
- MIT.

## pi-hashline-context-edit 0.11.0 — CHOSEN, with a patch
- MIT (`LICENSE` in the tarball) — vendoring allowed; LICENSE is copied next to the vendored source.
- Imports: `@earendil-works/pi-coding-agent`, `@earendil-works/pi-tui`, `@sinclair/typebox` (all pi's), node `fs`,
  `fs/promises`, `path`, `os`, `crypto`, `diff`, `file-type`. No `child_process`, no network call, no `fetch`.
- File access: `path-utils.ts` expands `~` via `os.homedir()` and the tools read/write only the path the model
  passes (the same as pi's built-in read/edit). Not restricted to cwd by the package itself, same as built-ins.
  Env use: only `PI_HASHLINE_DEBUG` (a notify on session_start).
- `diff`: pi bundles `diff` 8.0.4 (`pi-coding-agent/node_modules/diff`); the package asks for ^9. Only
  `Diff.diffLines` (edit-diff.ts:52) and `Diff.diffArrays` (merge.ts:24) are used. To be checked in the smoke run
  that both exist with the same behaviour in 8.0.4, and that the vendored dir resolves `diff` at all (extension
  loaded from the repo, not from pi's tree).
- `file-type`: NOT in pi's tree. Used once (`file-kind.ts:61`) to sniff image/binary MIME from the first 8 KiB.
  The planned PATCH (vendor/PATCH.diff) replaces that call with a small magic-byte check for png/jpeg/gif/webp
  plus the existing null-byte check, so no dependency remains. This is a code change, not a documented rename;
  it is the only change and is stated here. If the patched package fails to load in smoke, there is no hashline arm.
- Tools: registers `read` and `edit` (index.ts), replacing the built-ins by name (to be confirmed against
  pi.txt's registerTool section in the smoke run; the spec asks whether registerTool can replace a built-in).

## Does it change read output, and what does that cost?
Yes. By default every line is returned as `NNN#HH:content` (`hashline.ts:304-308`: right-aligned line number,
`#`, a two-character hash, `:`). That is about 4-8 extra characters per line, roughly 1-3 extra tokens per line
(estimate from the format, not measured). For a 400-line read that is on the order of 400-1000 tokens extra.
`raw: true` returns plain text but then the result can't be used to anchor edits. The read limit stays at pi's
DEFAULT_MAX_LINES / DEFAULT_MAX_BYTES (`read.ts:5-6`), and truncated reads tell the model the `offset` to continue
from (`read.ts:119`). The edit prompt text (`prompts/edit.md`, 2.5 KB) plus read prompt (0.8 KB) are added to the
system prompt: about 4.2 KB of prompt files in total, ~1k tokens. Measured cost belongs to the smoke run.

## Verdict
One package passes the gate conditional on the file-type patch: **pi-hashline-context-edit 0.11.0**. The arm exists
only if the patched copy loads under pi 0.86.1 in the smoke run.
