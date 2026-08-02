# Detailed Workflow

This reference contains the detailed project-specific procedure for the Skill. The Skill metadata and execution boundary in `SKILL.md` remain authoritative.

## Contents

- Intended workflow
- Required locations
- Step 0. Validate input
- Step 1. Minimal project context
- Step 2. Check working tree
- Step 3. Parse the user input
- feature_title
- feature_slug
- Step 4. Project-grounded inspection
- Optional LangChain Docs MCP documentation check
- Step 5. Existing-file protection
- Step 6. Create the function spec
- <feature_title>
- Default safety and scope constraints for the generated document
- Validation plan for the generated document
- Recommended implementation invocation
- Safety rules for this Skill
- Step 7. Quality self-check
- Step 8. Final response

You are creating a single implementation-ready **function spec** for this Agentic RAG project.

User input: the user's skill input

Create a function spec only. Do not implement the feature.

This Skill produces one implementation-ready function spec that can be passed
directly to
``$imple-spec`` — it must **not** create a separate plan file.

Use as few tools as possible.

Do not create or switch git branches.

Do not commit automatically.

## Intended workflow

```text
$new-function-spec <short feature description>
-> review the generated function spec
-> $imple-spec docs/roadmap/spec/<feature-slug>.md
```

## Required locations

Spec files live under:

`docs/roadmap/spec/`

Spec template (structure source):

`docs/roadmap/spec/spec-template.md`

Generated function spec:

`docs/roadmap/spec/<feature_slug>.md`

## Step 0. Validate input

If `the user's skill input` is empty, stop before reading any files and ask the user for a
short feature description:

`Please provide a short feature description.`

## Step 1. Minimal project context

Read only these files first:

* `AGENTS.md`
* `docs/roadmap/spec/spec-template.md`

The spec template is the **structure source** for the generated document. Do
not modify it.

If `docs/roadmap/spec/spec-template.md` does not exist, stop and tell the user:

`Missing docs/roadmap/spec/spec-template.md. Please create the spec template first.`

Do not invent a replacement template.

## Step 2. Check working tree

Run:

```powershell
git status --short
```

If the working tree has unrelated uncommitted changes, warn the user.

It is okay to create the new function spec only if doing so will not overwrite or
interfere with unrelated work, and only under:

`docs/roadmap/spec/`

Do not modify application files.

## Step 3. Parse the user input

From `the user's skill input`, infer:

### feature_title

A short human-readable title in Title Case.

Example:

`Source Citation Deduplication`

### feature_slug

A safe filename slug.

Rules:

* Lowercase.
* Kebab-case.
* Only `a-z`, `0-9`, and `-`.
* Replace spaces and punctuation with `-`.
* Collapse multiple `-` into one.
* Trim `-` from the start and end.
* Maximum length: 40 characters.

Example:

`source-citation-deduplication`

If you cannot infer a sensible title and slug, ask the user to clarify instead of
guessing.

## Step 4. Project-grounded inspection

After reading the required files, inspect **only the directly relevant** project
files needed to understand and plan the requested feature, so the generated
document is grounded in the real repository.

* Prefer the spec template and `AGENTS.md` for structure and rules.
* Use targeted text searches, file listings, and focused reads to verify real filenames,
  entry points, schemas, tests, and conventions before naming them in the document.
* When the feature touches `server/`, `frontend/`, or their public contract, inspect
  the directly coupled files and tests. Verify `server/schemas.py` against
  `frontend/src/api/types.ts`, API routes against `frontend/src/api/client.ts`, and
  FastAPI static serving against the Vite build. Include `tests/server/` and
  co-located frontend tests in the proposed scope when relevant; do not inspect
  generated `frontend/dist/` contents.
* When the feature changes a documented architectural decision, identify the
  correct ADR to update, or the **next available ADR number**, from the current
  repository state under `docs/adr/` — do not rely on stale ADR ranges or numbers
  from older reports.

Do not perform a broad repository or architecture review unless the requested
feature genuinely requires it.

Do not read unrelated files unless needed to plan the change safely.

Do not invent filenames, APIs, schemas, environment variables, model names, test
directories, or architectural contracts without verifying them in the repository.

## Optional LangChain Docs MCP documentation check

This step is conditional. Use it only when the requested feature depends on
**current external** LangChain ecosystem behavior — for example LangChain,
LangGraph, LangSmith, LangChain retrievers, tools, document loaders, vector
stores, OpenAI/Chroma/Tavily integration through LangChain, `langchain-mcp-adapters`,
or MCP-related LangChain integration behavior. When it applies, consult the
installed LangChain Docs MCP server (the configured `docs-langchain` MCP search tool
/ the configured `docs-langchain` MCP filesystem-docs tool).

* Keep the documentation query narrow and tied to the requested feature.
* Do not paste large documentation dumps into the document. Summarize only the
  relevant API assumptions, constraints, or version-sensitive behavior.
* If the LangChain Docs MCP server is unavailable, errors, or returns no relevant
  docs, continue without blocking and note that external docs were unavailable or
  not consulted.
* Do not use the LangChain Docs MCP server for project-local rules already covered
  by `AGENTS.md`, source code, tests, evals, ADRs, roadmap documents, existing
  specs, or implementation reports. Project-local sources remain authoritative and
  must not be overridden by external documentation.

If—and only if—you consulted the LangChain Docs MCP server, add a small note in
the most appropriate existing section of the generated document, such as:

