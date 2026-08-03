# Detailed Workflow

This reference contains the detailed project-specific procedure for the Skill. The Skill metadata and execution boundary in `SKILL.md` remain authoritative.

## Contents

- Goal
- Focus is a hard boundary
- Report filename rule
- Step 1. Read minimal project context
- Step 2. Inspect test-coverage-relevant areas
- Step 3. Review test coverage quality
- Step 4. Look for risks and improvement opportunities
- Step 5. Write test coverage review report
- Conditional report structure
- Step 6. Final response

You are reviewing test coverage for this Agentic RAG project.

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

> Are the intended behaviors protected by sufficient tests at the correct level, and
> are those tests executed by CI?

Review test evidence, coverage gaps, regression risks, test-layer placement, and CI
execution for the requested scope.

This review should focus on coverage gaps, regression risks, and missing tests around important behavior.

This review should cover:

* node test coverage
* graph routing test coverage
* eval harness test coverage
* failure-path test coverage
* cancellation and retry test coverage
* privacy-mode test coverage
* fallback-policy test coverage
* budget-limit test coverage
* stop_reason test coverage
* trace/observability test coverage
* security-related test coverage
* server/API and frontend/backend contract coverage
* frontend TypeScript type checking, Vitest, and Vite build validation
* documentation/test/CI alignment
* risky untested seams

Review test evidence, not whether the implementation itself is architecturally
correct, secure, or operationally appropriate. Those conclusions belong to the
corresponding review Skills.

Write a new test coverage review report under:

`docs/roadmap/test-coverage-review/`

Do not overwrite previous test coverage review reports.

## Report filename rule

Create a unique report filename using this format:

`docs/roadmap/test-coverage-review/<YYYY-MM-DD>-<focus-slug>-test-coverage-review.md`

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

* ``$test-coverage-review`` writes to something like:
  `docs/roadmap/test-coverage-review/2026-06-24-overall-test-coverage-review.md`

* `$test-coverage-review graph routing` writes to something like:
  `docs/roadmap/test-coverage-review/2026-06-24-graph-routing-test-coverage-review.md`

* `$test-coverage-review privacy mode` writes to something like:
  `docs/roadmap/test-coverage-review/2026-06-24-privacy-mode-test-coverage-review.md`

* `$test-coverage-review ??` and `$test-coverage-review !!!` sanitize to an empty slug, so they use `overall`:
  `docs/roadmap/test-coverage-review/2026-06-24-overall-test-coverage-review.md`

Before writing, select the report path by checking candidate paths for existence in order and using the first candidate that does not already exist:

1. the base filename `docs/roadmap/test-coverage-review/<YYYY-MM-DD>-<focus-slug>-test-coverage-review.md`
2. then `docs/roadmap/test-coverage-review/<YYYY-MM-DD>-<focus-slug>-test-coverage-review-2.md`
3. then `docs/roadmap/test-coverage-review/<YYYY-MM-DD>-<focus-slug>-test-coverage-review-3.md`
4. continue incrementing the numeric suffix until a candidate path does not exist

Check each candidate with a path-existence check before selecting it.

Do not overwrite any existing test coverage review report.

Create only the selected unique report file.

Do not write any other file.

## Focus is a hard boundary

When the user supplies a focus, scope, path, component, layer, or named concern, review
only that target and the minimum directly dependent evidence required to map its test
evidence. Direct evidence may include imported or called modules, adjacent API
contracts, directly relevant tests, directly relevant configuration, and directly
relevant documentation. It must not automatically include unrelated repository areas.

Apply this boundary consistently to discovery commands, files read, findings, report
sections, readiness conclusions, and recommended actions. Do not perform a
repository-wide scan, produce an overall test-readiness verdict, or populate unrelated
report sections. When no focus is supplied, the broader default coverage review may
remain.

## Step 1. Read minimal project context

Always read `AGENTS.md`. For an unscoped review, also read `README.md` and
`structure.md`. For a focused review, read those documents only when they contain a
directly relevant test, validation, or CI claim.

Run:

```powershell
git status --short
```

Then inspect only files permitted by the focus boundary.

Prefer targeted reads over broad file reading.

## Step 2. Inspect test-coverage-relevant areas

