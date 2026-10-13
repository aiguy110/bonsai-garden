#!/usr/bin/env python3
"""Check the research site's structure before it is built.

  python3 tools/check_site.py [site_dir]

Fails (exit 1) when:
- a page lacks a required front-matter field for its layer;
- a summary is over MAX_WORDS (about one minute of reading);
- an experiment names a series that has no series page;
- a parent is older than its newest child: the project page's `updated` must be
  >= every series' `updated`, and each series' >= its experiments'. Updating a
  child therefore forces the summaries above it to be revisited.
"""
import pathlib
import re
import sys

import yaml

MAX_WORDS = 200
REQUIRED = {
    "project": ["title", "updated", "tldr", "summary"],
    "series": ["title", "series", "order", "status", "updated", "tldr", "summary"],
    "experiment": ["title", "series", "status", "date", "updated", "tldr", "summary"],
}

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "site")
pages = []
for f in sorted(root.rglob("*.md")):
    if any(part.startswith("_") for part in f.relative_to(root).parts) or f.name == "AUTHORING.md":
        continue
    m = re.match(r"---\n(.*?)\n---\n", f.read_text(), re.S)
    if not m:
        continue
    fm = yaml.safe_load(m.group(1)) or {}
    if "layer" in fm:
        pages.append((f.relative_to(root), fm))

errors = []
for f, fm in pages:
    layer = fm["layer"]
    if layer not in REQUIRED:
        errors.append(f"{f}: unknown layer {layer!r}")
        continue
    for k in REQUIRED[layer]:
        if fm.get(k) in (None, ""):
            errors.append(f"{f}: missing {k}")
    words = len(re.findall(r"\S+", str(fm.get("summary", ""))))
    if words > MAX_WORDS:
        errors.append(f"{f}: summary is {words} words (max {MAX_WORDS}, ~1 min)")

projects = [p for p in pages if p[1]["layer"] == "project"]
series = {fm.get("series"): (f, fm) for f, fm in pages if fm["layer"] == "series"}
experiments = [p for p in pages if p[1]["layer"] == "experiment"]
if len(projects) != 1:
    errors.append(f"expected exactly one project page, found {len(projects)}")


def stale(parent, child):
    (pf, pfm), (cf, cfm) = parent, child
    if pfm.get("updated") and cfm.get("updated") and pfm["updated"] < cfm["updated"]:
        errors.append(f"{pf}: updated {pfm['updated']} is older than child {cf} ({cfm['updated']}); "
                      "revisit its summary and bump `updated`")


for e in experiments:
    s = series.get(e[1].get("series"))
    if s is None:
        errors.append(f"{e[0]}: series {e[1].get('series')!r} has no series page")
    else:
        stale(s, e)
for s in series.values():
    for p in projects:
        stale(p, s)

for e in errors:
    print("ERROR", e)
print(f"{len(pages)} pages checked, {len(errors)} errors")
sys.exit(1 if errors else 0)
