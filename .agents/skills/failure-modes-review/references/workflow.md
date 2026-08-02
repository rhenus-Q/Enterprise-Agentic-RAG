# Detailed Workflow

This reference contains the detailed project-specific procedure for the Skill. The Skill metadata and execution boundary in `SKILL.md` remain authoritative.

## Contents

- Goal
- Focus is a hard boundary
- Report filename rule
- Step 1. Read minimal project context
- Step 2. Inspect failure-mode-relevant areas
- Step 3. Review failure handling quality
- Step 4. Look for risks and improvement opportunities
- Step 5. Write failure-mode review report
- Conditional report structure
- Step 6. Final response

You are reviewing failure modes, failure handling, cost/budget controls, and operational
reliability readiness in this Agentic RAG project.

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

Do not run tests.

Do not run full eval.

Do not run `ingestion.py`.

Do not run `tests/chains/`.

Do not run API-key-requiring commands.

Do not commit.

Do not create or switch branches.

Use as few tools as possible.

## Goal

Primary question:

> When this system or dependency fails, is the behavior bounded, honest, recoverable,
> and operationally safe?

Review whether failure behavior in the requested scope supports operational reliability
readiness.

This review should cover:

* failure handling
* retry and loop behavior
* stop_reason correctness
* fallback policy behavior
* timeout and cancellation behavior
* LLM cost and budget controls
* web search budget controls
* web result grading budget controls
* external dependency failure behavior
* degraded-mode behavior
* partial success, cleanup, concurrency, and persistence failures
* recovery, retryability, and operational observability
* regression evidence for critical failure guarantees

Write a new failure-mode review report under:

`docs/roadmap/failure-modes-review/`

Do not overwrite previous failure-mode review reports.

## Report filename rule

Create a unique report filename using this format:

`docs/roadmap/failure-modes-review/<YYYY-MM-DD>-<focus-slug>-failure-modes-review.md`

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

* ``$failure-modes-review`` writes to something like:
  `docs/roadmap/failure-modes-review/2026-06-24-overall-failure-modes-review.md`

* `$failure-modes-review web search failures` writes to something like:
  `docs/roadmap/failure-modes-review/2026-06-24-web-search-failures-failure-modes-review.md`

* `$failure-modes-review budget limits` writes to something like:
  `docs/roadmap/failure-modes-review/2026-06-24-budget-limits-failure-modes-review.md`

* `$failure-modes-review ??` and `$failure-modes-review !!!` sanitize to an empty slug, so they use `overall`:
  `docs/roadmap/failure-modes-review/2026-06-24-overall-failure-modes-review.md`

Before writing, select the report path by checking candidate paths for existence in order and using the first candidate that does not already exist:

1. the base filename `docs/roadmap/failure-modes-review/<YYYY-MM-DD>-<focus-slug>-failure-modes-review.md`
2. then `docs/roadmap/failure-modes-review/<YYYY-MM-DD>-<focus-slug>-failure-modes-review-2.md`
3. then `docs/roadmap/failure-modes-review/<YYYY-MM-DD>-<focus-slug>-failure-modes-review-3.md`
4. continue incrementing the numeric suffix until a candidate path does not exist

Check each candidate with a path-existence check before selecting it.

Do not overwrite any existing failure-mode review report.

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
repository-wide scan, produce an overall operational-reliability-readiness verdict, or
populate unrelated report sections. When no focus is supplied, the broader default
failure-mode review may remain.

## Step 1. Read minimal project context

Always read `AGENTS.md`. For an unscoped review, also read `README.md` and
`structure.md`. For a focused review, read those documents only when they contain a
directly relevant failure-semantics claim.

Run:

```powershell
git status --short
```

Then inspect only files permitted by the focus boundary.

Prefer targeted reads over broad file reading.

## Step 2. Inspect failure-mode-relevant areas

Inspect these areas only when allowed by the focus boundary. For an unscoped review,
consider them as needed; do not read every listed area mechanically.

### Runtime and configuration

* `graph/engine.py`
* `graph/config.py`
* `graph/consts.py`
* `graph/state.py`
* `graph/graph.py`
* `graph/formatting.py`

### Graph routing and loop behavior

* `graph/graph.py`
* `graph/nodes/`
* `graph/chains/`

### Key node failure boundaries

* `graph/nodes/retrieve.py`
* `graph/nodes/grade_documents.py`
* `graph/nodes/generate.py`
* `graph/nodes/web_search.py`
* `graph/nodes/rewrite_query.py`
* `graph/nodes/add_grounding_feedback.py`
* `graph/nodes/clear_transient_tool_error.py`
* `graph/nodes/*notice*.py`

### API and browser failure boundaries

* `server/`, including engine-to-HTTP error mapping, startup preflight degradation,
  request concurrency, cancellation, run history, runtime status, document metadata,
  and optional static serving
* `frontend/src/api/`, including request timeouts, cancellation, response parsing,
  mocks, and frontend API types
