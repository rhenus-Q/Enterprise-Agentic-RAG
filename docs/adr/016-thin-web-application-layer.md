# ADR 016: Thin web application layer

Status: Accepted

Date: 2026-07-29

Relates to ADR 006 (graceful degradation), ADR 014 / ADR 015 (provider and
mode flags), and ADR 017 (cooperative run cancellation, which specifies the
cancel endpoint and HTTP 499). None is superseded.

## Context

The project was CLI-only: `main.py` drove an interactive loop over
`graph.engine.answer_question()`, and everything the assistant knew about a run
— the executed node path, per-step timings, the `stop_reason` caveat, the
deterministic `Sources:` lines, the resolved runtime policy — was printed to a
terminal and then lost.

A web surface was wanted for demonstration and review. The risk in adding one
is not the HTTP plumbing; it is that a second entry point quietly becomes a
second implementation. A server that re-reads `PRIVACY_MODE` to decide whether
to show a lock, re-derives fingerprint compatibility, or re-implements the
seeding rules ends up disagreeing with the CLI the first time any of those
rules changes — and the disagreement would be invisible, because both sides
would look plausible.

Everything the UI needs already existed programmatically: `AnswerResult` (with
the **resolved** `web_search_enabled` / `web_fallback_policy` the run actually
used), `engine.build_trace()` (the metadata-only run record),
`main.run_startup_preflight()` (mode/provider/endpoint/index validation), the
keys-free index helpers in `ingestion.py`, and
`graph.formatting.STOP_REASON_NOTES`.

## Decision

Add a **thin adapter**, not a second application: a FastAPI backend in
`server/` and a Vite + React frontend in `frontend/`, where the server computes
nothing the core already computes and the frontend renders nothing the server
did not report.

### The server is an adapter

`server/` imports only `graph.engine`, `graph.config`, `graph.consts`,
`graph.formatting`, `ingestion`, and `main`. It never imports `graph.nodes.*`
or the chain factories, and it constructs no LLM, embedding, Chroma, or Tavily
client — importing `server.app` stays side-effect-free and keys-free, the same
contract every other module holds.

| Module | Responsibility |
|---|---|
| `server/app.py` | `create_app()`, endpoints, error mapping, lifespan preflight, optional static mount |
| `server/schemas.py` | Pydantic request/response models — the API contract |
| `server/runs.py` | `RunStore`: bounded, thread-safe, in-memory, metadata-only |
| `server/status.py` | Resolved runtime + index status, assembled from existing readers |
| `server/documents.py` | Keys-free corpus listing (filesystem + fingerprint sidecar only) |

Graph execution goes through `engine.answer_question(...)` called via the
module attribute, which is both the repo's patchable test seam and the reason
the server cannot drift: the privacy lock, redaction, run ids, timings, and
`stop_reason` all arrive already decided.

### Resolved values are reported, never recomputed

`/api/ask` reports `AnswerResult.web_search_enabled` and
`.web_fallback_policy` — the values the run used — rather than re-reading the
environment. `/api/status` exposes `web_search_locked` for *display* only; the
actual lock stays in `engine.seed_state()`.

Index compatibility is the one place the server does mirror logic rather than
call it, because preflight raises rather than returns a structured verdict.
`server/status.py` reproduces preflight's ladder (`missing_index` →
`legacy_no_fingerprint` → `provider_mismatch` → `model_mismatch` →
`compatible`, plus `index_unreadable`) with preflight's asymmetry intact: a
missing fingerprint is legacy-OpenAI and needs no reindex in OpenAI mode, but
requires one in local mode. This mirroring is a known maintenance coupling,
recorded under **Known limitations**.

### Metadata-only run history

`app.state.run_store` holds `engine.build_trace(result)` plus `provider` and a
derived `status` (`ok` / `caveat` / `error`) in a `deque(maxlen=50)` behind a
lock, with a `run_id` index. No answer text, no snippets, no `page_content`, no
prompts, no raw state — the same rule the engine trace and eval history already
follow.

**Recording scope:** a record exists only when the engine *returned* an
`AnswerResult`, degraded runs included. HTTP-layer outcomes (422, 409, 503,
500) and cancellations (ADR 017) are returned live and never recorded, so
"Runs" means exactly "graph executions that produced a result".

### Errors are mapped deterministically, and `stop_reason` is never one

| Condition | HTTP |
|---|---|
| Invalid request (empty / > 4000 chars / bad policy) | 422 |
| Preflight failed at startup (`/api/ask` only) | 503 `preflight_failed` |
| Another run in flight | 409 `run_in_progress` |
| Config `ValueError` during a request | 503 `config_error` |
| Unknown `run_id` | 404 `run_not_found` |
| Run cancelled (ADR 017) | 499 `run_cancelled` |
| Unexpected engine exception | 500 `internal_error` + exception **type** only |
| Any of the nine `stop_reason` values | **200** + `stop_reason` and `caveat` |

