# Detailed Workflow

This reference contains the detailed project-specific procedure for the Skill. The Skill metadata and execution boundary in `SKILL.md` remain authoritative.

## Contents

- Documentation Drift Review
- Safety constraints (authoritative)
- Scope and exclusions
- Establish repository reality
- Classify documents before judging drift
- Drift categories to inspect
- Severity, confidence, and fix classification
- Report output
- Report file
- Report structure
- Chat summary
- Procedure

# Documentation Drift Review

Audit two documentation surfaces for drift against current repository reality —
code, directory structure, architecture, capabilities, configuration, commands,
versions, test organization, and validation status that changed without the
corresponding documentation being updated:

- the repository's tracked, active **Markdown documentation**; and
- **embedded documentation prose** inside tracked source/config files.

**Embedded documentation prose** means the documentation-like text carried inside
non-Markdown source and configuration files, including:

- Python module / class / function docstrings;
- TypeScript / TSX documentation comments and explanatory blocks;
- long explanatory comments (comment blocks that describe behavior, architecture,
  or rationale, not one-line implementation notes);
- user-facing constants and unsupported-intent / help messages;
- API descriptions, UI copy, and frontend help text that describe supported behavior;
- HTML metadata or other embedded user-facing descriptions;
- CLI help text;
- prompt / template prose;
- long string blocks that describe current architecture, capabilities, commands,
  config, tests, model behavior, feature flags, or user-facing behavior.

Keep this narrow and conservative:

- **Short implementation comments should not be reported** unless they make a
  materially misleading current-behavior claim.
- **Historical or local rationale comments should not be modernized** merely
  because the architecture later evolved.

The source/config files are **not** audited for code correctness — only their
embedded documentation prose is reviewed for drift.

This is a **review-only command with one narrowly scoped output**: you may create
exactly one detailed timestamped report under `docs/roadmap/docs-drift-review/`
and nothing else.

Optional scope supplied by the user:

    the user's skill input

When `the user's skill input` is empty, review the full repository. When it names a file,
directory, module, or drift category, narrow the review to that scope while still
inspecting enough repository evidence to validate the claims within it.

---

## Safety constraints (authoritative)

These rules apply to the entire command. They are stated once here and are not
repeated elsewhere.

- Do not modify any existing repository file.
- Do not apply documentation fixes and do not create a repair patch.
- The only file you may create is one new report under
  `docs/roadmap/docs-drift-review/` (see "Report output").
- Do not stage, revert, discard, commit, or push any change.
- Do not create or switch branches.
- Preserve all pre-existing working-tree changes exactly as they are.
- Do not read `.env` and do not expose secret values. Use `.env.example`, source
  code, configuration code, and documented variable names as evidence.
- Do not run real-model tests, gated integration tests, full evals, or
  provider-backed ingestion.
- Do not install frontend dependencies, run a frontend build, or start the API
  server. Frontend and server claims are verified statically from source,
  `frontend/package.json`, and CI.
- Do not make external network or provider calls (OpenAI, Tavily, Chroma,
  LangSmith, or any other). Do not access external URLs.
- Never scan `.agents/skills/**` or local `docs/roadmap/**` artifacts (see
  "Scope and exclusions"). The three tracked `docs/roadmap/` workflow files
  (`docs/roadmap/README.md`, `docs/roadmap/spec/spec-template.md`, and
  `docs/roadmap/implementation/implementation-template.md`) are the sole
  exception: they are version-controlled active documentation and **are**
  audited.
  `docs/roadmap/docs-drift-review/` is an output location only, not an audit input.

This Skill remains review-only even when clear drift is found.

---

## Scope and exclusions

Audit **tracked active Markdown and embedded documentation prose in tracked
source/config files**. The current working tree is the documentation reality being
checked — including intentional uncommitted changes. Do not treat an uncommitted
path as stale merely because it differs from `HEAD`.

Build **two** inventories from files tracked by Git, both excluding
`.agents/skills/**` and all local `docs/roadmap/**` artifacts (specs, plans,
implementation reports, and review artifacts) — **except** the three tracked
`docs/roadmap/` workflow files, which are active documentation and are audited.

Markdown inventory (the blanket `docs/roadmap/**` exclusion drops the local
artifacts; the second `git ls-files` additively re-includes exactly the three
tracked workflow files, and returns each only while it is tracked):

    git ls-files "*.md" \
      ":(exclude).agents/skills/**" \
      ":(exclude)docs/roadmap/**"

    git ls-files \
      "docs/roadmap/README.md" \
      "docs/roadmap/spec/spec-template.md" \
      "docs/roadmap/implementation/implementation-template.md"