* Frontend pages and components that present loading, partial, caveat, empty, offline,
  timeout, and error states
* `frontend/package.json`, `frontend/vite.config.ts`, and `frontend/tsconfig.json`

Inspect contract failure boundaries between `server/schemas.py` and
`frontend/src/api/types.ts`, API routes and `frontend/src/api/client.ts`, the Vite
development proxy, and FastAPI's optional `frontend/dist` mount. Do not inspect
generated `frontend/dist/` contents.

### Eval and regression evidence

* `evals/run_eval.py`
* `evals/questions.jsonl`
* `evals/README.md`
* `tests/node/`
* `tests/graph/`
* `tests/evals/`
* `tests/server/`
* `frontend/src/*.test.ts`
* `frontend/src/*.test.tsx`
* `frontend/src/**/*.test.ts`
* `frontend/src/**/*.test.tsx`

Use tests only as regression evidence for critical failure guarantees. The Skill may
report that a guarantee lacks evidence, but it must not construct a complete test
inventory, prescribe detailed test placement, or assess suite completeness. Inspect
`tests/chains/` only when the user explicitly places it in scope.

Do not run `tests/chains/`.

### Tooling and CI

* `pyproject.toml`
* Discover relevant CI workflows only through `.github/workflows/*.yml` and
  `.github/workflows/*.yaml`; do not assume one filename is authoritative.
* `.gitignore`

Do not inspect `.agents/skills/**` by default. Inspect it only when Skill files are
explicitly in focus or are part of the reviewed change.

Do not inspect `.env`.

Do not run `ingestion.py`.

Do not run API-key-requiring commands.

Do not inspect generated runtime artifacts unless needed.

## Step 3. Review failure handling quality

Evaluate the following areas.

### Failure-mode map

* What can fail in this system?
* Are LLM failures handled?
* Are retriever/vector-store failures handled?
* Are web search failures handled?
* Are grader failures handled?
* Are query rewriter failures handled?
* Are trace-write failures handled?
* Are eval/reporting failures isolated from runtime behavior?
* Are timeout, cancellation, partial-success, cleanup, concurrency, and persistence
  failures handled?
* Does the system degrade safely instead of crashing where appropriate?

### Stop reason correctness

* Are stop reasons explicit and consistent?
* Does each major failure path set the correct `stop_reason`?
* Are terminal notice nodes clear and intentional?
* Does formatting surface stop reasons accurately to users?
* Are stale or transient stop reasons cleared only when safe?
* Are stop reasons testable and covered by tests?
* Are stop reasons stable enough for eval expectations and future automation?

### Retry and loop safety

* Are retry loops bounded?
* Are hallucination retries bounded?
* Are usefulness retries bounded?
* Are rewrite-query loops bounded?
* Are graph cycles understandable?
* Can any path loop forever?
* Are max retry terminal paths clear?
* Are retry counters incremented consistently?
* Does retry feedback change the next generation attempt meaningfully?

### Timeout, cancellation, cleanup, and recovery

* Are timeouts explicit, bounded, and classified accurately?
* Does cancellation stop work cooperatively and release locks or shared state?
* Do partial-success paths preserve useful results without claiming complete success?
* Are state cleanup, retryability, and recovery ownership explicit?
* Can concurrency or persistence failures corrupt unrelated runs or leave the service
  unavailable?

### Cost and budget controls

* Are LLM call budgets enforced?
* Are web search budgets enforced?
* Are web result grading budgets enforced?
* Are budget limits centralized in config?
* Are budget defaults safe?
* Are invalid budget environment variables handled safely?
* Is `tracked_llm_calls` clearly documented as an operational counter rather than total billing?
* Can expensive paths accidentally run too many LLM/tool calls?
* Are budget-exhausted paths clear and user-visible?
* Are budget-related behaviors tested?

### External dependency failures

* If OpenAI/LLM calls fail, does the system return a safe result?
* If Chroma/vector store retrieval fails, does the system avoid crashing?
* If Tavily/web search fails, does the system preserve local results when possible?
* If graders fail, does the system avoid trusting unverified content?
* If query rewriting fails, does the system fall back safely?
* If trace writing fails, does the answer still return?
* Are exception logs careful not to print sensitive messages?
* Are dependency failures represented accurately in `stop_reason`?

### API and browser degraded modes

* Are engine and preflight failures mapped to stable, sanitized HTTP responses without
  discarding successful answers?
* Do single-flight conflicts and cooperative cancellation release server state safely?
* Do run-history, status, and document-metadata failures degrade without corrupting
  unrelated requests or exposing internal details?
* Does a missing frontend build leave the API operational in an explicit API-only mode?
* Does the frontend distinguish backend-unreachable, timeout, cancellation, malformed
  response, empty-data, and server-error states honestly?
* Do server schemas and frontend API types fail visibly rather than silently drifting?