Inspect these areas only when allowed by the focus boundary. For an unscoped review,
consider them as needed; do not read every listed area mechanically.

Use discovery first, then targeted reads.

Do not assume exact implementation filenames. Inspect the actual project layout before reading files.

Read only files that are relevant to the requested focus and to test coverage review.

Read implementation files only to identify intended behavior, contracts, seams, and
risk. Do not use this workflow to conclude that the implementation is architecturally
correct, secure, or operationally appropriate.

### Runtime and architecture areas

First list relevant existing runtime files under:

* `graph/*.py`
* `graph/nodes/*.py`
* `graph/chains/*.py`

Then inspect only the relevant existing files.

Prioritize files that define or affect:

* graph construction and routing
* runtime state
* constants and `stop_reason` values
* configuration and budget policy
* engine entry points
* answer formatting and source rendering
* observability and trace behavior
* node behavior
* chain / prompt boundaries
* structured output schemas
* retry behavior
* privacy-mode behavior
* failure paths

Do not fail or waste time if a likely file is absent. Use the discovered `graph/` file list as the source of truth.

### Web application areas

First list relevant existing files under:

* `server/`
* `frontend/src/`
* `frontend/package.json`
* `frontend/vite.config.ts`
* `frontend/tsconfig.json`
* `frontend/index.html`

Then inspect only the relevant existing files. Prioritize FastAPI request/response
schemas, endpoint adapters, runtime status, run history, cancellation, static serving,
the frontend API client and types, mocks, pages/components, and the contracts between
`server/schemas.py` and `frontend/src/api/types.ts` and between API routes and
`frontend/src/api/client.ts`. Inspect `frontend/package-lock.json` only when dependency
or CI reproducibility is relevant. Do not inspect generated `frontend/dist/` contents.

### Eval system

First list relevant existing eval files under:

* `evals/*`
* `evals/**/*.py`
* `evals/**/*.jsonl`
* `evals/**/*.md`

Then inspect only the relevant existing files.

Prioritize eval files that define or document:

* eval schema validation
* expected output checks
* `expected_contains`
* OR-group semantics
* `expected_not_contains`
* `expected_web_search_count`
* `expected_stop_reason`
* `expected_min_local_sources`
* history records
* delta reporting
* validate-only behavior
* markdown reporting

Do not run full eval.

### Test directories

First list relevant existing test files under:

* `tests/node/**/*.py`
* `tests/graph/**/*.py`
* `tests/evals/**/*.py`
* `tests/server/**/*.py`
* `frontend/src/*.test.ts`
* `frontend/src/*.test.tsx`
* `frontend/src/**/*.test.ts`
* `frontend/src/**/*.test.tsx`

Then inspect only the test files relevant to the requested focus and to coverage-gap analysis.

Prioritize tests that cover:

* node behavior
* graph routing
* eval harness behavior
* engine behavior
* config behavior
* privacy mode
* fallback policies
* budget limits
* `stop_reason` behavior
* trace / observability behavior
* failure paths
* recent security or redaction changes
* FastAPI endpoint, schema, status, cancellation, history, and static-mount behavior
* frontend API client, page/component behavior, and user-visible error states
* frontend/backend schema and route contract compatibility

Inspect `tests/chains/` only if the user explicitly asks.

Do not run `tests/chains/`.

Do not run tests.

Do not run API-key-requiring tests.

### Tooling and CI

First list relevant existing tooling files under:

* `.github/workflows/*.yml`
* `.github/workflows/*.yaml`
* `*.toml`
* `frontend/package.json`
* `frontend/package-lock.json`
* `frontend/vite.config.ts`
* `frontend/tsconfig.json`
* `.gitignore`

Then inspect only the relevant existing files.

Prioritize tooling files that define or document:

* safe default test commands
* lint commands
* format checks
* type checks
* CI test jobs
* API-key-requiring test isolation
* generated artifact hygiene
* ignored runtime outputs
* safe versus unsafe test workflows

Do not inspect `.agents/skills/**` by default. Use Skill files only as on-demand
evidence when the user places them in scope or when verifying a Skill's claimed test or
validation command.

Do not inspect `.env`.

Do not inspect generated runtime artifacts unless needed.

