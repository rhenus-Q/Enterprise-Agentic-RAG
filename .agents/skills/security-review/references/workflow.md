# Detailed Workflow

This reference contains the detailed project-specific procedure for the Skill. The Skill metadata and execution boundary in `SKILL.md` remain authoritative.

## Contents

- Goal
- Focus is a hard boundary
- Report filename rule
- Step 1. Read minimal project context
- Step 2. Inspect security-relevant areas
- Step 3. Review security quality
- Step 4. Look for risks and improvement opportunities
- Step 5. Write security review report
- Conditional report structure
- Step 6. Final response

You are reviewing the security, prompt-injection, and privacy posture of this Agentic RAG project.

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

Do not run tests.

Do not run `tests/chains/`.

Do not run API-key-requiring commands.

Do not commit.

Do not create or switch branches.

Use as few tools as possible.

## Goal

Primary question:

> Are the trust boundaries, data handling, permissions, secrets, and external
> interactions secure for the requested scope?

Review security and privacy risks for the requested scope, with special attention to:

* prompt injection
* untrusted retrieved context
* web search privacy
* user input secret handling
* trace/log safety
* `.env` and secret hygiene
* RAG document safety
* tool-call boundaries
* authentication and authorization when present
* regression evidence for security-critical guarantees
* fail-open behavior with security consequences

Write a new security review report under:

`docs/roadmap/security-review/`

Do not overwrite previous security review reports.

## Report filename rule

Create a unique report filename using this format:

`docs/roadmap/security-review/<YYYY-MM-DD>-<focus-slug>-security-review.md`

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

* ``$security-review`` writes to something like:
  `docs/roadmap/security-review/2026-06-24-overall-security-review.md`

* `$security-review prompt injection` writes to something like:
  `docs/roadmap/security-review/2026-06-24-prompt-injection-security-review.md`

* `$security-review web search privacy` writes to something like:
  `docs/roadmap/security-review/2026-06-24-web-search-privacy-security-review.md`

* `$security-review ??` and `$security-review !!!` sanitize to an empty slug, so they use `overall`:
  `docs/roadmap/security-review/2026-06-24-overall-security-review.md`

Before writing, select the report path by checking candidate paths for existence in order and using the first candidate that does not already exist:

1. the base filename `docs/roadmap/security-review/<YYYY-MM-DD>-<focus-slug>-security-review.md`
2. then `docs/roadmap/security-review/<YYYY-MM-DD>-<focus-slug>-security-review-2.md`
3. then `docs/roadmap/security-review/<YYYY-MM-DD>-<focus-slug>-security-review-3.md`
4. continue incrementing the numeric suffix until a candidate path does not exist

Check each candidate with a path-existence check before selecting it.

Do not overwrite any existing security review report.

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
repository-wide scan, produce an overall security-readiness verdict, or populate
unrelated report sections. When no focus is supplied, the broader default security
review may remain.

## Step 1. Read minimal project context

Always read `AGENTS.md`. For an unscoped review, also read `README.md` and
`structure.md`. For a focused review, read those documents only when they contain a
directly relevant security promise or boundary claim.

Run:

```powershell
git status --short
```

Then inspect only files permitted by the focus boundary.

Prefer targeted reads over broad file reading.

## Step 2. Inspect security-relevant areas

Inspect these areas only when allowed by the focus boundary. For an unscoped review,
consider them as needed; do not read every listed area mechanically.

### Security-sensitive runtime files

* `graph/engine.py`
* `graph/config.py`
* `graph/consts.py`
* `graph/formatting.py`
* `graph/state.py`
* `graph/graph.py`

### Prompt and chain files

* `graph/chains/generation.py`
* `graph/chains/retrieval_grader.py`
* `graph/chains/hallucination_grader.py`
* `graph/chains/answer_grader.py`
* `graph/chains/query_rewriter.py`
* `graph/chains/question_router.py`

### Node files and external boundaries

* `graph/nodes/retrieve.py`
* `graph/nodes/grade_documents.py`
* `graph/nodes/generate.py`
* `graph/nodes/web_search.py`
* `graph/nodes/rewrite_query.py`
* `graph/nodes/add_grounding_feedback.py`
* `graph/nodes/clear_transient_tool_error.py`
* `graph/nodes/*notice*.py`

### API and browser files

* `server/`, with emphasis on request validation, response construction, exception
  mapping, runtime status, metadata-only run history, cancellation, and static serving
* `frontend/src/api/`, including the client, mirrored types, and mock boundary
* Frontend pages and components that render answers, citations, errors, runtime status,
  document metadata, or run details
