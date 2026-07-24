# docs/roadmap

Process artifacts produced during development of this project.

## Version control

This tree is **local-only**: `.gitignore` excludes `docs/roadmap/*`, so specs,
plans, implementation reports, and every review report stay on the machine that
produced them and are never committed.

Exactly four files are tracked — this README and the three workflow templates
the `.claude/commands/` files read:

| Tracked file | Why |
|---|---|
| `docs/roadmap/README.md` | This file — the conventions the workflow commands rely on. |
| `docs/roadmap/spec/spec-template.md` | Structure source for `/new-function-spec`. |
| `docs/roadmap/plan/plan-template.md` | Structure source for `/new-function-spec`. |
| `docs/roadmap/implementation/implementation-template.md` | Structure source for `/imple-spec` reports. |

Keeping the templates tracked is what makes a fresh clone usable:
`/new-function-spec` stops with an explicit "create the template first" message
when `spec-template.md` or `plan-template.md` is missing, and `/imple-spec`
writes its implementation report only while `implementation-template.md` is
present.

Git cannot un-ignore a path inside an excluded directory, so each tracked file
needs its parent directory un-ignored and then re-ignored — see the
`docs/roadmap` block in `.gitignore` before adding another tracked file.

## Subfolders

| Folder | Contents |
|---|---|
| `spec/` | Feature specs — a brief description of *what* a feature should do and why. Written before implementation planning begins. |
| `plan/` | Implementation plans — step-by-step approach for a feature, usually produced from a spec. Includes the files to change and key decisions. |
| `implementation/` | Implementation reports — post-implementation summaries of what was done, what changed, and what was left out. |
| `commands-review/` | Command-file review reports — reviews of `.claude/commands/` files (structure, safety, tool scoping, template quality), e.g. from `/review-command`. |
| `<topic>-review/` | Timestamped project-level review reports from `<topic>-review` commands. One folder per topic, e.g. `architecture-review/`, `security-review/`, `failure-modes-review/`, `test-coverage-review/`. |

## Naming convention

Specs, plans, and implementation reports use a short feature slug, e.g.
`eval-history-delta-reporting.md`.

Project-level `<topic>-review/` reports use a dated, collision-safe filename:
`<YYYY-MM-DD>-<focus-slug>-<topic>-review.md`
(e.g. `2026-06-13-overall-architecture-review.md`) so that multiple reviews can
coexist in the same folder, sort chronologically, and never overwrite prior
reports. Older un-dated files (e.g. `architecture-review.md`) are
pre-convention baselines and can be read as historical context.

`docs/roadmap/<topic>-review/` holds project-level review reports; the separate
`docs/roadmap/commands-review/` holds command-file review reports (e.g. from
`/review-command`).