Embedded-prose source/config inventory:

    git ls-files \
      "graph/*.py" \
      "graph/**/*.py" \
      "server/*.py" \
      "server/**/*.py" \
      "main.py" \
      "ingestion.py" \
      "evals/*.py" \
      "evals/**/*.py" \
      "tests/*.py" \
      "tests/**/*.py" \
      "tests/server/*.py" \
      "tests/server/**/*.py" \
      "frontend/src/*.ts" \
      "frontend/src/*.tsx" \
      "frontend/src/**/*.ts" \
      "frontend/src/**/*.tsx" \
      "frontend/package.json" \
      "frontend/vite.config.ts" \
      "frontend/tsconfig.json" \
      "frontend/index.html" \
      "pyproject.toml" \
      ".github/workflows/*.yml" \
      ".github/workflows/*.yaml" \
      ":(exclude).agents/skills/**" \
      ":(exclude)docs/roadmap/**"

The source/config files in the second inventory are **not** audited for all code
correctness — inspect only their embedded documentation prose (docstrings, long
explanatory comments, TypeScript/TSX documentation comments, user-facing
constants/messages, API descriptions, UI/help copy, HTML metadata, CLI help text,
prompt/template prose, and long descriptive string blocks) for drift.

**Always read in full (do not rely only on search matches) the package-level
`__init__.py` of every audited source package** (for this repository:
`graph/__init__.py`, `graph/nodes/__init__.py`, `graph/chains/__init__.py`, and
`server/__init__.py`). Their module/package docstrings are prime
prose-drift surfaces — they often summarize the
package's capabilities, version status, and architecture, and drift silently when the
code around them evolves.

**Excluded audit input (never scanned):**

| Path | Why excluded |
|---|---|
| `.agents/skills/**` | Command definitions, including this file — not project documentation. |
| `docs/roadmap/**` local artifacts | Temporary plans, local review artifacts, and process documents — not active documentation. Includes this Skill's own report directory. **Excludes the three tracked workflow files below, which are audited.** |

**Audited despite living under `docs/roadmap/` (tracked active documentation):**

| Path | Why audited |
|---|---|
| `docs/roadmap/README.md` | Version-controlled; documents the roadmap version-control policy and conventions. |
| `docs/roadmap/spec/spec-template.md` | Version-controlled workflow template the `.agents/skills/` files depend on. |
| `docs/roadmap/implementation/implementation-template.md` | Version-controlled workflow template the `.agents/skills/` files depend on. |

**Allowed output location (not audit input):**

| Path | Role |
|---|---|
| `docs/roadmap/docs-drift-review/<report>.md` | The single report this Skill may create. |

Do not recursively scan untracked dependency, virtual-environment, cache,
generated, or build directories.

Unless `the user's skill input` narrows the scope, review all tracked Markdown and all
embedded documentation prose in the tracked source/config inventory outside the
excluded directories. Record: number of Markdown files discovered and number
actually reviewed; number of embedded-prose source/config files discovered and
number actually reviewed; files excluded by scope; and the exclusion rule used.

---

## Establish repository reality

Documentation claims must be checked against repository evidence — never against
memory or naming alone. Inspect the relevant current sources of truth as
applicable:

- top-level tree, tracked files, source package layout;
- `graph/`, `server/`, `frontend/`, `evals/`, `tests/`, and top-level entry points;
- `.github/workflows/`, `pyproject.toml`, `.env.example`,
  `frontend/package.json`, Vite and TypeScript configuration;
- graph routing, engine/state, nodes/chains, and retrieval/web-search boundaries;
- the server import boundary, FastAPI status/run/document endpoints, request/response
  schemas, cancellation, HTTP error mapping, URL/config/status sanitization, and API
  contracts;
- frontend pages/components, API clients, mirrored TypeScript types and field parity,
  URL safety, error/status display, cancellation UI, colocated tests, static serving,
  proxy configuration, and typecheck/Vitest/Vite build descriptions;
- feature flags, model factory / configuration code, test markers, CI
  exclusions, active scripts;
- `README` files, the ADR index, ADR status and supersession metadata.

