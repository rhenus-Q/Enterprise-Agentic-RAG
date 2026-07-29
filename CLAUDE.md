# CLAUDE.md

Guidance for Claude Code when working in this repository.

## 1. Project Overview

An **enterprise internal-document Q&A assistant** built with **LangGraph**, implementing a
self-correcting Agentic RAG (CRAG-style) workflow. It answers questions from an ingested
knowledge base and falls back to web search when needed.

**Stack:** LangGraph, LangChain, OpenAI (`gpt-5-mini`, `OpenAIEmbeddings`), Chroma (vector
store), Tavily (web search). Managed with **uv**. An optional local provider mode
(`LLM_PROVIDER=ollama` or `FULLY_LOCAL_MODE=true`) routes every LLM and embedding call to an
Ollama-compatible endpoint instead; OpenAI remains the default and primary provider.

**High-level flow** (see `structure.md` for details):

```
question
→ route_question
    ├── websearch → generate
    └── retrieve → grade_documents
            ├── relevant docs → generate
            └── no relevant docs → websearch → generate
generate
→ grounding check (hallucination_grader)
    ├── not grounded → add grounding feedback → regenerate
    └── grounded → usefulness check (answer_grader)
            ├── useful → END
            └── not useful → rewrite search query → websearch
```

Three quality gates: **document relevance**, **answer grounding** (anti-hallucination), and
**answer usefulness**. A `retries` counter in state caps the regenerate/websearch loop at
`MAX_RETRIES = 5` (defined in `graph/graph.py`).

External dependency failures (retriever, Tavily, generation LLM, graders, query rewriter)
never crash the graph: each call site catches the exception, degrades or stops safely, and
records a `stop_reason` (`retrieval_error`, `web_search_error`, `generation_error`,
`tool_error`) so `main.py` appends an honest caveat. Console banners log only the exception
type, never the message.

## 2. Project Structure

