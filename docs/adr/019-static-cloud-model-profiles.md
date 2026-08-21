# ADR 019: Static cloud model profiles

Status: Accepted

Date: 2026-08-17

## Context

All six chat tasks historically used OpenAI `gpt-5-mini`. The application now
supports a small set of static cloud allocations without turning model
selection into a per-request decision, changing graph routing, or weakening
provider isolation.

Cloud chat allocation and embedding deployment are separate concerns. The
cloud retriever continues to embed each query with `OpenAIEmbeddings`, including
when some chat tasks use Together. Startup validation therefore has to account
for both chat targets and the unchanged OpenAI embedding dependency.

## Decision

Keep `MODEL_OPTIMIZATION_PROFILE` as a strict process-level setting with three
supported values:

- `legacy`: OpenAI `gpt-5-mini` serves all six chat tasks.
- `luna_all`: OpenAI `gpt-5.6-luna` serves all six chat tasks.
- `flash_luna`: Together `deepseek-ai/DeepSeek-V4-Flash-0731` serves
  `question_router`, `retrieval_grader`, and `hallucination_grader`; OpenAI
  `gpt-5.6-luna` serves `answer_grader`, `generation`, and `query_rewriter`.

The first two profiles are uniform allocations. `flash_luna` is an explicit
per-task mapping rather than a generic Cheap/Primary tier split. Selection is
still static and process-level: it does not inspect questions, documents,
answers, confidence, or runtime state.

All six chains continue through `graph/chains/_llm.py`. OpenAI targets use the
official API. The retained Together target uses `ChatOpenAI` with Together's
OpenAI-compatible base URL and `TOGETHER_API_KEY`, and requests
`reasoning.enabled=false`. There is no provider/model fallback.

The provider boundary is explicit: each task uses only its profile-assigned
provider. Invalid profiles and missing provider credentials fail clearly
instead of being silently coerced or routed to another provider.

Every cloud profile requires `OPENAI_API_KEY` because cloud retrieval retains
OpenAI embeddings and the OpenAI-scoped index. `flash_luna` additionally
requires `TOGETHER_API_KEY` for its three Flash chat tasks. Startup preflight
uses the effective profile, makes no network request, and exposes only missing
environment-variable names.

Local mode overrides every requested cloud profile, resolves all six tasks to
the configured Ollama-compatible target, and constructs no cloud client. The
configured endpoint is the trust boundary: it may be `localhost` or private
infrastructure. No data is sent to OpenAI, Together, Tavily, or LangSmith, and
no local failure path falls back to them. The guarantee is no third-party
egress, not that nothing leaves the machine.

Privacy mode forces the effective cloud profile to `legacy`. Target settings,
provider usage, and model identities remain metadata-only; prompts, documents,
answers, raw responses, reasoning text, and credentials are not persisted.

## Consequences

- Runtime configuration, startup preflight, status responses, and frontend
  contracts expose exactly the three supported cloud profiles.
- `flash_luna` uses Together only for its three explicitly mapped Flash tasks;
  its other chat tasks and all cloud query embeddings use OpenAI.
- Switching profiles requires a fresh process because policy, clients, and
  chain factories are cached intentionally.
- Graph topology, `GraphState`, prompts, chain schemas, retry and budget
  semantics, embeddings, indexes, and retrieval behavior remain unchanged.
- Together-specific request settings and provider-reported usage are attributed
  to the exact provider/model. Unsupported usage fields remain `null`, not zero.
- Local-provider failures never fall back to OpenAI, Together, Tavily, or
  LangSmith.

## Trade-offs

- Static routing cannot optimize per question. This keeps model allocation
  deterministic, observable, and independent of graph state.
- The hybrid profile adds a second chat provider and credential while cloud
  retrieval continues to depend on OpenAI embeddings.
- Reusing `ChatOpenAI` for Together preserves the structured-output path and
  avoids another client dependency, but provider-specific nonstandard response
  fields are not retained.

## Alternatives considered

- **Dynamic or per-run model routing.** Rejected because it would add another
  runtime decision, complicate cached-client ownership, and make allocation
  content-aware.
- **Cross-provider fallback.** Rejected because it hides failures, corrupts
  provider attribution, and can violate privacy or operator intent.
- **Together SDK or another adapter dependency.** Rejected because the retained
  Together target is served through the existing OpenAI-compatible client path.
- **Together-only startup credentials for `flash_luna`.** Rejected because
  query embedding still uses OpenAI in the cloud deployment.