Every reported drift item must cite concrete evidence: an existing/missing path,
a tracked filename, a function/class/constant/enum/schema field, a CI command, a
config value, an import, a current test location, a feature flag, an active model
name, a router capability, a test marker, or a superseding ADR. When evidence is
ambiguous, classify the finding as **maintainer review required**, not confirmed
drift.

---

## Classify documents before judging drift

Do not apply the same freshness rules to every file. Local roadmap artifacts
(specs, plans, implementation reports, review artifacts) are out of scope entirely
(excluded above) and are **not** a review category. The three tracked roadmap
workflow files are the exception: audit them as Category A active documentation.

| Category | Examples | Drift rule |
|---|---|---|
| **A. Active / current** | `README.md`, `AGENTS.md`, `structure.md`, module READMEs, `evals/README.md`, and the three tracked roadmap workflow files (`docs/roadmap/README.md`, `docs/roadmap/spec/spec-template.md`, `docs/roadmap/implementation/implementation-template.md`) | Expected to describe current reality. Inaccurate current claims are drift. |
| **B. Historical decision records** | `docs/adr/**` | Preserve what was true when decided. Flag only: broken link; history presented as current; stale current-status/implementation-note section; wrong supersession reference; missing/incorrect supersession metadata; an objective typo or impossible path already wrong at the time. |
| **C. Release notes / version snapshots** | Dated validation reports and other explicitly versioned snapshots | Old versions/paths/totals may be correct history. Flag only: claims to describe the *current* version; broken current navigation link; a command presented as currently runnable that no longer works; contradictory version relationship; stale current-status section; a pointer to an active doc via an obsolete path. |
| **D. Generated results / eval reports** | tracked eval or benchmark output Markdown | Treat measured values as point-in-time unless they claim to be current. Check links, headings, scope descriptions, runner/dataset paths, and obvious contradictions. Do not rewrite measured values by inference. |
| **E. Embedded documentation prose** | Python docstrings, TypeScript/TSX documentation comments, long explanatory comments, user-facing constants, API descriptions, UI/help copy, HTML metadata, CLI help text, prompt/template strings | Treat as current documentation when it describes current behavior, capabilities, architecture, commands, config, tests, model/LLM usage, feature flags, paths, API contracts, or user-facing output. Do not modernize short local implementation comments or clearly historical rationale unless they materially mislead maintainers. |

For categories B-D, do not modernize historical bodies (Decision/Context/Rationale/
Consequences, dated benchmarks, archived facts, or clearly historical rationale
comments) merely because the repository later evolved.

---

## Drift categories to inspect

Cover at least these, judging active documentation against the evidence above and
distinguishing active claims from valid historical records.

1. **Paths and structure** — Markdown references to paths that no longer exist,
   were renamed/moved, use obsolete singular/plural names, point to the wrong
   module, describe an old test/eval layout, or describe a tree that no longer
   matches the repository. Evidence: `git ls-files`, path-existence checks,
   current imports and module boundaries.
2. **Markdown links** (active docs) — broken local file links, verifiable broken
   anchors, wrong relative depth, links to renamed/moved files, navigation
   indexes that omit current documents or point to obsolete ones. Do not access
   external URLs; report an external link only when its visible label or local
   context is internally contradictory.
3. **Commands and workflows** — documented `pytest` / eval-runner / script /
   `ruff` / `mypy` / `uv` / npm / TypeScript / Vitest / Vite / CI / server-start /
   entry-point / setup commands that reference
   missing paths, invoke renamed files, unintentionally include gated real-model
   tests, omit required exclusions, contradict current CI, use obsolete flags,
   claim to be keys-free while reaching a provider, describe a gated full eval as
   safe/free, or use an old test/eval path or dataset/runner filename. Establish
   correctness statically from paths, config, markers, imports, and CI — do not
   execute the commands.
4. **Architecture and module boundaries** — active claims about graph routing,
   grading, engines, state, nodes/chains, retrieval and web-search boundaries,
   the server import boundary, FastAPI status/run/document endpoints and schemas,
   HTTP error mapping and sanitization, frontend/backend layering, frontend pages,
   API clients and mirrored TypeScript types, URL safety, error/status display,
   cancellation UI, static serving, proxy configuration, eval/test ownership,
   dependencies, entry points, import direction, and fallback behavior. Verify
   against implementation; do not infer drift from naming.