| Path | Purpose |
|------|---------|
| `main.py` | CLI entry point. Loads `.env`, then runs an interactive Q&A loop over `graph.engine.answer_question()`. Re-exports the `graph/formatting.py` names (`format_answer`, `format_sources`, caveat notes) for backward compatibility. Also owns `run_startup_preflight()` — mode/provider validation plus the local-mode endpoint, installed-model, and index-fingerprint checks — which runs *before* the graph and raises `PreflightError`; `evals/run_eval.py` reuses it rather than duplicating the logic. Preflight lives outside the graph on purpose: ADR 006 requires in-graph failures to degrade rather than crash, so a node could only turn a misconfiguration into a generic `*_error` whose message is discarded. |
| `graph/engine.py` | Canonical programmatic API: `answer_question(question, options) -> AnswerResult`, `AnswerOptions` (per-run `web_search_enabled` / `web_fallback_policy` / `run_id` / `trace_path` / `cancel_event` overrides; `None` = env default), and `seed_state()` — the single state-seeding helper shared by CLI, evals, and tests. Also owns cooperative cancellation (ADR 016): when `AnswerOptions.cancel_event` (a `threading.Event`) is set from another thread, `_run_graph_with_trace()` stops at the next streamed node boundary and raises `RunCancelled` instead of returning — no `AnswerResult`, no `stop_reason`, no trace file, nothing to record. Latency is one node; nothing pre-empts a call already in flight, and the `invoke()` fallback path is not cancellable. Only `server/app.py` passes a `cancel_event`; CLI and eval runs leave it `None` and are unaffected. Also owns the lightweight observability: every run gets a `run_id`, the executed `node_path` + per-step timings + `total_duration_ms` are collected by streaming graph updates (additive — merging the updates reproduces `invoke()`), and `trace_path` optionally writes a metadata-only trace JSON (never `page_content`, prompts, raw state, or keys). Also applies input redaction: secret-like values in the question are replaced with `[REDACTED]` before it enters `GraphState`, with `question_sha256` (hash of the original) and `input_redacted` on `AnswerResult` for correlation. |
| `graph/formatting.py` | Shared presentation: `stop_reason` caveats (`STOP_REASON_NOTES`) plus the deterministic `Sources:` section built from `Document` metadata (`format_answer` / `format_sources` / `source_lines`; local corpus vs. `web_search` supplement). Pure — no clients, no env reads. |
| `ingestion.py` | Builds the knowledge base: loads the local Markdown corpus from `data/acmecorp_internal_docs/`, splits, embeds, persists to Chroma (idempotent: collection reset + deterministic chunk ids; provenance metadata `source`/`title`/`source_type`/`document_category`). Exposes `get_retriever()` (lazy, `@lru_cache`). Run once before `main.py`. `get_embeddings()` and the index location are provider-scoped: OpenAI keeps `chroma_db/` / `agentic_rag_docs`, local mode uses `chroma_db_local/` / `agentic_rag_docs_local`, and the idempotent-rebuild `delete_collection()` is scoped to the active provider so neither ingest destroys the other's index. Each index carries an `embedding_fingerprint.json` sidecar (provider + model) checked at startup; a missing fingerprint means legacy-OpenAI. Switching between two already-built matching indexes needs no re-ingestion. |
| `data/acmecorp_internal_docs/` | Synthetic AcmeCorp enterprise corpus: 6 fictional internal Markdown documents (VPN, expenses, incident response, on-call, data retention, onboarding). No real company data — safe to edit/extend. |
| `graph/graph.py` | Assembles the LangGraph `StateGraph`, wires nodes + conditional edges, exports compiled `app`. Holds `MAX_RETRIES` and the routing decision functions. |
| `graph/state.py` | `GraphState` TypedDict: `question`, `documents`, `generation`, `web_search`, `web_search_enabled`, `web_fallback_policy` (resolved per run by the engine; graph decisions read it from state), `retries`, `stop_reason`, `insufficient_context`, `retry_feedback`, `search_query`, plus budget counters (`llm_call_count`, `web_search_count`, `web_result_grading_count`). |
| `graph/config.py` | Env-driven runtime flags: `web_search_enabled()` (privacy mode), `web_fallback_policy()` / `normalize_web_fallback_policy()` (conservative/aggressive/disabled, default conservative; the env var is the *default source* — the engine resolves the effective policy into per-run state), the per-run budgets `max_llm_calls_per_run()` / `max_web_searches_per_run()` / `max_web_results_to_grade()`, and the per-request LLM timeout `llm_request_timeout_seconds()` (`LLM_REQUEST_TIMEOUT_SECONDS`, default 60s; wired into all six chains). Also the deployment-mode readers `privacy_mode()` / `fully_local_mode()` (`PRIVACY_MODE` / `FULLY_LOCAL_MODE`, default off) and the provider readers `llm_provider()` / `local_mode_enabled()` / `local_chat_model()` / `local_embedding_model()` / `ollama_base_url()`. These mode and provider variables **fail loudly** (`ValueError`) on an unparseable or contradictory value instead of falling back the way `normalize_web_fallback_policy()` does — a misread privacy intention means silent third-party egress, not a benign variation. |
| `graph/consts.py` | Node-name string constants (`RETRIEVE`, `GRADE_DOCUMENTS`, `GENERATE`, `WEBSEARCH`, `WEB_SEARCH_DISABLED_NOTICE`) and `stop_reason` values. |
| `graph/nodes/` | Graph node functions: `retrieve`, `grade_documents`, `generate`, `web_search`, retry helpers (`add_grounding_feedback`, `rewrite_query`), plus terminal notice nodes (`web_search_disabled_notice`, `web_fallback_disabled_notice`, `max_retries_not_grounded_notice`, `max_retries_not_useful_notice`, `budget_exhausted_notice`, `tool_error_notice`) that record `stop_reason`, and `clear_transient_tool_error` (success-path pass-through: clears a stale transient `tool_error` once both gates pass). |
| `graph/chains/` | LCEL chains: `generation`, `retrieval_grader`, `question_router`, `hallucination_grader`, `answer_grader`, `query_rewriter`. Each exposes a lazy `get_*()` factory. `_llm.py` holds the single shared `get_chat_model()` that all six use, so the model name, `temperature=0`, and the request timeout live in one place rather than six. |
| `tests/node/` | Unit tests for node functions. Fully mocked — no API keys needed. |
| `tests/graph/` | Routing / privacy-toggle / compiled-graph tests. Fully mocked — no API keys needed. |
| `tests/chains/` | Integration tests for the chains. Call the real `gpt-5-mini` — need `OPENAI_API_KEY`. |
| `tests/evals/` | Mocked unit tests for the eval harness's pure helpers (validation, checks, metrics, rendering). No API keys needed. |
| `evals/` | Behavioral eval harness: `questions.jsonl` (24-row dataset with multi-document and fallback-policy rows; optional per-row `web_fallback_policy`, source-title, min-local-source, and web-search-count checks), `run_eval.py` (runs the real graph via `graph.engine.answer_question()` — **never run the full eval without explicit approval**; `--validate-only` is safe), `results.md` (generated report). Each full run also writes a metadata-only JSON history record and renders a "Delta vs. previous run" section in the report. `--validate-only` must stay keys-free and dependency-free: it returns before the graph is imported *and* before startup preflight runs, so it keeps working with no API keys and no local endpoint. Not part of CI. |
| `evals/history/` | Append-only, metadata-only eval history records (one JSON per full run; never answer text, `page_content`, prompts, or raw state). The harness only writes new records — never edits/deletes. `evals/history/*.json` is gitignored by default (the dir is tracked via `.gitkeep`); force-add (`git add -f`) to share a known-good baseline. |
| `docs/adr/` | Architecture Decision Records (001–015) with an index in `docs/adr/README.md`. When a documented decision changes, update or supersede the matching ADR. |
| `docs/roadmap/` | **Local-only process artifacts** — gitignored by default (see `docs/roadmap/README.md`). Only four files are tracked: `docs/roadmap/README.md`, `spec/spec-template.md`, `plan/plan-template.md`, and `implementation/implementation-template.md`. Everything else (specs, plans, implementation reports, and all review reports) stays on the local machine and is never committed. Layout: `spec/`, `plan/`, `implementation/`, `commands-review/`, plus per-topic `<topic>-review/` dirs (e.g. `architecture-review/`, `security-review/`, `failure-modes-review/`, `test-coverage-review/`). Specs/plans/reports use a short feature slug. `docs/roadmap/<topic>-review/` is the convention for timestamped reports from project-level `<topic>-review` commands (architecture, security, failure-modes, test-coverage); these use dated `<YYYY-MM-DD>-<focus-slug>-<topic>-review.md` collision-safe filenames and must not overwrite prior reports. `docs/roadmap/commands-review/` remains for command-file review reports (e.g. `/review-command`). |
| `.claude/commands/` | Claude Code slash-command workflow files (spec → plan → implement → review-diff; plus `arch-review`, command-authoring/review, and `update-claude-md`). Each has YAML frontmatter (`description`, `argument-hint`, `allowed-tools`); keep `allowed-tools` minimal and scoped (e.g. `Bash(git status:*)`, not blanket `Bash`). |
| `tests/conftest.py` | Loads `.env` before collection; provides the `requires_openai` skip marker; and clears the mode/provider env vars (`PRIVACY_MODE`, `FULLY_LOCAL_MODE`, `LLM_PROVIDER`, `LOCAL_CHAT_MODEL`, `LOCAL_EMBEDDING_MODEL`, `OLLAMA_BASE_URL`) via an autouse fixture, so a developer's `.env` can never decide what the mocked suites assert. |
| `pyproject.toml` | uv project config: deps, `[dependency-groups] dev` (pytest, ruff, mypy, pre-commit), `[tool.pytest.ini_options]`, `[tool.ruff]`/`[tool.ruff.lint]`/`[tool.ruff.lint.per-file-ignores]`, and `[tool.mypy]`/`[[tool.mypy.overrides]]`. |
| `.gitattributes` | Line-ending policy: `text=auto` + explicit `*.py/md/yml/yaml/toml/json text` rules to prevent CRLF churn on Windows working copies. |
| `.pre-commit-config.yaml` | Local hooks mirroring CI: `ruff-check --fix`, `ruff-format`, and basic hygiene hooks (`trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-toml`, `check-added-large-files`, `check-merge-conflict`). |

