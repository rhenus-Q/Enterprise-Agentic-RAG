# Detailed Workflow

This reference contains the detailed project-specific procedure for the Skill. The Skill metadata and execution boundary in `SKILL.md` remain authoritative.

## Contents

- Goal
- Focus is a hard boundary
- Report filename rule
- Step 1. Read minimal project context
- Step 2. Inspect architecture-relevant areas
- Step 3. Review architecture quality
- Step 4. Look for risks and improvement opportunities
- Step 5. Write architecture review report
- Conditional report structure
- Step 6. Final response

You are reviewing the architecture of this Agentic RAG project.

User input: the user's skill input

## Safety constraints (authoritative)

This is a review-only task.

Do not modify application code.

Do not modify tests.

Do not modify eval files.

Do not modify prompts.

Do not modify model names.

Do not modify corpus documents.

Do not modify `.env` or `.env.example`.

Do not modify graph behavior.

Do not modify graph routing.

Do not modify graph nodes.

Do not modify `stop_reason` semantics.

Do not modify fallback policy semantics.

Do not run full eval.

Do not run `ingestion.py`.

Do not run `tests/chains/`.

Do not run API-key-requiring commands.

Do not commit.

Do not create or switch branches.

Use as few tools as possible.

## Goal

Primary question:

> Is the system structure and dependency design appropriate for the requested scope?

Review whether the requested architecture is clean, maintainable, testable, observable,
and structurally safe to continue building on. For an unscoped review, assess the
repository's broader architectural readiness.

This review should cover:

* architecture quality
* separation of concerns
* graph design
* configuration and side effects
* observability architecture
* architectural readiness
* eval architecture
* testability architecture, dependency injection, and mock seams
* architecture diagrams and boundary documentation when directly relevant

Write a new architecture review report under:

`docs/roadmap/architecture-review/`

Do not overwrite previous architecture review reports.

## Report filename rule

Create a unique report filename using this format:

`docs/roadmap/architecture-review/<YYYY-MM-DD>-<focus-slug>-architecture-review.md`

Where:

* `<YYYY-MM-DD>` is the verified date collected immediately before report creation in
  Step 5.

* `<focus-slug>` is derived from `the user's skill input`.

* If `the user's skill input` is empty, use `overall`.

* Convert the focus to a lowercase slug:

  * trim whitespace
  * replace spaces with hyphens
  * remove quotes
  * remove characters that are unsafe for filenames
  * keep only letters, numbers, and hyphens where possible

* If `the user's skill input` is not empty but sanitizing it produces an empty slug, use `overall`.

Examples:

* ``$arch-review`` writes to something like:
  `docs/roadmap/architecture-review/2026-06-13-overall-architecture-review.md`

* `$arch-review eval harness` writes to something like:
  `docs/roadmap/architecture-review/2026-06-13-eval-harness-architecture-review.md`

* `$arch-review graph flow` writes to something like:
  `docs/roadmap/architecture-review/2026-06-13-graph-flow-architecture-review.md`

* `$arch-review ??` and `$arch-review !!!` sanitize to an empty slug, so they use `overall`:
  `docs/roadmap/architecture-review/2026-06-13-overall-architecture-review.md`

Before writing, select the report path by checking candidate paths for existence in order and using the first candidate that does not already exist:

1. the base filename `docs/roadmap/architecture-review/<YYYY-MM-DD>-<focus-slug>-architecture-review.md`
2. then `docs/roadmap/architecture-review/<YYYY-MM-DD>-<focus-slug>-architecture-review-2.md`
3. then `docs/roadmap/architecture-review/<YYYY-MM-DD>-<focus-slug>-architecture-review-3.md`
4. continue incrementing the numeric suffix until a candidate path does not exist

Check each candidate with a path-existence check before selecting it.

Do not overwrite any existing architecture review report.

Create only the selected unique report file.

Do not write any other file.

## Focus is a hard boundary

When the user supplies a focus, scope, path, component, layer, or named concern, review
only that target and the minimum directly dependent evidence required to verify it.
Direct evidence may include imported or called modules, adjacent API contracts,
directly relevant tests, directly relevant configuration, and directly relevant
documentation. It must not automatically include unrelated repository areas.

Apply this boundary consistently to discovery commands, files read, findings, report
sections, readiness conclusions, and recommended actions. Do not perform a
repository-wide scan, produce an overall architectural-readiness verdict, or populate
unrelated report sections. When no focus is supplied, the broader default review may
remain.

## Step 1. Read minimal project context

