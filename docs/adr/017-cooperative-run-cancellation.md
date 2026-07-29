# ADR 017: Cooperative run cancellation

Status: Accepted

Date: 2026-07-29

Relates to ADR 006 (graceful degradation) and ADR 001 (`stop_reason` values).
Neither is superseded: a cancelled run is not a degraded run, and this ADR
deliberately adds no `stop_reason` value.

## Context

The web UI runs one question at a time. `POST /api/ask` acquires a
process-wide lock before calling `graph.engine.answer_question()` and releases
it in a `finally`, because thread safety of the cached chains, retriever, and
compiled graph is unverified in this repository — a second concurrent question
gets HTTP 409 rather than an assumption.

That made a Stop button impossible to build honestly on the client alone.
Aborting the browser request stops nothing: the engine call is synchronous, the
endpoint is a sync `def` running in Starlette's threadpool (so it cannot even
observe the disconnect), and the graph keeps executing every remaining node.
The lock therefore stayed held for the abandoned run's full remaining duration
— up to `MAX_RETRIES = 5` loops at `LLM_REQUEST_TIMEOUT_SECONDS` each — during
which every new question returned 409. The run also kept spending provider
calls and still landed in run history.

So "Stop" either had to reach the engine or stop being offered.

## Decision

Add **cooperative** cancellation at node boundaries, and make the cancel
request wait for the server to actually be free before it answers.

### Engine (`graph/engine.py`)

* `AnswerOptions.cancel_event: threading.Event | None = None`. Default `None`
  means the run cannot be cancelled, which is every CLI and eval run.
* `RunCancelled(Exception)` is raised when the event is set.
* `_run_graph_with_trace()` checks the event once per streamed chunk. The
  existing update stream (`stream_mode="updates"`) already yields one chunk per
  completed node, so it is the only cancellation point that does not interrupt
  work in flight. The `invoke()` fallback (minimal test fakes) exposes no
  boundaries and is not cancellable.

Cancellation latency is therefore **one node**, bounded by the per-request LLM
timeout. Nothing is pre-empted mid-call.

### No new `stop_reason`

A cancelled run raises instead of returning an `AnswerResult`. It has no
`stop_reason`, no caveat, no trace file, and no history record.

This is the load-bearing part of the decision. `stop_reason` (ADR 001)
describes how the *graph* ended and is shared vocabulary across nodes,
`graph/formatting.py::STOP_REASON_NOTES`, the run store, and the eval harness.
"Someone else stopped it" is a caller's decision, not a graph outcome; adding
it as a tenth value would have put an HTTP concern into all four.

### Server (`server/app.py`)

* The in-flight run's event is published on `app.state.ask_cancel` only while
  the ask lock is held, and cleared *before* the lock is released.
* `POST /api/ask/cancel` sets the event, then blocks on the ask lock (bounded
  by `llm_request_timeout_seconds() + 15s`) and returns
  `{cancelled, idle}`. Returning only once the lock is free is the point: the
  response means "you can ask again". Without it the client races the run it
  just cancelled and collects a 409 for its next question.
* A cancelled ask returns **HTTP 499** (`{"error": "run_cancelled"}`), the
  non-standard "client closed request" convention. It is neither a success nor
  a server fault, and a non-2xx keeps it off the `AskResponse` contract so a
  typed client can never parse it as an answer.

### Frontend

Stop calls `cancelRun()` first and shows a "Stopping…" state until the server
confirms; only then does the composer reopen. Both cancellation codes —
`request_cancelled` (local abort) and `run_cancelled` (the 499) — are
classified as cancellations and never rendered as errors: a stop is a choice
the user made, not a failure to report. Any result arriving after the click is
discarded.

## Consequences

* Stop frees the single-flight slot within one node instead of one full run, so
  the next question is accepted almost immediately.
* Cancellation stops spending provider calls at that boundary.
* Cancelled runs leave no record anywhere — no history entry, no trace, no
  caveat. Run history continues to mean "graph executions that returned a
  result".
* `graph/engine.py` gained one new control-flow path. It is inert unless a
  caller passes `cancel_event`; only `server/app.py` does. The CLI and the eval
  harness are byte-for-byte unaffected.
* Stop is not instant. The UI must show a pending state rather than pretend
  otherwise.

## Trade-offs

* **Latency over pre-emption.** A node already inside an LLM call runs to its
  own timeout. Killing the thread would be immediate but unsafe: the cached
  chains and compiled graph would be left in an unknown state, which is the
  same reason concurrent invocation is not assumed.
* **A blocking endpoint.** `POST /api/ask/cancel` holds a threadpool worker
  while it waits. Acceptable for a single-user deployment; it never blocks the
  event loop, since the endpoint is a sync `def`.
* **Non-standard status code.** 499 is an nginx convention, not an RFC. A
  reverse proxy in front of the app may treat it specially. Direct uvicorn and
  the Vite dev proxy both pass it through.

## Known limitations

* **Stale cancel across clients.** `POST /api/ask/cancel` cancels *the*
  in-flight run, not a named one — the client cannot know the `run_id`, which
  the engine generates. If a run finishes between the endpoint reading
  `ask_cancel` and acquiring the lock, and a new run starts, the endpoint waits
  on the new run and reports `cancelled: true` for a run it did not cancel.
  Unreachable from the shipped UI, whose composer is disabled while stopping;
  reachable from two browser tabs. Fixing it would need a client-supplied run
  token in `AskRequest`, which is not worth the contract change for a
  single-user demo.
* **Uncancellable window.** A run is not cancellable until its first node
  completes, nor on the `invoke()` fallback path.
* **In-memory only.** The cancel switch lives on `app.state`, so it does not
  survive a restart and is not shared across worker processes. Run uvicorn
  single-process, as the run history already requires.

## Alternatives considered

* **Frontend-only Stop.** Abort the fetch and say nothing to the server.
  Rejected: the 409 that prompted this work would remain, the run would keep
  costing money, and the button would be a lie.
* **Detect client disconnect.** Make the endpoint `async def` and race the
  engine against `request.is_disconnected()`. Rejected: the graph thread would
  still run to completion, and releasing the lock early would permit exactly
  the concurrent invocation the lock exists to prevent.
* **A `run_cancelled` stop_reason.** Rejected for the reasons under
  **Decision** — it would leak an HTTP-layer concern into the graph, the
  formatting layer, and the evals.
* **Return 200 with a cancelled marker.** Rejected: a 2xx that is not an
  `AskResponse` invites a typed client to parse it as one.