## 3. Development Rules

- **Preserve behavior by default.** Do not change graph routing, `GraphState` schema, prompts,
  model names (`gpt-5-mini`), `temperature=0`, chain input variables, or node return
  structures unless explicitly asked.
- **No broad architecture changes.** Avoid restructuring the graph or rewriting modules wholesale.
- **`GraphState` fields are plain last-value channels.** Do not add `typing.Annotated` reducers /
  accumulating channels: `graph/engine.py` merges streamed node updates with `dict.update()`, which
  only reproduces `app.invoke()` for last-value channels. If a reducer is ever needed, revisit that merge first.
- **Refactors should be small, mechanical, and reviewable.** Prefer minimal diffs.
- **Lazy external clients (required pattern).** `ChatOpenAI`, `OpenAIEmbeddings`,
  `TavilySearch` (`langchain-tavily`), `Chroma`, `ChatOllama` / `OllamaEmbeddings`
  (`langchain-ollama`), retrievers, and any API-backed tool must be constructed
  inside a lazy factory — use `@lru_cache(maxsize=1) def get_x(): ...` — never at module level.
  Import the optional local-provider classes *inside* their factory, so the default OpenAI
  path keeps working where `langchain-ollama` is absent.
- **All six chains obtain their model from `graph/chains/_llm.py::get_chat_model()`.** No chain
  module may construct a provider client itself — a stray `ChatOpenAI(...)` there would keep
  sending traffic to OpenAI in local mode. Provider choice is process-level: never per-chain,
  never per-run (`get_retriever()` is cached and bound to one embedding space).
- **The privacy lock lives in `graph/engine.py::seed_state()`.** `PRIVACY_MODE=true` and local
  mode force `web_search_enabled=False` *after* the per-run resolution, so an explicit
  `AnswerOptions(web_search_enabled=True)` cannot reopen web search or LangSmith export. Do not
  fold this into `config.web_search_enabled()`, which a per-run option bypasses entirely —
  moving it would silently downgrade the lock to a default. `WEB_SEARCH_ENABLED` deliberately
  stays a per-run-overridable default, which is how the eval harness runs privacy rows and
  web rows in the same process.
