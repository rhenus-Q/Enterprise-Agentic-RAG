# ADR 014: Optional local provider mode (`LLM_PROVIDER`)

Status: Accepted

Date: 2026-07-24

## Context

Every LLM call in this project was hard-wired to OpenAI: six chain modules each
constructed their own `ChatOpenAI(model="gpt-5-mini", temperature=0, ...)` with
identical arguments, and `OpenAIEmbeddings()` appeared twice in `ingestion.py`.

The privacy mode of ADR 002 (as amended to cover trace export) stops external
**web search** and **LangSmith export**, but the question and every retrieved
chunk still reach OpenAI for document grading, generation, grounding grading,
and answer-usefulness grading. Privacy mode therefore cannot remove third-party
egress — only a provider swap can. For an enterprise internal-document
assistant that is a real gap: the documents being graded and summarized are
exactly the ones a compliance-sensitive deployment cannot send out.

Two constraints shaped the design:

* `get_retriever()` is `@lru_cache`'d and its Chroma collection is bound to one
  embedding space (OpenAI's default 1536 dims vs. a local model's 1024). The
  provider cannot vary per run.
* In local mode the router LLM is skipped (privacy mode returns `RETRIEVE`
  before invoking it) and the query rewriter is unreachable (`REWRITE_QUERY`
  only edges into `WEBSEARCH`), so a single end-to-end local run cannot
  exercise all six chains.

## Decision

Add a single **process-level** provider switch, `LLM_PROVIDER`, defaulting to
`openai`. It is deliberately coarse: a deployment mode, not a per-run option
(`AnswerOptions`) and not a per-chain selection.

1. **Configuration** (`graph/config.py`): `llm_provider()`,
   `local_mode_enabled()`, `local_chat_model()`, `local_embedding_model()`,
   `ollama_base_url()`. Unset or empty means `openai`. An **invalid non-empty
   value raises `ValueError`** naming the bad value and the valid options.
2. **One chat-model factory** (`graph/chains/_llm.py::get_chat_model()`), used
   by all six chains. `temperature=0` and `LLM_REQUEST_TIMEOUT_SECONDS` apply
   on both branches; for Ollama the timeout travels via `client_kwargs`,
   because `ChatOllama` has no `timeout` field and ignores unknown kwargs, so
   passing it directly would be silently dropped.
3. **One embedding factory** (`ingestion.py::get_embeddings()`), with
   provider-scoped indexes: OpenAI keeps `chroma_db/` / `agentic_rag_docs`,
   local mode uses `chroma_db_local/` / `agentic_rag_docs_local`. The
   idempotent-rebuild `delete_collection()` is scoped to the active provider's
   collection.
4. **An index fingerprint** — `{"embedding_provider", "embedding_model"}` —
   written as a sidecar JSON inside the persist directory at build time and
   checked at startup.
5. **Local mode forces the existing privacy path**: `seed_state()` resolves
   `web_search_enabled` to `False`, and a per-run
   `AnswerOptions(web_search_enabled=True)` **cannot** override it.
6. **Startup preflight** in `main.py` (provider value, endpoint reachability,
   both models installed, index present and fingerprint-matching), reused by
   `evals/run_eval.py` *after* its `--validate-only` early return.

**The boundary, stated accurately.** In local mode no data is sent to OpenAI,
Tavily, or LangSmith, and no failure path falls back to them. The configured
endpoint is itself the trust boundary: it defaults to `localhost` but may point
at a company's own private infrastructure. The claim is **"no third-party
egress"**, never "nothing leaves the machine". No document in this repository
makes the stronger claim.

**Experimental, and not a quality claim.** The development defaults
(`qwen3:4b-instruct-2507-q4_K_M`, `qwen3-embedding:0.6b`) prove the local
execution path works end to end. A deployment can point the same switch at a
much stronger locally hosted model with no graph changes.

## Consequences

* Local mode is a genuine no-third-party-egress deployment, proven by tripwire
  tests rather than by inspection: `ChatOpenAI` and `OpenAIEmbeddings` are
  never constructed, the Tavily tool is never invoked, LangSmith export is
  suppressed, and a failing local model ends the run through the existing
  `generation_error` `stop_reason` instead of rerouting to a third party.
* Model name, `temperature=0`, and the request timeout now live in one place
  instead of six — a net reduction in duplication.