5. **Capabilities and features** — current claims about LangGraph routing and
   grading, the effective `web_search_enabled` value, retrieval, web search,
   generation, graders, query rewriting, retry/budget limits, `GraphState` and
   terminal `stop_reason` values, privacy/local-provider locks, fully local mode,
   ingestion/index versioning and embedding fingerprints, FastAPI endpoints and
   sanitization, frontend pages and API type mirrors, cancellation, and fallback
   behavior. Verify against current graph, config, engine, state, nodes, chains,
   ingestion, server, and frontend implementation. Preserve historical ADRs.
6. **Models, config, environment** — model names, temperature, provider
   dependencies, env-variable names, defaults, feature flags, retry/budget
   config, optional vs. mandatory keys, keys-free commands, gated-test / real-model
   eval requirements. Verify against source, `.env.example`, and config code; do
   not print secrets.
7. **Tests, evals, CI** — test/eval directory locations, root-level and recursive
   Python tests (including `tests/server/`), colocated frontend tests, mocked vs.
   real-model suites, gated markers, CI scope, typecheck/Vitest/Vite commands,
   runner/dataset/report locations, module ownership, eval/ADR historical status,
   and whether real-model suites are excluded by directory vs. only by missing
   keys. Verify against the current `tests/`, `frontend/`, and `evals/` trees, CI
   workflows, pytest markers, and `tests/conftest.py`.
8. **Versions and release status** — current release/version/milestone claims and
   version labels in active README headings. Report conflicting current-version
   claims, active docs pinned to an obsolete release without reason, "latest"
   claims contradicted by newer records, and version labels that freeze evergreen
   docs. Do not flag old numbers inside historical release notes.
9. **Test counts and validation totals** — fixed claims like `592 passed`,
   `817 collected`, exact file counts, "all tests pass", or current validation
   dates. Decide whether each is a dated/versioned historical snapshot, an active
   current-status claim, or an undated number likely to drift. Do not invent
   replacement totals; prefer removing, dating, or qualifying fragile ones.
10. **Cross-document contradictions** — active-vs-active conflicts (e.g. a default
    is documented as an absolute privacy lock; backend schemas and frontend type
    mirrors disagree; a command includes chain integration tests CI excludes). Do
    not treat a correctly historical/superseded ADR as contradicting a current
    README.
11. **Terminology / semantic drift** — wording that materially misleads a
    maintainer: "case" vs. "check" when semantics differ, "unit test" for a gated
    integration test, "eval" for a test of an eval harness, "deterministic"
    applied to an LLM-backed path, "current" for a historical snapshot,
    "complete/fully supported" contradicted by implementation, a cancellation path
    described with the wrong `stop_reason`, or "keys-free" for a command that can
    reach a provider.
12. **Embedded documentation prose drift** — Python docstrings, TypeScript/TSX
    documentation comments, long comments, user-facing constants, API descriptions,
    UI/help copy, HTML metadata, CLI help text, and prompt/template prose that
    describe current behavior, capabilities, paths, tests, feature flags, LLM
    usage, model names, version status, API contracts, or user-facing output. Verify
    against current implementation. Do not flag short local comments
    unless they materially mislead maintainers, and do not modernize clearly
    historical rationale merely because the architecture later evolved.

**Avoid false positives.** Do not report drift merely because an ADR describes an
older architecture, a release note holds an old version, a result file holds an
old total, or a document explicitly labels a statement as historical, superseded,
or a point-in-time snapshot. Avoid broad search-and-replace recommendations; weigh
document category and sentence context. A smaller evidence-backed report beats a
large speculative one.

---

## Severity, confidence, and fix classification

Assign every finding one severity, one confidence, and one fix classification.

**Severity**

| Level | Meaning |
|---|---|
| `BLOCKING` | A documented command/path/procedure is actively unsafe or unusable (e.g. a keys-free command runs a gated real-model suite; a required setup command points to a nonexistent file; a "safe" command can incur provider cost). |
| `HIGH` | Current architecture, security, capability, or runtime behavior is materially misdescribed. |
| `MEDIUM` | A current version, config, test-status, ownership, workflow, or validation statement is stale or likely to mislead. |
| `LOW` | Minor terminology, heading, navigation, or consistency drift. |
| `HISTORICAL / NO CHANGE` | Old by design; a valid historical record that should stay unchanged. |

**Confidence:** `HIGH` (directly proven by evidence) / `MEDIUM` (strong evidence,
interpretation involved) / `LOW` (plausible, needs maintainer confirmation).