* `frontend/package.json`, `frontend/package-lock.json`, `frontend/vite.config.ts`,
  `frontend/tsconfig.json`, and `frontend/index.html` when relevant to dependency,
  build, proxy, or browser security

Inspect the contracts between `server/schemas.py` and `frontend/src/api/types.ts`, API
routes and `frontend/src/api/client.ts`, and FastAPI's optional `frontend/dist` mount.
Do not inspect generated `frontend/dist/` contents.

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

Use tests only as regression evidence for security-critical guarantees. The Skill may
report that a security guarantee lacks evidence, but it must not construct a complete
test inventory or coverage map. Inspect `tests/chains/` only if the user explicitly
places it in scope.

Do not run `tests/chains/`.

### Tooling and project hygiene

* `pyproject.toml`
* Discover relevant CI workflows only through `.github/workflows/*.yml` and
  `.github/workflows/*.yaml`; do not assume one filename is authoritative.
* `.gitignore`
* `ingestion.py`

Do not inspect `.agents/skills/**` by default. Inspect it only when the focus concerns
tool or agent permissions, Skill files are part of the reviewed change, or the user
explicitly requests a Skill security review.

Do not run `ingestion.py`.

Do not inspect `.env`.

Do not inspect `.env.example` unless needed to assess whether it contains placeholders rather than real secrets.

Do not inspect corpus documents broadly. Only inspect corpus metadata or filenames if needed for security review.

Do not inspect generated runtime artifacts unless needed.

## Step 3. Review security quality

Evaluate the following areas.

### User input secret handling

* Are user-provided secret-like values redacted before entering GraphState?
* Can API keys, tokens, passwords, or secrets reach retrievers, graders, generators, routers, query rewriters, or web search queries?
* Is the original user input stored anywhere after redaction?
* Is a safe hash used for correlation instead of storing raw input?
* Is the redaction best-effort behavior clearly documented?
* Are there obvious secret patterns missing from the redaction rules?
* Does redaction avoid breaking ordinary user questions unnecessarily?

### Prompt injection defense

* Do generation prompts clearly treat retrieved documents as untrusted context?
* Do prompts instruct the model not to follow instructions inside retrieved documents or web results?
* Are system/developer instructions separated from retrieved context?
* Are context delimiters clear enough?
* Could malicious retrieved content override the system prompt?
* Could retrieved content cause tool execution, data exfiltration, secret disclosure, or policy bypass?
* Are graders or routers vulnerable to prompt injection through user question, document text, or web result content?
* Are retry feedback and query rewriting prompts safe against malicious previous answers or documents?

### RAG document and web result safety

* Are retrieved local documents graded before generation?
* Are web search results treated as untrusted?
* Are web results relevance-graded before entering generation?
* Are ungraded or failed-grade web results excluded?
* Are web supplement documents marked clearly with metadata?
* Could web result content inject instructions into downstream generation?
* Are raw URLs/titles handled safely in sources?
* Is there any risk of mixing trusted local corpus with untrusted web content without metadata?

### Privacy and web search controls

* Is `web_search_enabled=False` a hard privacy guarantee?
* Can user input be sent to external web search when privacy mode is disabled?
* Are fallback policies separate from the global web-search privacy switch?
* Are web fallback decisions explicit and testable?
* Does secret redaction happen before outbound web queries?
* Is the search query derived safely from user input and rewritten query state?
* Are web search counts and limits enforced?
* Are privacy risks documented clearly enough?

### API and browser boundaries

* Does FastAPI validate and bound user-controlled request data before calling the
  engine?
* Are exception responses and runtime-status diagnostics sanitized so configuration,
  paths, documents, prompts, and secrets are not disclosed?
* Are run history and citations limited to the intended metadata and snippets?
* Are cancellation and single-flight state isolated safely between requests?
* Does the frontend render untrusted answer, citation, error, and run data without
  unsafe HTML or URL handling?
* Are mock mode, the Vite proxy, and the production static mount explicit boundaries
  that cannot silently weaken runtime security?
* Do frontend API types stay aligned with server response schemas so security-relevant
  fields are not ignored or misinterpreted?

### Trace, logging, and artifact safety

* Are trace files metadata-only?
* Are raw documents, prompts, raw graph state, user secrets, and API keys excluded from trace output?
* Are trace question previews redacted and truncated?
* Is the original question hash safe enough for correlation?
* Are trace write failures handled without exposing exception messages that might contain paths or secrets?
* Are eval history files metadata-only?
* Are generated reports safe to commit or clearly ignored when appropriate?
* Is there any direct printing of raw state, document content, prompt content, or secrets?

### `.env`, secret, and repository hygiene