The last row is the load-bearing one. A degraded run is an honest answer with a
caveat (ADR 001, ADR 006), not a server fault; turning it into a 5xx would
throw away the answer the graph worked to qualify.

A failed preflight does **not** stop the server: `/api/status` and
`/api/documents` keep working and report it, so the operator can see *what* is
wrong from the UI, while `/api/ask` returns 503 until the configuration is
fixed and the process restarted.

### Single in-flight Ask

Thread safety of the cached chains, retriever, and compiled graph is
**unverified in this repository**, so it is not assumed. `app.state.ask_lock`
is acquired non-blocking at the top of `/api/ask`; a second concurrent question
gets 409 without the engine being touched. Read-only endpoints are not
serialized. All per-app state (`preflight`, `run_store`, `ask_lock`,
`ask_cancel`) lives on `app.state` rather than at module level, so each app —
including each test app — is isolated.

### Sanitized surface

No public response contains an endpoint URL or hostname (notably not
`OLLAMA_BASE_URL`), an absolute filesystem path, or a raw exception message.
`persist_directory` / `collection_name` are the repo-relative constants from
`active_index_config()`. A `PreflightError`'s actionable text can name
endpoints and paths, so it is printed to the server console at startup — as the
CLI already does — and the API returns only a fixed summary pointing there.
Local mode is described by provider and model names alone.

### The frontend invents nothing

Three views (Ask / Documents / Runs), plain CSS, no router, state, or UI
library. Every runtime, mode, and index fact on screen comes from
`/api/status`, `/api/documents`, or a run payload; a failing `/api/status`
renders an explicit "backend unreachable" state rather than defaults.

Delivery was mock-first: the whole UI was built and tested against a typed mock
client selected by one module constant (`USE_MOCKS` in `src/api/client.ts` — no
`VITE_*` variable), covering every success, caveat, failure, privacy,
local-mode, and index-mismatch state, and the approved desktop UI became a
frozen visual baseline before backend work began. Typing the fixtures with
`api/types.ts` makes mock/real drift a compile error.

## Consequences

* One question at a time. Adequate for a single-user demo; a second caller is
  told so explicitly instead of racing unverified shared state.
* Run history is lost on restart and is not shared across worker processes —
  run uvicorn single-process.
* The web layer inherits every core guarantee for free: privacy lock, budgets,
  retry caps, redaction, provenance, and honest caveats. Nothing had to be
  restored at the HTTP boundary.
* No graph, node, routing, prompt, model, `stop_reason`, or `GraphState`
  change was needed to ship the web app; the CLI and eval harness are
  unaffected.
* New dependencies: `fastapi`, `uvicorn` (runtime), `httpx` (dev, for
  Starlette's `TestClient`), plus the Node toolchain for `frontend/`.
* Ask responses carry 300-character corpus snippets so citations can show
  evidence. That is user-owned content in a live response only — it is
  excluded from stored history, keeping the metadata-only convention intact.

## Trade-offs

* **Serialization over throughput.** Verifying concurrent graph invocation was
  out of scope; the lock is the smaller, honest claim. If concurrency is ever
  wanted, verify thread safety first rather than deleting the lock.
* **Mirrored index logic over a shared verdict function.** Refactoring
  preflight to return a structured result would have touched `main.py`, a
  protected file for this work. Mirroring is cheaper now and costlier later.
* **No streaming.** `answer_question()` returns after the run, so the execution
  timeline renders post-hoc. Live token/step streaming would require a new
  engine surface.
* **In-memory history over a database.** No schema, no migration, no
  persistence guarantee.
* **A sanitized status surface is less useful for debugging.** The operator
  reads the console for the full preflight message. Chosen because a browser
  page is a wider audience than a terminal.

## Known limitations

* **Preflight mirroring.** `server/status.py` reproduces preflight's
  compatibility semantics rather than calling it. A future change to preflight
  must be mirrored here, or the UI will report a verdict the CLI disagrees
  with.
* **Preflight runs once, at startup.** Configuration changed afterwards is not
  re-detected; the operator restarts the server.
* **No auth.** The API is unauthenticated and intended for local or trusted
  single-user deployment.

## Alternatives considered

* **Expose the graph directly over HTTP** (endpoints per node, or a LangServe
  mount). Rejected: it would publish internal graph structure as an API
  contract and bypass the engine's seeding, redaction, and observability.
* **Re-derive runtime policy in the server** from `graph.config`. Rejected —
  this is the drift the whole ADR exists to prevent; the resolved values ride
  on `AnswerResult`.
* **Persist run history to SQLite.** Rejected for v1: it would add a schema
  and a migration story to a demo whose history is deliberately
  metadata-only and disposable.
* **Map `stop_reason` to HTTP error codes.** Rejected: a caveat-bearing answer
  is a successful response with a warning, and encoding it as 5xx would make
  the API disagree with ADR 001 and ADR 006.
* **Allow concurrent asks and see what happens.** Rejected: an intermittent
  corruption of cached chain or retriever state is exactly the failure mode
  that is hardest to diagnose from a UI.
