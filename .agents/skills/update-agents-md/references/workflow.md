# Detailed Workflow

This reference defines the project-specific procedure for maintaining durable agent
guidance after a completed change. The execution boundary in `../SKILL.md` is
authoritative.

## Contents

- Safety constraints
- Resolve the source change
- Decide whether durable guidance changed
- Update AGENTS.md
- Update roadmap conventions when required
- Validate and report

## Safety constraints

Modify only:

- `AGENTS.md`;
- `docs/roadmap/README.md`, and only when artifact-directory or filename conventions
  changed.

Do not edit any other README, application code, tests, evals, prompts, models, corpus
documents, environment files, specifications, plans, implementation reports, review
reports, or Skill definitions. Do not create new files.

Do not run tests, evals, ingestion, the application, or commands requiring API keys. Do
not stage, commit, create branches, or switch branches.

## Resolve the source change

Require one of:

- an implementation report path;
- a specification or plan path;
- a review report path;
- a concise description of a completed change.

If the user provides an explicit path, read it and stop if it does not exist. Do not
replace a missing explicit path with a broad search.

For a short description, search only relevant subdirectories of `docs/roadmap/`. Use one
clear match. If multiple artifacts are equally relevant, list them and ask for the exact
path. If none match, report that no source artifact was found.

Always read the current `AGENTS.md`. Read `docs/roadmap/README.md` only when the source
change may affect artifact conventions.

## Decide whether durable guidance changed

Add guidance only for long-lived information future agents need, such as:

- architecture or module boundaries;
- safety and privacy constraints;
- public contracts and compatibility requirements;
- testing and validation conventions;
- canonical entry points;
- generated-file and gitignore rules;
- stable evaluation or history conventions;
- repository Skill and workflow conventions.

Do not add:

- one-off implementation details;
- dates, commits, or task history;
- full test output or validation counts;
- report summaries;
- temporary notes;
- feature trivia already discoverable from code;
- rules already stated clearly in `AGENTS.md`.

When no durable guidance changed, leave `AGENTS.md` untouched and report a no-change
outcome.

## Update AGENTS.md

When an update is justified:

- make the smallest edit in the most relevant existing section;
- preserve the current structure and tone;
- prefer concise, actionable bullets;
- avoid duplicating `README.md`, `structure.md`, or source-code details;
- keep application model configuration separate from Codex development configuration;
- do not alter graph routing, stop-reason, privacy, fallback-policy, prompt, or state
  descriptions unless the completed source change actually changed them.

Do not turn `AGENTS.md` into a changelog.

## Update roadmap conventions when required

Edit `docs/roadmap/README.md` only when the source change adds, renames, removes, or
materially changes a durable artifact directory or filename convention. Document the
directory purpose and naming rule, not individual generated reports.

## Validate and report

Inspect the resulting content and confirm that only the two permitted files could have
changed. If Git metadata is available, inspect status and a diff restricted to those
files. If the directory is not a Git checkout, report that limitation and list the files
changed directly.

Return:

- whether `AGENTS.md` changed;
- whether `docs/roadmap/README.md` changed;
- the durable rule or convention added, or why no update was needed;
- validation performed and omitted;
- confirmation that no other file was modified.