Always read `AGENTS.md`. For an unscoped review, also read `README.md` and
`structure.md`. For a focused review, read those documents only when they contain a
directly relevant architectural claim.

Run:

```powershell
git status --short
```

Then inspect only files permitted by the focus boundary.

Prefer targeted reads over broad file reading.

## Step 2. Inspect architecture-relevant areas

Inspect these areas only when allowed by the focus boundary. For an unscoped review,
consider them as needed; do not read every listed area mechanically.

### Project entry points and configuration

* `pyproject.toml`
* Discover relevant CI workflows only through `.github/workflows/*.yml` and
  `.github/workflows/*.yaml`; do not assume one filename is authoritative.
* `.gitignore`
* `AGENTS.md`
* `README.md`
* `structure.md`

### Graph and runtime flow

* `graph/graph.py`
* `graph/state.py`
* `graph/consts.py`
* `graph/config.py`
* `graph/engine.py`
* `graph/formatting.py`
* `graph/nodes/`
* `graph/chains/`

### Web application layer

* `server/`, including the FastAPI application, schemas, runtime status, run history,
  document metadata, and package boundary
* `frontend/src/`, including API client/types, mocks, pages, components, and co-located
  tests
* `frontend/package.json`
* `frontend/package-lock.json`
* `frontend/vite.config.ts`
* `frontend/tsconfig.json`
* `frontend/index.html`

Inspect the integration boundaries between `server.app` and `graph.engine`,
`server.status` / `server.documents` and graph or ingestion configuration,
`server/schemas.py` and `frontend/src/api/types.ts`, API routes and
`frontend/src/api/client.ts`, the Vite `/api` proxy, and FastAPI's optional
`frontend/dist` static mount. Do not inspect generated `frontend/dist/` contents.

### Eval system

* `evals/run_eval.py`
* `evals/questions.jsonl`
* `evals/README.md`
* `evals/history/`

### Testability evidence

* `tests/node/`
* `tests/graph/`
* `tests/evals/`
* `tests/server/`
* `frontend/src/*.test.ts`
* `frontend/src/*.test.tsx`
* `frontend/src/**/*.test.ts`
* `frontend/src/**/*.test.tsx`

Use tests only to assess architectural testability, contract seams, dependency
injection, mock seams, import isolation, and whether the design makes correct testing
possible. Do not build a complete coverage map or enumerate missing tests. Do not
inspect `tests/chains/` unless the user explicitly asks.

### Codex Skill workflow

Do not inspect `.agents/skills/**` by default. Inspect it only when the user explicitly
focuses on agent/Skill architecture or files there are part of the reviewed change.

Inspect roadmap artifacts only when they contain a directly relevant architectural
decision or boundary claim.

Do not inspect `.env`.

Do not inspect generated runtime artifacts unless needed.

## Step 3. Review architecture quality

Evaluate the following areas.

### Graph design

* Is the graph flow understandable?
* Are node responsibilities clear?
* Are routing decisions explicit?
* Are cycles, terminal paths, and policy ownership placed in the correct layer?
* Are quality gates such as document grading, hallucination grading, and answer usefulness grading placed in the right layer?

### Configuration and side effects

* Are API clients lazy-loaded?
* Are imports side-effect free where they should be?
* Is environment/config access centralized?
* Are expensive operations avoided at import time?
* Can tests import modules without API keys?
* Are runtime policies resolved once per run rather than read inconsistently across nodes?

### Separation of concerns

* Is graph execution separated from formatting?
* Is eval logic separated from graph logic?
* Are node and chain responsibilities separated?
* Are nodes responsible for GraphState updates while chains handle LLM/prompt logic?
* Is persistence/history logic isolated enough?
* Does `server/` remain a thin adapter over the canonical engine rather than
  duplicating graph or business behavior?
* Does `frontend/` consume the API contract without duplicating backend policy?
* Is business behavior separated from observability and reporting?

### Web application boundaries

* Do server request/response schemas and frontend API types remain aligned?
* Are API error, status, cancellation, citation, document, and run-history contracts
  explicit and stable?
* Are development proxying and production static serving clearly separated?
* Are server and frontend imports/builds side-effect-safe for their respective tools?

### Eval architecture

* Are eval rows expressive enough?
* Are eval checks deterministic?
* Are history and delta reporting safe and metadata-only?
* Is full eval clearly separated from safe validation?
* Are generated history files correctly ignored?
* Is `validate-only` safe?
* Are eval expectations readable and maintainable?

### Observability architecture