**Fix classification:** `SAFE TO FIX` (mechanical: broken path, moved test
command, wrong tree, obsolete active link, stale filename) / `REVIEW BEFORE
FIXING` (architectural statement, current-version claim, security wording,
validation totals, prompt/model/config docs, ADR implementation note, roadmap
reinterpretation) / `DO NOT CHANGE` (correct historical ADR text, version-specific
release facts, dated benchmark/eval output, accurate migration-history reference).

This Skill must not apply any fix regardless of classification.

---

## Report output

Produce two outputs: a concise chat summary and one detailed report file.

### Report file

Before the first report write, determine the authoritative date and time by
running this command exactly once:

    powershell.exe -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'"

Treat the returned timestamp as the only authoritative current local time, and
reuse that same value throughout this run. Use its `YYYY-MM-DD` portion
consistently for the report filename and any date/timestamp text in the report
body. Never infer or guess the date from model knowledge, conversation history,
Git history, existing reports, or existing filenames, and never copy the date
from an existing report. If the command fails, stop and report the failure; do
not write a report with a guessed date.

Write the complete report under `docs/roadmap/docs-drift-review/`, creating the
directory if needed. Name it using the project's review-skill convention:

    docs/roadmap/docs-drift-review/<YYYY-MM-DD>-<focus-slug>-docs-drift-review.md

- `<YYYY-MM-DD>` — the verified date from the command above. No time component.
- `<focus-slug>` — `overall` when `the user's skill input` is empty; otherwise a concise
  lowercase kebab-case slug from `the user's skill input` (trim, spaces to hyphens, remove
  quotes and filename-unsafe characters, no path separators, keep it short). If
  sanitizing produces an empty slug, use `overall`.

Examples:

- full repository — `docs/roadmap/docs-drift-review/2026-07-06-overall-docs-drift-review.md`
- scoped — `docs/roadmap/docs-drift-review/2026-07-06-graph-routing-docs-drift-review.md`

**Collision handling.** Before writing, select the path by checking candidates in
order, checking each path and using the first that does not already exist:

1. `<YYYY-MM-DD>-<focus-slug>-docs-drift-review.md`
2. `<YYYY-MM-DD>-<focus-slug>-docs-drift-review-2.md`
3. `<YYYY-MM-DD>-<focus-slug>-docs-drift-review-3.md`
4. continue incrementing the numeric suffix until an unused path is found.

Never overwrite or modify an earlier report. The report file is the only file
this Skill may create.

If the report cannot be written, stop and report the failure in chat. Do not
silently substitute a chat-only full report.

### Report structure

Write the detailed report using this structure:

    # Documentation Drift Review

    ## Report metadata
    Timestamp; requested scope; report path; repository root; Markdown and
    embedded-prose discovery rules; exclusions (`.agents/skills/**` and local
    `docs/roadmap/**` artifacts, noting the three tracked roadmap workflow files
    are audited as active documentation); Markdown files discovered; Markdown
    files reviewed;
    embedded-prose source/config files discovered; embedded-prose source/config
    files reviewed, split into **read in depth** vs. **search-triaged** (located but
    not read in full); files excluded by scope and exclusion rule; relevant
    working-tree state; confirmation no existing file was modified; note that this
    report is a point-in-time artifact.

    ## Executive summary
    Counts for: confirmed drift; possible drift; broken local links; stale
    commands/paths; architecture/capability mismatches; version/validation
    mismatches; historical references intentionally preserved. State whether active
    documentation is broadly healthy / moderately drifted / significantly drifted.

    ## Confirmed drift
    For each finding:
    ### `[SEVERITY] Short title`
    - File / Location (heading, line, or nearby text)
    - Confidence / Fix classification
    - Current documentation says (short quote or faithful paraphrase)
    - Repository reality
    - Evidence (exact path/code/config/CI/import/test)
    - Why this is drift
    - Recommended correction
    - Related files that should stay consistent

    ## Possible drift — maintainer decision required
    Same fields, plus what evidence is missing, why interpretation is required, and
    what decision is needed (e.g. undated totals, unclear current version, a
    could-be-historical statement, ambiguous ownership).

    ## Broken or stale links and commands
    | Severity | File | Link or command | Problem | Recommended target |
    Include only evidence-backed failures.

    ## Cross-document inconsistencies
    | Topic | Document A | Document B | Repository evidence | Recommendation |
    Exclude expected differences between current docs and valid historical records.

    ## Historical references preserved
    Reviewed historical statements that look stale but must not change; for each:
    file; old path/version/capability/command; why it is historically valid;
    whether a current implementation note or navigation link still needs review.

    ## Suggested repair order
    1. Safe mechanical fixes  2. Architecture/workflow corrections
    3. Version/validation-status decisions  4. Historical clarifications (only when
    needed). Do not perform the repairs.

    ## Files reviewed with no material drift
    Important active documents/prose surfaces that were **read in depth** and found
    consistent. List a surface here only if it was actually read — never on the basis
    of search triage alone. Track search-only-triaged files separately (e.g. in report
    metadata) so their status is not overstated as verified drift-free.

    ## Final verdict
    Overall drift risk; any blocking item; whether a repair pass is recommended;
    whether active documentation is trustworthy for onboarding/maintenance; and
    confirmations that this was review-only, that `.agents/skills/**` and local
    `docs/roadmap/**` artifacts were excluded (the three tracked roadmap workflow
    files audited as active documentation), that no existing file was modified,
    that no repair was applied, and that no external calls, real-model tests, or
    full evals ran.

