# ADR 018: The engine API — one entry point, redacted input, metadata-only observability

Status: Accepted

Date: 2026-08-04

Relates to ADR 002 (privacy mode, whose amendment relies on the per-run
resolution described here), ADR 011 (whose Update note first recorded the
policy half of this decision), ADR 015 (whose privacy lock lives in
`seed_state()`), ADR 012 (whose operational rules assume metadata-only trace
output), and ADR 016 / ADR 017 (both built on this surface). None is
superseded.

## Context

This ADR is written **retroactively**, in the same spirit as ADR 013: the
decisions below are already implemented and already depended on by five later
ADRs, but they were never recorded as decisions of their own. They arrived
together during what ADR 011's Update calls the "engine API phase" and were
documented only as footnotes elsewhere — a per-run policy note in ADR 011, a
passing mention of redaction and metadata-only tracing in ADR 002's amendment
and ADR 012's operational rules, and a list of things that "already existed
programmatically" in ADR 016's Context. Anything that much of the design leans
on should be checkable against a decision record rather than inferred from
four half-references.

Three problems shared one cause.

**Every caller built its own run.** `main.py` seeded `GraphState` inline and
`evals/run_eval.py` duplicated it, each resolving `WEB_SEARCH_ENABLED` and
`WEB_FALLBACK_POLICY` on its own. Adding a state field meant editing every
caller, and a caller that missed a key handed nodes a state they had to
`.get()` defensively. Worse for the privacy story: with resolution spread
across callers there was no single place a lock could be applied, and
`decide_to_generate` read `os.environ` at decision time, so a run's behavior
could change mid-flight if the environment did.

