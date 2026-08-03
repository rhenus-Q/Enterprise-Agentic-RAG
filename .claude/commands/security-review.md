---
description: Review security, prompt-injection, and privacy risks and write a timestamped security review report
argument-hint: Optional review focus, for example "prompt injection" or "web search privacy"
allowed-tools: Read, Write, Glob, Grep, Bash(git status:*), Bash(date:*)
---

You are reviewing the security, prompt-injection, and privacy posture of this Agentic RAG project.

User input: $ARGUMENTS

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

Review whether the current project is secure enough for a production-oriented Agentic RAG / LangGraph system, with special attention to:

* prompt injection
* untrusted retrieved context
* web search privacy
* user input secret handling
* trace/log safety
* `.env` and secret hygiene
* RAG document safety
* the HTTP/API boundary and frontend rendering of API-supplied content
* tool-call boundaries
* security-related test coverage
* production-like privacy risks

Write a new security review report under:

`docs/roadmap/security-review/`

Do not overwrite previous security review reports.

## Step 0. Determine the authoritative date and time

Before the first report write, run this command exactly once:

    date "+%Y-%m-%d %H:%M:%S %z"

Treat the returned timestamp as the only authoritative current local time, and reuse that same value throughout this run. Use its `YYYY-MM-DD` portion consistently for the report filename, the report title, the `Date:` / metadata field, and any generated-date text in the body. Never infer or guess the date from model knowledge, conversation history, Git history, existing reports, or existing filenames, and never copy the date from an existing report. If the command fails, stop and report the failure; do not write a report with a guessed date.

## Report filename rule

Create a unique report filename using this format:

`docs/roadmap/security-review/<YYYY-MM-DD>-<focus-slug>-security-review.md`

Where:

* `<YYYY-MM-DD>` is the verified date from Step 0.

* `<focus-slug>` is derived from `$ARGUMENTS`.

* If `$ARGUMENTS` is empty, use `overall`.

* Convert the focus to a lowercase slug:

  * trim whitespace
  * replace spaces with hyphens
  * remove quotes
  * remove characters that are unsafe for filenames
  * keep only letters, numbers, and hyphens where possible

* If `$ARGUMENTS` is not empty but sanitizing it produces an empty slug, use `overall`.

Examples:

* `/security-review` writes to something like:
  `docs/roadmap/security-review/2026-06-24-overall-security-review.md`

* `/security-review prompt injection` writes to something like:
  `docs/roadmap/security-review/2026-06-24-prompt-injection-security-review.md`

* `/security-review web search privacy` writes to something like:
  `docs/roadmap/security-review/2026-06-24-web-search-privacy-security-review.md`

* `/security-review ??` and `/security-review !!!` sanitize to an empty slug, so they use `overall`:
  `docs/roadmap/security-review/2026-06-24-overall-security-review.md`

Before writing, select the report path by checking candidate paths for existence in order and using the first candidate that does not already exist:

1. the base filename `docs/roadmap/security-review/<YYYY-MM-DD>-<focus-slug>-security-review.md`
2. then `docs/roadmap/security-review/<YYYY-MM-DD>-<focus-slug>-security-review-2.md`
3. then `docs/roadmap/security-review/<YYYY-MM-DD>-<focus-slug>-security-review-3.md`
4. continue incrementing the numeric suffix until a candidate path does not exist

Check each candidate with `Glob` or an equivalent path-existence check before selecting it.

Do not overwrite any existing security review report.

Use `Write` only for the selected unique report file.

Do not write any other file.

If the user provides a focus in `$ARGUMENTS`, prioritize that focus while still checking the overall security posture.

## Step 1. Read minimal project context

Read:

* `CLAUDE.md`
* `README.md`
* `structure.md`

Run:

```powershell
git status --short
```

Use the authoritative date from Step 0 for the report filename and body; do not use any other date source.

Then inspect only security-relevant files.

Prefer targeted reads over broad file reading.

## Step 2. Inspect security-relevant areas

Inspect these areas as needed.

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

### Web/API layer and frontend boundary

* `server/app.py`
* `server/schemas.py`
* `server/runs.py`
* `server/status.py`
* `server/documents.py`
* `frontend/src/api/client.ts`
* `frontend/src/api/types.ts`
* `frontend/src/components/CitationList.tsx`
* `frontend/src/components/AnswerCard.tsx`

Inspect frontend files only where they build request payloads or render
API-supplied content. Do not review frontend styling or layout.

### Eval and tests

* `evals/run_eval.py`
* `evals/questions.jsonl`
* `evals/README.md`
* `tests/node/`
* `tests/graph/`
* `tests/evals/`
* `tests/server/`

Inspect `tests/chains/` only if needed to assess security test coverage.

Do not run `tests/chains/`.

### Tooling and project hygiene

* `pyproject.toml`
* `.github/workflows/ci.yml`
* `.gitignore`
* `frontend/package.json`
* `frontend/vite.config.ts`
* `ingestion.py`

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

### Web/API boundary and frontend rendering safety

* Does the HTTP layer validate and bound request input before it reaches the engine?
* Are error responses sanitized so configuration values, exception messages, file paths, and secrets never reach the client?
* Is the run history metadata-only and bounded?
* Are citation URLs scheme-validated before crossing the HTTP boundary and being rendered as links?
* Does the frontend render API-supplied answer text, titles, and URLs without creating an injection or link-based exfiltration path?
* Do privacy mode and local mode hold across the HTTP path, including per-request overrides?
* Is the optional `frontend/dist` static mount scoped so it cannot expose unintended files?
* Does the API layer import graph nodes/chains or construct an external client, contrary to its documented boundary?
* Are cancellation and concurrent-run rejection free of information leakage?

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