Cite evidence for every confirmed finding; do not quote long passages.

### Chat summary

Keep the chat response concise — do not paste the full report or long evidence
excerpts unless the user asks. Use this structure:

    # Documentation Drift Review — Summary

    - **Scope:** ...
    - **Markdown files scanned:** N
    - **Embedded-prose source/config files scanned:** N
    - **Confirmed drift:** N
    - **Possible drift:** N
    - **Broken links / stale commands:** N
    - **Blocking findings:** yes / no
    - **Detailed report:** `docs/roadmap/docs-drift-review/<YYYY-MM-DD>-<focus-slug>-docs-drift-review.md`

    ## Highest-priority findings
    Up to five, as `[SEVERITY] path/to/file.md — short explanation`. If none:
    "No material documentation drift was confirmed."

    ## Verdict
    Active documentation is broadly healthy / moderately drifted / significantly
    drifted. Confirm in one paragraph: no repair applied; no existing file
    modified; only the new report created; `.agents/skills/**` and local
    `docs/roadmap/**` artifacts excluded (three tracked roadmap workflow files
    audited); no external calls, real-model tests, or full evals run.

---

## Procedure

1. Read `AGENTS.md`. Run `git status --short` and record the initial working-tree
   state.
2. Build both inventories — the tracked-Markdown inventory and the tracked
   source/config embedded-prose inventory — excluding `.agents/skills/**` and
   local `docs/roadmap/**` artifacts, but additively including the three tracked
   roadmap workflow files in the Markdown inventory as active documentation. Apply
   `the user's skill input` scope when provided.
3. Classify reviewed documents and prose (active / historical ADR / release /
   generated / embedded documentation prose).
4. Inspect current repository structure, config, CI, tests, evals, entry points,
   and relevant implementation.
5. Search Markdown and embedded documentation prose for high-risk claims: paths,
   shell commands, capability counts, model names, feature flags, env variables,
   version labels, test totals, and words like "current", "latest", "complete",
   "only", "all", "fully supported". Also search for high-risk **stale-version /
   stale-status** terms that frequently outlive the code that justified them:
    `Phase 1`, `Phase 2`, `will be added`, `local retrieval only`, `unlimited
    retries`, `raw trace`, `current`, `latest` (verify each hit against the
   present implementation, and weigh document category — a term inside a valid
   historical ADR or a labeled release snapshot is not automatically drift). For
   source/config files, review only the embedded documentation prose (docstrings,
   long comments, user-facing constants / messages, CLI help text, prompt/template
   strings), not code correctness. To keep the large source/config inventory
   affordable, triage with targeted text search first — locate prose-dense regions
   (module/class/function docstrings, user-facing constants / messages, CLI help
   text, prompt/template strings, and long descriptive string blocks) rather than
   reading whole source files, and do not read assertion-heavy test files wholesale;
   inspect only the prose-dense regions surfaced by search. Always read each audited
   source package's package-level `__init__.py` **in full**, not merely its search
   matches. **Search triage is a locator, not verification:** do not report a prose
   surface as accurate / drift-free on the basis of a search hit or miss alone
   — a surface may only be called drift-free after it was actually read in depth.
6. Validate each candidate against evidence; separate confirmed drift, possible
   drift, preserved historical references, and healthy documentation.
7. Select the collision-safe report path with path-existence checks and write exactly one new
   report.
8. Run `git status --short` again and confirm the only new change is the report
   file; preserve all pre-existing changes.
9. Return only the concise chat summary.