**The question was passed through untouched.** It reaches the retriever, the
router, the generator, three graders, and — after rewriting — an outbound
Tavily query. A user who pastes an API key into a question ("why is
`sk-…` rejected by the payments runbook?") ships it to every one of those.

**A run left nothing behind.** The CLI printed the answer and the state was
discarded. There was no way to see which nodes actually ran, how long each
took, or why a run took the path it did — and the obvious fix, LangSmith,
exports full prompt inputs and outputs including retrieved `page_content`
(ADR 002's amendment), which is exactly what a compliance-sensitive
deployment cannot allow.

## Decision

One module, `graph/engine.py`, owns all three.

### 1. `answer_question()` is the only way to run the graph

`answer_question(question, options) -> AnswerResult` is the canonical entry
point for the CLI, the web API, the eval harness, and tests.

- **`AnswerOptions`** carries per-run overrides — `web_search_enabled`,
  `web_fallback_policy`, `run_id`, `trace_path`, `cancel_event` (ADR 017).
  Every field defaults to `None`, meaning "use the environment default".
  Nothing is ever written back to `os.environ`, which is what lets the eval
  harness run privacy rows and web rows in the same process.
- **`seed_state()`** is the single state-seeding helper. It builds the full
  `GraphState` — no key is ever absent — and resolves the per-run
  configuration once, before the first node runs. Graph decisions then read
  the resolved values from state rather than from the environment.
- **`AnswerResult`** reports what the run *actually used*, including the
  resolved `web_search_enabled` and `web_fallback_policy`. Callers report
  those values instead of recomputing them; ADR 016 exists largely to hold
  the web layer to that rule.

The privacy lock (ADR 015) is one condition inside `seed_state()`, applied
*after* the per-run resolution so an explicit
`AnswerOptions(web_search_enabled=True)` cannot reopen a path the deployment
closed. It cannot live in `graph/config.py`, which an explicit per-run option
bypasses entirely.

### 2. Input redaction happens before `GraphState`

Secret-shaped substrings are replaced with `[REDACTED]` before the question
enters state, so the redacted text is what reaches the retriever, the chains,
the outbound search query, the result, and the trace. Patterns cover
OpenAI/Anthropic-style keys, GitHub tokens, Tavily keys, AWS access key ids,
JWT-shaped tokens, `Authorization: Bearer` values, and generic
`api_key|token|password|secret` key/value pairs.

Two details are deliberate. The Bearer rule is narrow — the value must be at
least 12 characters from the token alphabet *and* contain a digit — so
ordinary prose like "the bearer of the on-call pager" is not mangled on its
way to the retriever. And the *original* input is used for exactly two things,
then dropped: `question_sha256` (so identical questions still correlate across
runs) and the `input_redacted` flag. It is never stored in `AnswerResult`,
`raw_state`, or the trace.

### 3. Observability is metadata-only, and additive by construction

Every run gets a `run_id`. The executed `node_path`, per-step
`node_timings_ms`, and `total_duration_ms` are collected by running the graph
through LangGraph's update stream (`stream_mode="updates"`) instead of
`invoke()`, and `AnswerOptions.trace_path` optionally writes `build_trace()`
as JSON.

The trace holds node names, timings, counters, flags, `stop_reason`, the
resolved runtime policy, the deduplicated citation lines, a redacted question
preview capped at `QUESTION_PREVIEW_MAX_CHARS = 80`, and the question hash —
**never** `page_content`, prompts, raw state, or keys. `build_trace()`
re-redacts the preview defensively, so even a directly-constructed
`AnswerResult` cannot leak a raw secret into a file.

Streaming is safe here only because `GraphState` has no custom reducers: every
channel is a plain last-value overwrite, so merging the updates onto the
seeded state reproduces `app.invoke()` exactly. Tracing therefore cannot
change routing, retries, or any node behavior. Objects without `stream` (test
fakes) fall back to `invoke()` with an empty trace. A failed trace write is
reported as a console banner with the exception type only and never loses the
answer.

## Consequences

- The privacy lock, the fallback policy, redaction, run ids, timings, and
  `stop_reason` all arrive **already decided** at every caller. ADR 016's
  central claim — that the server cannot drift from the CLI — is a
  consequence of this decision, not an independent one.
- A new `GraphState` field costs one edit, in `seed_state()`.
- The metadata-only rule that eval history (ADR 013) and the web layer's run
  store (ADR 016) both follow originates here; both are literally built on
  `build_trace()` or its shape.
- ADR 017's cancellation had an obvious seam to attach to: the update stream
  is already a per-node boundary, so cancellation cost one branch rather than
  a new execution path.
- Privacy mode gained a usable debugging substitute. Suppressing LangSmith
  (ADR 002's amendment) is only acceptable because a content-free local trace
  exists.
- **A constraint follows:** `GraphState` must not gain `typing.Annotated`
  reducers or accumulating channels. The `dict.update()` merge reproduces
  `invoke()` only for last-value channels, so a reducer would make traced runs
  diverge from untraced ones. The rule is recorded in `graph/state.py` and in
  CLAUDE.md.

## Trade-offs

- **Redaction is best-effort pattern matching, not a guarantee.** It catches
  common secret shapes; a novel or unusual one passes through. It can also
  mangle a legitimate question that happens to contain a token-shaped string,
  and because it runs *before* retrieval, a mangled question produces a worse
  answer rather than just a worse log line. Both directions were accepted:
  the alternative is shipping the secret to five external call sites.
- **`question_sha256` is an unsalted hash of the original question.** It
  correlates identical inputs, which is its purpose — but a short or guessable
  question is recoverable by brute force. It is a correlation id, not an
  anonymization mechanism, and must not be published as if it were one.
- **The trace is metadata-only, not content-free.** Citation lines carry
  document titles and web URLs, and the 80-character preview carries the start
  of a redacted question. That is far less than a LangSmith export, and it is
  still not nothing — `trace_path` writes plaintext JSON wherever the caller
  points it.
- **Timings are approximate.** They measure wall-clock between node
  completions, so conditional-edge evaluation — including the two grader LLM
  calls inside `grade_generation` — is attributed to the adjacent step, not to
  the edge. Useful for spotting a slow path, wrong for per-node billing.
- **One entry point is also one place to break.** Every caller inherits a
  regression in `seed_state()` simultaneously. Accepted: the failure mode it
  replaces was four callers disagreeing silently.
- **`AnswerResult.raw_state` is a leak of abstraction.** It exposes the final
  graph state so the CLI can format it and tests can assert on it, which means
  callers *can* reach past the structured fields. Kept because removing it
  would force presentation logic back into the graph (ADR 007).

## Alternatives considered

- **Keep per-caller seeding and share a helper function.** Rejected — a
  helper callers may or may not use is exactly what existed, and it drifted.
  The lock in particular has to be unavoidable to be a lock.
- **Put the privacy lock in `config.web_search_enabled()`.** Rejected, and
  worth restating because it looks tidier: an explicit per-run option bypasses
  that module entirely, so the lock would silently degrade into a default. See
  ADR 015.
- **Redact only in trace/log output, leaving `GraphState` raw.** Rejected —
  it protects the debug artifact and nothing else. The question reaches the
  retriever, four LLM chains, and a third-party search API; the debug file is
  the least exposed surface of the set.
- **Redact inside each node.** Rejected — five call sites to keep in sync,
  with the same drift failure this ADR exists to end.
- **Store the original question alongside the redacted one** for debugging.
  Rejected outright: it reintroduces the secret into `raw_state`, history, and
  traces, defeating the entire mechanism.
- **LangSmith as the observability story.** Rejected as the *only* story — it
  exports retrieved `page_content` and prompts to a third party (ADR 002's
  amendment) and is unavailable in exactly the deployments that most need to
  debug the self-correction loops. It remains fully supported for deployments
  that allow it.
- **OpenTelemetry / a metrics backend.** Rejected as overengineering: a
  single-user CLI and a single-process demo server have no collector to export
  to, and the JSON file is reviewable in one sitting.
- **LangChain callback handlers instead of the update stream.** Rejected —
  callbacks would fire per chain and per model call, giving finer detail at
  the cost of instrumenting every seam and reintroducing content into the
  callback payloads. Streaming node updates required no per-node
  instrumentation and, as ADR 017 later showed, was also the only clean
  cancellation boundary.
- **Making tracing always-on with a fixed path.** Rejected — writing a file
  for every CLI question is a surprise side effect; `trace_path=None` (the
  default) writes nothing.