`External docs consulted: LangChain Docs MCP, <library/topic>`

Do not add a large new section, do not dump raw MCP output, and do not mention the
LangChain Docs MCP server in the document if it was not used.

## Step 5. Existing-file protection

Before writing, check whether the target function spec already exists by checking this
path:

`docs/roadmap/spec/<feature_slug>.md`

If that file already exists, do not overwrite it. Stop and ask the user whether to:

* revise the existing function spec at that path, or
* create a new function spec under a different `feature_slug`.

Do not silently overwrite an existing function spec.

## Step 6. Create the function spec

Before writing the spec, determine the authoritative date and time by running
this command exactly once:

    powershell.exe -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'"

Treat the returned timestamp as the only authoritative current local time, and
use its `YYYY-MM-DD` portion for the `Date:` field in the document header below.
Never infer or guess the date from model knowledge, conversation history, Git
history, existing specs, or existing filenames, and never copy the date from an
existing spec. If the command fails, stop and report the failure; do not write
the spec with a guessed date.

Only once the target path is confirmed unused (or the user explicitly chooses a
path), create the directory if needed:

`docs/roadmap/spec/`

Then create exactly one file:

`docs/roadmap/spec/<feature_slug>.md`

Use the spec template as the structural baseline and the requirements below to
create one non-repetitive, implementation-ready document. Do not create a
separate plan file.

Label the document header:

```text
# <feature_title>

Status: Draft

Date: <YYYY-MM-DD>

Type: Function Spec
```

The document must contain these sections, in order:

1. Title, status, date, and type (the header above).
2. Summary.
3. Background and current behavior.
4. Goals.
5. Non-goals.
6. Current system understanding (only what was verified from project files).
7. Files to inspect during implementation (split into **Required files** and
   **Optional files**).
8. Proposed architecture and behavioral changes.
9. Detailed implementation steps — small, ordered, and specific enough to execute
   without writing a further plan. Each step should note its goal, the files it
   likely changes, what to avoid, and any per-step validation.
10. Expected files to change.
11. Files that must not change (protected files).
12. Safety and scope constraints (see the default constraints below).
13. Validation and testing plan (keys-free, per-suite commands — see below).
14. Acceptance criteria (measurable).
15. Risks and calibration notes.
16. Recommended implementation invocation.
17. Final implementation report format.

The document must clearly distinguish:

* required behavior vs. optional behavior vs. non-goals,
* existing contracts that must remain unchanged,
* files expected to change vs. files explicitly protected,
* safe, keys-free validation vs. commands requiring separate user approval.

### Default safety and scope constraints for the generated document

Include these (each holds unless the feature explicitly approves an exception):

* Do not change prompts, model names, or corpus documents.
* Do not change graph behavior, graph routing, or graph nodes.
* Do not change `stop_reason` semantics or fallback policy semantics.
* Do not modify `.env` or `.env.example`.
* Do not run full eval, `ingestion.py`, `tests/chains/`, or API-key-requiring
  commands without separate user approval.
* Do not commit automatically; do not create or switch branches.

### Validation plan for the generated document

Recommend the relevant commands from the project's safe, keys-free validation set,
with each suite run as its own command (do not combine test directories into one
`pytest` invocation):

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest tests/node/ -q
uv run pytest tests/graph/ -q
uv run pytest tests/evals/ -q
uv run pytest tests/server/ -q
uv run python evals/run_eval.py --validate-only
npm --prefix frontend run typecheck
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

Use `tests/server/` for API changes. For frontend or frontend/backend contract changes,
include the relevant TypeScript type check, Vitest run, and Vite production build plus
any affected Python suite. Do not require unrelated suites, and state that executing
any validation still requires the active user's approval under repository rules.

Mark full eval as requiring separate approval and only when the feature needs it:

```powershell
uv run python evals/run_eval.py --output evals/results.md
```

### Recommended implementation invocation

The document's invocation section must point directly to:

```text
$imple-spec docs/roadmap/spec/<feature_slug>.md
```

The implementation steps must be specific enough that ``$imple-spec`` can execute
them without first creating another plan.

## Safety rules for this Skill

``$new-function-spec`` creates specification documentation only. It must not:

* implement the feature,
* modify application code, tests, prompts, model names, graph behavior/routing/nodes,
  eval rows, eval runners, or corpus documents,
* modify `.env` or `.env.example`,
* modify the spec template or any file outside
  `docs/roadmap/spec/<feature_slug>.md`,
* run tests, Ruff, mypy, full evals, ingestion, or API-key-requiring commands,
* commit, push, or create/switch branches.

## Step 7. Quality self-check

Before finishing, confirm:

* Exactly one document was created, under `docs/roadmap/spec/`.
* No plan file was created.
* The document follows the spec template and contains the required
  implementation-ready sections without duplication or contradiction.
* The implementation steps are detailed enough to feed directly into
  ``$imple-spec`` with no further planning.
* Filenames, APIs, schemas, and ADR references were verified against the repository.
* The spec template and all other repository files remain unchanged.

## Step 8. Final response

After the function spec file is saved, respond in exactly this concise format:

```text
Function spec file: `docs/roadmap/spec/<feature_slug>.md`

Title: `<feature_title>`

Ready for implementation: `$imple-spec docs/roadmap/spec/<feature_slug>.md`
```

Do not repeat the generated document in chat unless the user explicitly asks to see it.