### Tool-call boundaries

* Are dangerous operations — full eval, ingestion, and API-key workflows —
  blocked by default in the runtime and eval paths?
* Are generated reports and artifacts written only to intended paths?

Claude command files under `.claude/commands/` are out of scope here: their
frontmatter, tool-permission breadth, and write scoping belong to
`/review-command`.

### Security test coverage

Check only whether each security guarantee this report relies on is locked by
*some* test at all — redaction, privacy mode, web-search-disabled, trace
metadata-only, and API error sanitization.

Do not produce a coverage-gap inventory — `/test-coverage-review` owns that.

## Step 4. Look for risks and improvement opportunities

Flag:

* raw user input reaching GraphState, LLMs, or web search
* secrets stored in AnswerResult, raw_state, trace, eval history, or reports
* prompt injection weaknesses in generation, grading, routing, or query rewriting
* untrusted web results entering generation without filtering
* privacy mode bypasses
* fallback policy confusion
* logging or trace leakage
* `.env` or generated artifact hygiene problems
* unsanitized HTTP error responses that echo configuration values, exception messages, or filesystem paths
* API responses or run-history records carrying answer text, document content, or raw state
* citation URLs reaching the frontend without scheme validation
* an API layer that imports graph nodes/chains or constructs its own external client
* missing security tests
* stale docs that overstate security guarantees
* areas where the project looks secure by accident rather than by design

Do not rewrite the architecture.

Do not implement fixes.

Only review and recommend.

## Step 5. Write security review report

Create a new unique report file using the filename rule above.

Do not overwrite an existing security review report.

Use this structure:

# Security Review

Status: Review

Date: <YYYY-MM-DD>

Focus: <user input or "Overall security">

Report file: <selected unique report path>

## 1. Executive summary

State whether the security posture is:

* Strong / production-oriented
* Good but needs minor cleanup
* Needs significant improvement

Give a short explanation.

## 2. Files reviewed

List the files and directories reviewed.

## 3. Security map

Briefly describe the current security-relevant flow:

* User input handling
* Secret redaction
* GraphState boundary
* Local retrieval boundary
* Web search boundary
* Prompt / chain boundary
* HTTP/API boundary
* Frontend rendering boundary
* Trace and logging boundary
* Eval and test boundary

## 4. What is strong

List the strongest security choices.

## 5. Main issues found

For each issue include:

* Issue
* Why it matters
* Risk level: Low / Medium / High
* Recommended fix
* Whether it should be done now or later

## 6. Prompt injection review

Assess:

* generation prompt
* retrieved-context treatment
* web result treatment
* grader prompts
* router prompt
* query rewriter prompt
* retry feedback path
* whether untrusted content can override trusted instructions

## 7. Privacy review

Assess:

* user input redaction
* original question storage
* web search privacy mode
* fallback policy interaction
* outbound web query safety
* trace privacy
* eval history privacy
* generated artifact privacy

## 8. Secret handling review

Assess:

* `.env`
* `.env.example`
* API key handling
* token/password redaction
* question hashing
* AnswerResult fields
* raw_state risks
* CI secret usage
* accidental commit risks

## 9. Web search and external dependency review

Assess:

* Tavily/web search boundary
* search query construction
* web result grading
* web source metadata
* failed web search behavior
* external service failure handling
* privacy implications

## 10. Web/API boundary and frontend review

Assess:

* request validation and input bounds
* error-response sanitization
* run history contents and bounds
* citation URL scheme validation
* frontend rendering of API-supplied answers, titles, and URLs
* privacy-mode enforcement across the HTTP path
* static-mount exposure
* whether the documented `server/` import boundary holds

## 11. Trace and observability safety review

Assess:

* trace JSON contents
* metadata-only guarantees
* question preview redaction
* question hash correlation
* node_path and timing safety
* counter safety
* trace write failure behavior
* whether any observability artifact could leak secrets

## 12. Security test coverage review

State, per security guarantee claimed in this report, whether a test locks it —
yes or no. Keep this to a list of guarantees, not a coverage audit.

Refer gap analysis to `/test-coverage-review`.

## 13. Documentation review

Assess only whether security behavior is documented clearly and not overstated.

General documentation accuracy belongs to `/docs-drift-review`; Claude command
safety belongs to `/review-command`.

## 14. Recommended next actions

Separate recommendations into:

### Must fix

### Should fix soon

### Optional improvements

## 15. Security-readiness verdict

Give one of:

* Security-ready / production-oriented
* Security-ready after minor cleanup
* Not security-ready yet

Explain why.

## 16. Overall recommendation

Do not restate the executive summary or the security-readiness verdict here.

Instead, give a short, action-oriented recommendation that answers:

* Is the security posture safe to continue building on?
* Is cleanup needed before adding more features?
* What is the single next recommended action?

## Step 6. Final response

After writing the report, respond with:

Security review report: `<selected unique report path>`

Overall recommendation: `<overall recommendation>`

Top issues:

* <issue 1>
* <issue 2>
* <issue 3>

Do not repeat the full report in chat unless the user explicitly asks.