### Documentation

Use the already-read project docs from Step 1 as the primary documentation context.

Inspect additional documentation only when needed to verify test command accuracy, CI expectations, eval workflow, or coverage-related claims.

Limit documentation findings to test commands, markers, CI suites, coverage claims,
Vitest, frontend type checking, frontend builds, and validation instructions. Do not
perform a general documentation-drift audit.

Do not broadly read roadmap artifacts unless they are directly relevant to the test coverage review.



## Step 3. Review test coverage quality

Evaluate the following areas.

### Node test coverage

* Are all node functions covered by mocked unit tests?
* Are node inputs and GraphState updates tested?
* Are success paths tested?
* Are failure paths tested?
* Are stop_reason updates tested?
* Are counters tested where nodes update counters?
* Are privacy, fallback, and budget-related fields tested?
* Are notice nodes tested?
* Are transient error cleanup behaviors tested?

### Graph routing coverage

* Are major graph routes covered?
* Are conditional routing decisions tested?
* Are terminal paths tested?
* Are retry loops tested?
* Are max-retry paths tested?
* Are insufficient-context paths tested?
* Are web-search-disabled paths tested?
* Are fallback-disabled paths tested?
* Are budget-exhausted paths tested?
* Are graph tests isolated from real API calls?

### Chain seam coverage

* Are chains separated from nodes enough to mock LLM behavior?
* Are node tests using monkeypatch seams rather than real API calls?
* Are structured-output chain expectations tested safely where possible?
* Are prompt-level risks covered by review or eval rows when direct tests would require API keys?
* Are chain imports side-effect free and testable without secrets?
* Are `tests/chains/` isolated from default CI if they require API keys?

### Engine and state coverage

* Is `seed_state()` tested?
* Is per-run config resolution tested?
* Is `AnswerOptions` dict conversion tested?
* Is `AnswerResult` construction tested?
* Is run_id generation tested?
* Is node_path/timing trace collection tested?
* Is trace write failure behavior tested?
* Is user input redaction tested?
* Is question hashing tested?
* Is raw question exclusion from runtime state tested?

### Server/API coverage

* Are request validation, response construction, citations, and stop-reason/status
  mapping covered without calling the real engine or external services?
* Are startup preflight, sanitized errors, runtime/index status, document metadata,
  bounded metadata-only run history, concurrency, cancellation, and static mounting
  covered?
* Are server imports and endpoint tests keys-free and network-free?

### Frontend and contract coverage

* Are the API client, mock client, pages, and critical components covered by Vitest?
* Are loading, success, caveat, empty, offline, timeout, cancellation, malformed-data,
  and server-error states covered where relevant?
* Are server schemas/routes and frontend types/client calls checked for contract drift?
* Does CI run TypeScript type checking, Vitest in non-watch mode, and the Vite
  production build?

### Config and budget coverage

* Are default config values tested?
* Are environment override behaviors tested?
* Are invalid environment values tested?
* Are budget defaults tested?
* Are budget override parsing rules tested?
* Are web_search_enabled and web_fallback_policy interactions tested?
* Are conservative, aggressive, and disabled fallback policies tested?
* Are budget-exhausted paths tested at graph or node level?

### Security and privacy coverage

* Are user-input secret redaction behaviors tested?
* Are API key/token/password patterns tested?
* Are privacy-mode guarantees tested?
* Are web search disabled guarantees tested?
* Are outbound web query redaction behaviors tested?
* Are trace metadata-only guarantees tested?
* Are raw document/prompt/raw_state leakage risks covered by tests or review checks?
* Are prompt-injection defenses covered by mocked tests, eval rows, or Skill reviews?

Report whether intended security behavior lacks regression evidence. Do not conclude
that the implementation is secure; security correctness belongs to `security-review`.

For timeout, cancellation, retry, budget, fallback, degraded-mode, and other failure
behavior, report only the presence, absence, placement, and CI execution of tests. The
correctness of the failure design belongs to `failure-modes-review`.

### Eval harness coverage

