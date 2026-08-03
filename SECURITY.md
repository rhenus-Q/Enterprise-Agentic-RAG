# Security Policy

## Reporting a vulnerability

Please report security issues through GitHub's
[private vulnerability reporting](https://github.com/rhenus-Q/Enterprise-Agentic-RAG/security/advisories/new)
(**Security → Report a vulnerability**). Do not open a public issue for a
suspected vulnerability.

Only the latest release on `main` is supported.

## Scope

This is a demonstration project for an Agentic RAG architecture, not a hardened
product. The following are **known, deliberate design limits — not
vulnerabilities**:

* **The web layer is single-user by design.** No authentication, no
  authorization, no rate limiting, no tenant isolation; one in-flight question
  at a time and in-memory run history. Bind it to localhost. Do not expose it
  to a network you do not control.
* **Answer quality is not a security boundary.** Hallucinated, incorrect, or
  unhelpful model output is a quality issue, not a security issue.
* **Prompt-injection defense is prompt-level only.** The generation prompt
  treats retrieved content — especially web results — as untrusted evidence,
  never as instructions ([ADR 010](docs/adr/010-prompt-injection-defense.md),
  [ADR 012](docs/adr/012-prompt-injection-hardening.md)). This is a first-line
  mitigation, not a complete solution: the relevance gate checks topicality,
  not safety, and there is no injection detection, content sanitization, or
  domain allowlisting. Generation has no tools to call, which limits — but does
  not eliminate — the impact of injected instructions.

Reports that a stronger boundary *should* exist are welcome as regular issues
or discussions; they are roadmap items rather than vulnerability reports.

## Trust boundaries and data egress

Understanding where data goes is the main security-relevant decision an
operator makes here. Full detail lives in the
[Deployment modes](README.md#deployment-modes-privacy_mode-fully_local_mode)
section of the README and in [`.env.example`](.env.example); the summary:

| Mode | Question and retrieved documents reach |
|---|---|
| Default (`LLM_PROVIDER=openai`) | OpenAI; Tavily when web search runs; LangSmith when tracing is on |
| `PRIVACY_MODE=true` | OpenAI only — web search and LangSmith export are locked off and cannot be re-enabled per run |
| `FULLY_LOCAL_MODE=true` / `LLM_PROVIDER=ollama` | Only the configured `OLLAMA_BASE_URL` endpoint |

Two things worth stating explicitly:

* **LangSmith traces carry full prompts and the body text of retrieved internal
  documents** to a third party. A run with effective `web_search_enabled=false`
  suppresses export entirely. To debug a private run, use the metadata-only
  engine trace (`AnswerOptions.trace_path`) instead.
* **Local-provider mode means "no third-party egress", not "nothing leaves the
  machine".** `OLLAMA_BASE_URL` is itself the trust boundary and may point at
  separate infrastructure.

## Handling secrets

* API keys are read from `.env`, which is gitignored. Only
  [`.env.example`](.env.example) — placeholders only — is committed.
* Secret-shaped values in a question (OpenAI/Anthropic-style keys, GitHub
  tokens, `api_key=` / `token=` / `password=` / `secret=` pairs) are redacted at
  the engine boundary before the question reaches run history or trace output.
  This is defense in depth for debug artifacts, not a guarantee that every
  possible secret shape is caught — do not paste credentials into questions.
* Run history and engine traces are metadata-only: no answers, document bodies,
  prompts, or raw graph state.

**Never commit a real `.env`.** Enabling GitHub secret scanning with push
protection on a fork is recommended.