* **Intentionally changed:** in local mode the *resolved runtime policy* forces
  `web_search_enabled=False`, so a local-mode run traverses the existing
  privacy path. **Unchanged:** graph topology, routing functions, nodes,
  `GraphState`, prompts, the `gpt-5-mini` model name, the corpus,
  `stop_reason` semantics, and fallback-policy semantics. This feature must not
  be described as "no runtime behavior changed".
* An invalid `LLM_PROVIDER` now fails startup. That is the point: the failure
  it replaces is silent third-party egress.
* The two indexes coexist. Re-ingestion is required only on first use of a
  provider and when the configured embedding model changes; **switching between
  two already-built matching indexes requires none**. An index built before
  this feature has no fingerprint and is treated as legacy-OpenAI: accepted in
  OpenAI mode, a mismatch in local mode.
* Six chain factories, `get_chat_model()`, and `get_retriever()` are all
  `@lru_cache`'d, so an environment change mid-process has no effect. Correct
  at runtime, a real trap in tests — the provider suite clears every cache
  around each test.
* `LLM_REQUEST_TIMEOUT_SECONDS=60` is likely too tight for local inference,
  particularly on the first call while the model cold-loads.

## Trade-offs

* **Process-level, not per-run.** Accepted deliberately: the cached retriever
  and its embedding-space binding make per-run switching incoherent, and a
  per-run provider option would also be a per-run way to reopen egress.
* **Fail-fast on an invalid value breaks the module's usual fail-safe
  pattern.** `normalize_web_fallback_policy()` falls back to `conservative`
  because every policy value is a benign variation. A mistyped provider is
  different in kind — quietly degrading `ollma` to `openai` is exactly the
  silent privacy failure this ADR exists to prevent.
* **Preflight sits outside the graph, duplicating a little intent.** ADR 006
  requires in-graph failures to degrade rather than crash, so satisfying
  "clear failure" inside a node would have meant weakening graceful
  degradation. Checking before the graph keeps both.
* **A sidecar JSON rather than Chroma collection metadata.** Storing the
  fingerprint with the collection would be tidier, but `langchain-chroma`
  accepts `collection_metadata` only as a constructor argument and exposes no
  public reader; the alternative was reaching into `_collection`. The sidecar
  lives inside the persist directory, so it still travels with the index.
* **Answer quality is explicitly not a success criterion.** Small local models
  are weakest at the grounding gate — leniency lets ungrounded answers through
  silently, strictness causes retry thrash to `MAX_RETRIES = 5`, which at local
  inference speed is a latency cliff. Tuning prompts or thresholds to flatter
  local output would silently change OpenAI-mode behavior too, so it is out of
  scope.

## Alternatives considered

* **Per-chain provider selection** (local generation, OpenAI graders).
  Rejected: it reintroduces third-party egress through the back door while
  looking like a local deployment, and multiplies the configuration surface.
* **Automatic failover to OpenAI when the local endpoint is down.** Rejected
  outright — it converts a loud local failure into silent third-party egress.
  A local failure degrades through the existing `stop_reason` instead, and a
  test asserts `ChatOpenAI` is never constructed on that path.
* **A new `stop_reason` for provider misconfiguration.** Rejected: preflight
  runs before the graph, so no new terminal state or caveat is needed.
* **Dimension checking instead of a fingerprint.** Insufficient: a dimension
  mismatch already fails loudly, but two *different* embedding models of the
  same dimension produce no error at all — retrieval would silently return
  meaningless neighbours and the graph would grade and answer over garbage.
* **Index migration tooling / fingerprint versioning / corpus hashing.**
  Rejected as overengineering; the fingerprint stays provider + model only.
* **Gating `--validate-only` on preflight.** Rejected: it returns before
  importing the graph by design, performs no model execution, and gating it
  would break a keys-free invariant and remove a safe command from the
  standard validation set.

## Follow-up

* Eval history records carry no provider field, so running evals in both modes
  would make the "Delta vs. previous run" section (ADR 013) compare across
  providers and report meaningless deltas. Out of scope here; add a provider
  field to the history record before evaluating local mode systematically.
* `qwen3` is a hybrid reasoning model. LangChain normalizes reasoning into
  separate content blocks, so `StrOutputParser` output should be clean, but
  this depends on how the installed `ChatOllama` maps Ollama's thinking
  parameter. Leaked `<think>` blocks would contaminate both the answer and what
  the grounding grader sees — worth a manual check on first use.