* Are eval schema validations tested?
* Are expected_contains semantics tested?
* Are OR-group semantics tested?
* Are expected_not_contains checks tested?
* Are expected_web_search_count checks tested?
* Are expected_stop_reason checks tested?
* Are expected_min_local_sources checks tested?
* Are history record and delta calculations tested?
* Are validate-only paths tested?
* Are reporting functions tested without running full eval?

### CI and safe default coverage

* Does CI run the safe mocked tests?
* Does CI avoid API-key-requiring tests by default?
* Are lint, formatting, type-checking, and safe tests wired correctly?
* Are test commands documented and consistent with AGENTS.md?
* Are generated results/history artifacts kept out of accidental commits where appropriate?

### Coverage gap quality

* Are missing tests prioritized by risk?
* Are recommendations specific enough to implement?
* Are gaps separated into Must fix, Should fix soon, and Optional?
* Are proposed tests scoped to the right layer: node, graph, eval, engine, config,
  server, frontend, contract, integration, end-to-end, or documentation/CI validation?
* Are recommendations careful not to demand brittle tests that lock implementation details unnecessarily?

## Step 4. Look for risks and improvement opportunities

Flag:

* important behavior with no test coverage
* critical failure paths tested only by accident
* tests that only cover happy paths
* graph routing not covered by tests
* stop_reason semantics not locked by tests
* budget behavior not covered
* privacy mode not covered
* user input redaction not covered
* trace safety not covered
* eval harness behavior not covered
* fragile or over-specific tests
* tests that require API keys in safe/default workflows
* mismatches between docs, CI, and actual tests
* server endpoints or failure mappings with no focused tests
* frontend critical states or API-client paths with no Vitest coverage
* frontend/backend contracts enforced on only one side
* generated artifacts that tests may accidentally rely on
* missing regression tests for recent changes

Do not rewrite the architecture.

Do not implement tests.

Do not modify code.

Only review and recommend.

## Step 5. Write test coverage review report

Immediately before the first report write, run this command exactly once:

    date "+%Y-%m-%d %H:%M:%S %z"

Treat the returned timestamp as the only authoritative current local time. Reuse its
`YYYY-MM-DD` portion in the filename and report body. Never infer or copy the date from
model knowledge, conversation history, Git history, existing reports, or filenames. If
the command fails, stop and do not write a report with a guessed date.

Create `docs/roadmap/test-coverage-review/` if needed, then create only the selected
unique report using the filename rule above. Do not overwrite an existing report.

### Conditional report structure

Include report metadata: title `Test Coverage Review`, status `Review`, verified date,
requested focus or `Overall test coverage`, and selected report path.

Always retain this compact core:

1. **Review summary** — give a scope-specific conclusion. Include a test-readiness
   verdict only for an unscoped overall review.
2. **Scope reviewed** — state the requested boundary, included dependencies, and
   explicit exclusions.
3. **Evidence inspected** — list exact implementation, test, configuration,
   documentation, and CI files plus repository commands.
4. **Findings** — for each gap give evidence, regression risk, recommended test,
   suggested layer, priority, and timing; state clearly when no material gap was
   confirmed.
5. **Recommendations or priority** — Must fix / Should fix soon / Optional, using only
   gaps inside scope.
6. **Limitations / not reviewed** — omit unrelated domains or state briefly:
   `Not reviewed because it was outside the requested scope.`
7. **Validation or commands run** — list commands actually run and prohibited
   validation that did not run.

Add domain-specific sections—such as node, graph, engine, config, server/API,
frontend, frontend/backend contract, security/privacy, failure and cancellation
behavior, eval harness,
unit/integration/contract/end-to-end placement, mocked versus real dependencies,
Vitest, TypeScript type checking, Vite build, Python selection, markers, or CI
execution—only when relevant to the requested focus and evidence actually inspected.
Do not add a general architecture, security, reliability, or documentation verdict,
fill unrelated sections speculatively, or expand the scan merely to avoid writing
`Not reviewed`.

## Step 6. Final response

After writing the report, respond with:

Test coverage review report: `<selected unique report path>`

Scope conclusion: `<scope-specific conclusion>`

Top coverage gaps:

* <gap 1>
* <gap 2>
* <gap 3>

Do not repeat the full report in chat unless the user explicitly asks. For a focused
review, do not present the conclusion as a repository-wide test-readiness verdict.
