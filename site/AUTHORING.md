# Research site

Published to GitHub Pages from `site/` by `.github/workflows/pages.yml` on every push
to `main` that touches `site/`. Three layers, linked automatically by the layout:

```
index.md                          project overview      layer: project
series/<series>/index.md          experiment series     layer: series
series/<series>/<experiment>.md   one experiment        layer: experiment
```

Parents list their children automatically (title, date, status, `tldr`). Their
**summaries are hand-written**, so keeping a parent current is part of every change.

## Front matter

```yaml
layer: experiment            # project | series | experiment
series: memory-evals         # series and experiment pages
order: 2                     # series pages: position on the project page
title: "..."
status: done                 # experiment: planned | running | done; series: active | done
date: 2026-10-11             # experiment: when it ran
updated: 2026-10-11          # last meaningful edit
tldr: One line shown in the parent's list.
summary: |                   # rendered first; <= 200 words (~1 minute)
  ...
```

## Adding or updating an experiment

1. Write or update `series/<series>/<name>.md` and set `updated`.
2. Revise the series page's summary to account for it, and bump its `updated`.
3. Do the same for `index.md` (status, findings, next steps).
4. `python3 tools/check_site.py` must pass. It enforces the word limit and fails if
   any parent's `updated` is older than a child's.

Preview locally: `docker run --rm -p 4000:4000 -v "$PWD/site:/srv/jekyll" jekyll/jekyll jekyll serve`
(then open `http://localhost:4000/bonsai-garden/`).