* Are `run_id`, `node_path`, node timings, counters, and trace outputs useful for debugging graph runs?
* Is observability additive and non-behavior-changing?
* Are trace files metadata-only?
* Are raw documents, prompts, raw graph state, user secrets, and API keys excluded from trace output?
* Are trace write failures handled safely without losing the answer?
* Are `stop_reason`, retry counters, web search counters, and grading counters sufficient to understand why a run ended?
* Are observability fields exposed in a structured way through `AnswerResult`?
* Are generated trace/debug artifacts safe to persist or share?
* Does the observability design help diagnose graph failures without making the graph harder to reason about?

### Testability

* Are dependency-injection, lazy-factory, monkeypatch, and mock seams clean and
  intentional?
* Are graph, node, eval, server, frontend, and contract test layers structurally
  separated?
* Can important boundaries be tested without external services or import-time side
  effects?
* Does the design make correct testing possible without locking tests to internal
  implementation details?

Do not inventory missing tests here. Detailed suite completeness belongs to
`test-coverage-review`.

### Architectural readiness

* Are structural deployability, coupling, state ownership, interfaces, persistence
  boundaries, scaling constraints, and build/runtime boundaries credible?
* Are import-time side effects and dependency construction compatible with deployment
  and tooling?
* Are concurrency and persistence responsibilities explicit rather than hidden in
  adapters or global state?

Do not turn architectural readiness into an operational timeout, retry, cancellation,
fallback, degradation, or failure-path audit. Those questions belong to
`failure-modes-review`.

### Architectural documentation

Inspect documentation only to verify architecture diagrams, module responsibilities,
dependency direction, interface ownership, and architectural boundary claims. Do not
perform a general documentation-drift audit.

### Engineering quality

* Would this architecture read as credible to a senior engineer?
* Are there signs of overengineering?
* Are there signs of underengineering?
* What would improve architectural readiness?
* Is the project's design explainable in a clear technical narrative?
* Does the architecture reflect real engineering judgment rather than only prototype LLM behavior?

## Step 4. Look for risks and improvement opportunities

Flag:

* hidden coupling
* unclear ownership of logic
* duplicate logic
* fragile eval assumptions
* architecture that makes future features harder
* observability seams that are structurally coupled to behavior
* structural deployment constraints that make future operation or scaling harder

Security, reliability, test, and documentation evidence may be cited only when it
proves an architectural boundary or consequence. Do not independently audit those
neighboring domains.

Do not rewrite the architecture.

Do not implement fixes.

Only review and recommend.

## Step 5. Write architecture review report

Immediately before the first report write, run this command exactly once:

    date "+%Y-%m-%d %H:%M:%S %z"

Treat the returned timestamp as the only authoritative current local time. Reuse its
`YYYY-MM-DD` portion in the filename and report body. Never infer or copy the date from
model knowledge, conversation history, Git history, existing reports, or filenames. If
the command fails, stop and do not write a report with a guessed date.

Create `docs/roadmap/architecture-review/` if needed, then create only the selected
unique report using the filename rule above. Do not overwrite an existing report.

### Conditional report structure

Include report metadata: title `Architecture Review`, status `Review`, verified date,
requested focus or `Overall architecture`, and selected report path.

Always retain this compact core:

1. **Review summary** — give a scope-specific conclusion. Include an architectural-
   readiness verdict only for an unscoped overall review.
2. **Scope reviewed** — state the requested boundary, included dependencies, and
   explicit exclusions.
3. **Evidence inspected** — list exact files, directories, and repository commands.
4. **Findings** — for each finding give evidence, architectural consequence, risk,
   recommended action, and timing; state clearly when no material issue was confirmed.
5. **Recommendations or priority** — Must fix / Should fix soon / Optional, using only
   findings inside scope.
6. **Limitations / not reviewed** — omit unrelated domains or state briefly:
   `Not reviewed because it was outside the requested scope.`
7. **Validation or commands run** — list commands actually run and prohibited
   validation that did not run.

Add domain-specific sections—such as graph structure, API contracts, eval architecture,
observability seams, testability architecture, architectural documentation, or
architectural readiness—only when relevant to the requested focus and evidence
actually inspected. Do not fill unrelated sections with speculative findings or expand
the scan merely to avoid writing `Not reviewed`.

## Step 6. Final response

After writing the report, respond with:

Architecture review report: `<selected unique report path>`

Scope conclusion: `<scope-specific conclusion>`

Top issues:

* <issue 1>
* <issue 2>
* <issue 3>

Do not repeat the full report in chat unless the user explicitly asks. For a focused
review, do not present the conclusion as a repository-wide readiness verdict.