### Web fallback and degraded mode

* Are fallback policies clear?
* Is conservative fallback behavior understandable?
* Is aggressive fallback behavior, if present, controlled?
* Is disabled fallback behavior explicit?
* Does privacy mode prevent outbound web search even when fallback is requested?
* Does the system produce an honest insufficient-context answer when it cannot safely continue?
* Are local documents preserved when web search fails?
* Are unverified web results excluded from generation?

### Privacy and security-related failure behavior

Review privacy and security only when caused by a failure mode.

* If user input contains secrets, are they redacted before failure paths can log or persist them?
* If web search is disabled, is the privacy guarantee preserved under all failure paths?
* If a tool fails, can raw user input, raw documents, or secrets leak through logs/traces?
* Are trace and observability failures safe?
* Are exception messages intentionally limited?

General security posture belongs to `security-review`.

### Operational reliability readiness

* Is the project safe to continue building on without accumulating fragile failure paths?
* Are operational counters sufficient for debugging?
* Are failure behavior, cleanup, recovery, retryability, and degraded operation bounded
  and honest?
* Are operational risks explicit without making a repository-wide architecture or
  security judgment?

### Regression evidence for critical failure guarantees

When directly relevant, determine whether a critical failure guarantee has regression
evidence. Report absent evidence as a reliability risk modifier, but leave detailed
test placement, suite completeness, and coverage mapping to `test-coverage-review`.

Documentation checks are limited to directly relevant claims about retries, budgets,
timeouts, cancellation, fallback, degraded behavior, `stop_reason`, and failure
semantics. Do not perform a broad documentation-drift audit.

## Step 4. Look for risks and improvement opportunities

Flag:

* failure paths that crash instead of degrading safely
* silent failures with no `stop_reason`
* stale `stop_reason` values that survive successful recovery
* failure paths that overwrite useful previous context
* unbounded loops
* retry counters that are inconsistent
* budget counters that do not match actual expensive operations
* web search or grading paths that can exceed configured limits
* fallback-policy confusion
* privacy-mode bypasses
* exception messages that may leak paths, prompts, raw documents, or secrets
* observability that is too weak to debug failures
* API failures that return misleading status codes or leak internal details
* cancellation or request-lock paths that leave the server unavailable
* frontend failures that collapse distinct backend states into misleading UI
* server/frontend contract drift that produces unhandled or silent failures
* a critical failure guarantee without regression evidence
* operational reliability gaps that could cause fragile behavior
* directly relevant documentation that overstates failure handling or recovery

Do not rewrite the architecture.

Do not implement fixes.

Only review and recommend.

## Step 5. Write failure-mode review report

Immediately before the first report write, run this command exactly once:

    powershell.exe -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'"

Treat the returned timestamp as the only authoritative current local time. Reuse its
`YYYY-MM-DD` portion in the filename and report body. Never infer or copy the date from
model knowledge, conversation history, Git history, existing reports, or filenames. If
the command fails, stop and do not write a report with a guessed date.

Create `docs/roadmap/failure-modes-review/` if needed, then create only the selected
unique report using the filename rule above. Do not overwrite an existing report.

### Conditional report structure

Include report metadata: title `Failure Modes Review`, status `Review`, verified date,
requested focus or `Overall failure modes`, and selected report path.

Always retain this compact core:

1. **Review summary** — give a scope-specific conclusion. Include an operational-
   reliability-readiness verdict only for an unscoped overall review.
2. **Scope reviewed** — state the requested boundary, included dependencies, and
   explicit exclusions.
3. **Evidence inspected** — list exact files, directories, and repository commands.
4. **Findings** — for each finding give evidence, reliability consequence, risk,
   recommended action, and timing; state clearly when no material issue was confirmed.
5. **Recommendations or priority** — Must fix / Should fix soon / Optional, using only
   findings inside scope.
6. **Limitations / not reviewed** — omit unrelated domains or state briefly:
   `Not reviewed because it was outside the requested scope.`
7. **Validation or commands run** — list commands actually run and prohibited
   validation that did not run.

Add domain-specific sections—such as retries, timeouts, cancellation, budgets, loop
termination, fallback, degraded modes, provider failures, partial success, cleanup,
concurrency, persistence, `stop_reason`, error classification, recovery, operational
observability, directly relevant failure-semantics documentation, or regression
evidence for a critical guarantee—only when relevant to the requested focus and
evidence actually inspected. Do not produce a full test-coverage, security,
architecture, or documentation section, and do not expand the scan merely to avoid
writing `Not reviewed`.

## Step 6. Final response

After writing the report, respond with:

Failure-mode review report: `<selected unique report path>`

Scope conclusion: `<scope-specific conclusion>`

Top issues:

* <issue 1>
* <issue 2>
* <issue 3>

Do not repeat the full report in chat unless the user explicitly asks. For a focused
review, do not present the conclusion as a repository-wide readiness verdict.
