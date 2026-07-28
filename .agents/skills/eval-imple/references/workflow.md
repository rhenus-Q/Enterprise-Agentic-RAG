# Detailed Workflow

This reference contains the detailed project-specific procedure for the Skill. The Skill metadata and execution boundary in `SKILL.md` remain authoritative.

## Contents

- Step 0. Validate input
- Step 1. Read project rules
- Step 2. Understand the request
- Step 3. Inspect the current implementation
- Optional LangChain Docs MCP check
- Step 4. Evaluate the proposed change
- Step 5. Decide
- If no change is justified
- If a change is justified
- Step 6. Check working tree
- Step 7. Implement the smallest correct change
- Default safety constraints
- Step 8. Validate
- Step 9. Review the final diff
- Step 10. Ask only when necessary
- Final report

You are evaluating a proposed change for this Agentic RAG project, then implementing it **only if the repository evidence justifies it**.

User input: the user's skill input

This Skill formalizes one workflow: **evaluate first -> decide whether a change is justified -> implement only when necessary -> validate the result.**

Core principle: **do not assume the proposed solution is necessary merely because it was requested.** A no-change decision is a complete, successful outcome. When action is warranted, make the smallest correct change.

Use as few tools as possible.

Do not create or switch git branches.

Do not commit automatically.

## Step 0. Validate input

If `the user's skill input` is empty, stop before reading any files and ask the user to
describe the proposed change or goal:

`Please describe the change or goal you want evaluated.`

## Step 1. Read project rules

Read first:

* `AGENTS.md`

Prefer evidence from this repository — its code, tests, ADRs, configuration, and
docs — over generic best practices.

## Step 2. Understand the request

State, in your own words:

* the underlying **problem or goal** behind the request (not just the literal
  solution proposed);
* what "solved" would look like.

If the request conflates a problem with a specific solution, separate the two.

## Step 3. Inspect the current implementation

Inspect only what is relevant to the request: the current implementation, related
tests, configuration, documentation, ADRs (`docs/adr/`), and existing
abstractions. Prefer targeted text searches, file listings, and focused reads over broad sweeps.

Determine whether the current implementation **already solves the problem**. If it
does, that is strong evidence for a no-change outcome.

### Optional LangChain Docs MCP check

Only if the change depends on current LangChain / LangGraph / LangSmith / MCP
behavior, consult the LangChain Docs MCP server
(the configured `docs-langchain` MCP search tool /
the configured `docs-langchain` MCP filesystem-docs tool) with a narrow
query. Do not let external docs override local project contracts, and do not dump
raw MCP output. Mention it in the final report only if used.

## Step 4. Evaluate the proposed change

Assess the proposal against the current codebase for:

* correctness;
* meaningful practical value;
* architectural consistency;
* duplication of an existing abstraction;
* unnecessary complexity;
* maintenance burden;
* compatibility and public-contract impact;
* testing impact;
* documentation drift;
* security implications;
* error and failure behavior.

Then consider whether a **smaller or simpler solution** would solve the same
problem, and whether the repository already offers a more idiomatic approach.

## Step 5. Decide

Choose exactly one:

* **no change** — the problem is already solved, or the change is not justified;
* the **proposed change**;
* a **smaller alternative** that solves the same problem;
* a **different implementation** supported by stronger repository evidence.

Treat "no change" as a valid, complete result.

### If no change is justified

Make no modifications. Go straight to the final report and clearly explain the
evidence supporting the decision. This is a successful outcome.

### If a change is justified

Continue to Step 6.

## Step 6. Check working tree

Run:

```powershell
git status --short
```

If the working tree has unrelated uncommitted changes, stop and ask the user
whether to continue. Do not overwrite unrelated changes.

## Step 7. Implement the smallest correct change

* Implement only what the decision requires.
* Preserve existing behavior and public contracts unless the request explicitly
  requires otherwise.
* Do not add speculative abstractions, future-proofing, dependencies, or
  configuration.
* Do not perform unrelated refactoring or cleanup.
* Update tests and documentation only where the change makes it necessary.
* Never weaken or delete tests to make a change pass.

### Default safety constraints

Unless the request explicitly approves an exception:

* Do not change prompts, model names, or corpus documents.
* Do not change graph behavior, graph routing, graph nodes, `stop_reason`
  semantics, or fallback-policy semantics.
* Do not modify `.env` or `.env.example`.
* Do not run full eval, `ingestion.py`, `tests/chains/`, or any
  API-key-requiring command.
* Do not commit automatically; do not create or switch branches.

## Step 8. Validate

Run the **narrowest relevant validation first**, then expand only when justified.
Run each keys-free suite as its own command so it matches its scoped
active sandbox and approval permission:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest tests/node/ -q
uv run pytest tests/graph/ -q
uv run pytest tests/evals/ -q
uv run python evals/run_eval.py --validate-only
```

Run only the suites relevant to the change. Do not run full eval, ingestion,
chain integration tests, or API-key commands unless the user separately approves.

## Step 9. Review the final diff

Inspect the diff (`git diff`, `git status --short`) and check for:

* accidental scope expansion;
* unnecessary files or abstractions;
* duplication;
* contradictions;
* regressions;
* weakened tests;
* stale or inaccurate documentation;
* security or failure-mode regressions.

If any appear, fix or revert them before reporting.

## Step 10. Ask only when necessary

Ask for confirmation only when the action is destructive, irreversible,
security-sensitive, materially ambiguous, or requires a product decision that
cannot be inferred from the repository. Otherwise decide from repository evidence
and proceed.

## Final report

Report:

* the underlying **problem or goal**;
* whether a change was **necessary** (yes / no);
* the **evidence** supporting the decision;
* the **chosen approach**;
* important **alternatives considered and rejected**;
* files **created, modified, or deleted** (or "none");
* **tests and validation** performed, and their **results**;
* remaining **risks, limitations, or unresolved ambiguity**.

Do not commit. Do not create or switch branches.