- **Cancellation adds no `stop_reason` value.** A cancelled run raises
  `graph.engine.RunCancelled` and produces no `AnswerResult`; it is abandoned, not
  degraded. `stop_reason` describes how the *graph* ended and is shared vocabulary across
  nodes, `STOP_REASON_NOTES`, the run store, and the evals — do not add a value there for a
  caller's decision to stop (ADR 016). Cancellation checks belong at the streamed node
  boundary in `_run_graph_with_trace()`; do not add them inside nodes or chains.
- **Imports must be side-effect-free.** Importing any module (`graph.graph`, `graph.nodes.*`,
  `graph.chains.*`, `ingestion`) must NOT require API keys or network, and must NOT construct
  any external client.
- **Backward-compatible chain names.** Chain modules expose `get_*()` factories; old
  module-level names (e.g. `generation_chain`, `question_router`) remain available via a lazy
  module-level `__getattr__`. Don't reintroduce eager module-level chain objects.
- Code comments/docstrings are written in **English**.

## 4. Testing Rules

- **Unit tests mock all external dependencies** via `monkeypatch`, targeting the lazy seam
  (e.g. patch `get_node_retriever`, `get_web_search_tool`, `get_retrieval_grader`,
  `generate_answer`).
- **Node tests (`tests/node/`) must never call real OpenAI, Tavily, Chroma, or embeddings.**
  They must pass with no API keys.
- **Integration tests (`tests/chains/`) call real services** and require `OPENAI_API_KEY`.
  Label such tests clearly and gate them with the `requires_openai` marker from `conftest.py`.
- **Mode/provider env vars are cleared per test** by the autouse fixture in
  `tests/conftest.py`. A test that needs one sets it explicitly with `monkeypatch`, and must
  `.cache_clear()` any `@lru_cache`'d factory it then calls (`get_chat_model`, `get_retriever`,
  the six chain factories) or it will observe a client built under the previous environment.
- **Do not run tests unless explicitly asked.** Writing tests ≠ running them.

## 5. Claude Code Behavior Rules

- **Plan first.** Before changing files, explain the plan and list every file to be changed and why.
- **Summarize after.** After editing, provide a diff summary.
- **Don't run commands without explicit approval** — no `pytest`, `python -c`, `py_compile`, or
  any code-executing command unless the user asks. Provide commands for the user to run instead.
- **Stop and ask** before any change that may affect business logic, graph routing, prompt
  behavior, model behavior, or the state schema.
- **Tests-only tasks:** when the request is only to write tests, prefer asking before touching
  production code; make the smallest safe change if a seam is genuinely needed for testability.

## 6. Common Commands

> These are for **the user to run manually**. Claude Code should not execute them without approval.

```powershell
# Always work from the project root
cd "<your-local-repo-path>"

# Set up the environment (creates .venv, writes uv.lock)
uv sync --group dev

# Install local pre-commit hooks (one-time per clone)
uv run pre-commit install

# Build the Chroma index (one-time, before first run)
uv run python ingestion.py

# Run the assistant
uv run python main.py

# Node unit tests — fully mocked, NO API keys required
uv run pytest tests/node/ -v

# Chain integration tests — real gpt-5-mini, needs OPENAI_API_KEY
uv run pytest tests/chains/ -v

# Whole suite
uv run pytest -v

# Dev hygiene (mirrors the CI lint job — run before committing)
uv run ruff check .                  # lint
uv run ruff check --fix .            # lint + safe autofixes
uv run ruff format .                 # format
uv run ruff format --check .         # format check (CI mode)
uv run mypy                          # type-check scoped modules only

# Run all pre-commit hooks across every file (equivalent to what runs on commit)
uv run pre-commit run --all-files

# Syntax-only check (no test execution)
$files = @(
    "graph/graph.py",
    "graph/nodes/generate.py",
    "graph/nodes/retrieve.py",
    "graph/nodes/web_search.py",
    "graph/nodes/grade_documents.py",
    "graph/chains/_llm.py",
    "graph/chains/generation.py",
    "graph/chains/retrieval_grader.py",
    "graph/chains/question_router.py",
    "graph/chains/hallucination_grader.py",
    "graph/chains/answer_grader.py",
    "graph/chains/query_rewriter.py",
    "ingestion.py",
    "main.py"
)

uv run python -m py_compile $files

# Verify imports construct no clients and need no keys
uv run python -c "import graph.graph, graph.nodes, graph.chains, ingestion; print('IMPORT OK')"
```