* Is `.env` ignored?
* Does `.env.example` avoid real secrets?
* Are API keys avoided in committed files?
* Are vector stores, generated traces, runtime outputs, and local artifacts ignored where appropriate?
* Does CI avoid requiring real API keys by default?
* Are API clients lazy-loaded to avoid import-time secret requirements?
* Are error messages careful not to print secret values?

### Tool-call and command boundaries

Review these boundaries only when tool or agent permissions are in scope or directly
affect the reviewed security boundary.

* Do Codex Skills use narrow tool permissions?
* Do review commands avoid modifying code unless explicitly intended?
* Are dangerous commands, full eval, ingestion, and API-key workflows blocked by default?
* Are there overly broad Bash grants?
* Are generated reports written only to intended report paths?
* Is command behavior safe if the working tree is dirty?

### Regression evidence for security-critical guarantees

When directly relevant, determine whether the security guarantee has regression
evidence, such as a focused mocked test, contract test, or eval row. Report the absent
evidence as a security risk modifier, for example: `The security guarantee lacks
regression evidence.` Do not inventory unrelated suites, prescribe complete test
placement, or assess repository-wide coverage; that belongs to
`test-coverage-review`.

Failure handling is in scope only when it has a security effect, such as fail-open
behavior, privacy bypass, secret leakage, unintended external transmission, or
authorization bypass. Generic retry, timeout, cancellation, degradation, and recovery
correctness belongs to `failure-modes-review`.

Documentation is evidence only for directly relevant security, privacy, permission,
secret, or egress promises. Do not perform a general documentation-drift audit.

Do not turn this workflow into a generic implementation-correctness review.

## Step 4. Look for risks and improvement opportunities

Flag:

* raw user input reaching GraphState, LLMs, or web search
* secrets stored in AnswerResult, raw_state, trace, eval history, or reports
* prompt injection weaknesses in generation, grading, routing, or query rewriting
* untrusted web results entering generation without filtering
* privacy mode bypasses
* API validation, error, or status responses that disclose sensitive data
* unsafe browser rendering or URL handling for API-provided content
* frontend/backend contract drift that drops or misclassifies security-relevant fields
* fallback behavior that creates a security or privacy bypass
* logging or trace leakage
* `.env` or generated artifact hygiene problems
* overly broad Codex Skill permissions
* a security-critical guarantee without regression evidence
* directly relevant documentation that overstates a security guarantee
* areas where the project looks secure by accident rather than by design

Do not rewrite the architecture.

Do not implement fixes.

Only review and recommend.

## Step 5. Write security review report

Immediately before the first report write, run this command exactly once:

    date "+%Y-%m-%d %H:%M:%S %z"

Treat the returned timestamp as the only authoritative current local time. Reuse its
`YYYY-MM-DD` portion in the filename and report body. Never infer or copy the date from
model knowledge, conversation history, Git history, existing reports, or filenames. If
the command fails, stop and do not write a report with a guessed date.

Create `docs/roadmap/security-review/` if needed, then create only the selected unique
report using the filename rule above. Do not overwrite an existing report.

### Conditional report structure

Include report metadata: title `Security Review`, status `Review`, verified date,
requested focus or `Overall security`, and selected report path.

Always retain this compact core:

1. **Review summary** — give a scope-specific conclusion. Include a security-readiness
   verdict only for an unscoped overall review.
2. **Scope reviewed** — state the requested boundary, included dependencies, and
   explicit exclusions.
3. **Evidence inspected** — list exact files, directories, and repository commands.
4. **Findings** — for each finding give evidence, security consequence, risk,
   recommended action, and timing; state clearly when no material issue was confirmed.
5. **Recommendations or priority** — Must fix / Should fix soon / Optional, using only
   findings inside scope.
6. **Limitations / not reviewed** — omit unrelated domains or state briefly:
   `Not reviewed because it was outside the requested scope.`
7. **Validation or commands run** — list commands actually run and prohibited
   validation that did not run.

Add domain-specific sections—such as trust boundaries, prompt injection, privacy,
secrets, external egress, browser safety, trace disclosure, tool permissions,
security-effect failure handling, directly relevant security promises, or regression
evidence for security-critical guarantees—only when relevant to the requested focus
and evidence actually inspected. Do not produce a full test-coverage or documentation
section, fill unrelated sections speculatively, or expand the scan merely to avoid
writing `Not reviewed`.

## Step 6. Final response

After writing the report, respond with:

Security review report: `<selected unique report path>`

Scope conclusion: `<scope-specific conclusion>`

Top issues:

* <issue 1>
* <issue 2>
* <issue 3>

Do not repeat the full report in chat unless the user explicitly asks. For a focused
review, do not present the conclusion as a repository-wide readiness verdict.
