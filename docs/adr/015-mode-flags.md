# ADR 015: `PRIVACY_MODE` and `FULLY_LOCAL_MODE` deployment flags

Status: Accepted

Date: 2026-07-24

Extends ADR 002 (`WEB_SEARCH_ENABLED` privacy mode) and ADR 014 (local provider
mode). Neither is superseded; both variables keep working with unchanged
semantics.

## Context

Two features arrived at overlapping controls, each named after its mechanism
rather than the property an operator cares about:

* `WEB_SEARCH_ENABLED=false` (ADR 002) disables web search *and* LangSmith
  export — a reader has to know the second effect. It is a **default**:
  `seed_state()` consults it only when the per-run option is `None`, so an
  explicit `AnswerOptions(web_search_enabled=True)` overrides it.
* `LLM_PROVIDER=ollama` (ADR 014) names a vendor rather than "run everything
  locally". It is a **lock**: `seed_state()` forces `web_search_enabled=False`
  unconditionally, so no per-run option can reopen the path.

So the codebase already had a soft default and a hard lock, enforced at two
different points, with no way to assert the hard lock *without* also switching
model provider — and no vocabulary matching how deployments are actually
described.

Adding a second control surface over the same state is how configuration
ambiguity is born, so the precedence question had to be settled before the
names were worth adding.

## Decision

Add two default-off flags, `PRIVACY_MODE` and `FULLY_LOCAL_MODE`, as the
primary documented surface.

### Privacy precedence

Resolved in this order:

1. `PRIVACY_MODE=true` **or** the active provider is local → `web_search_enabled = False`. Absolute; a per-run option cannot override.
2. Otherwise an explicit `AnswerOptions(web_search_enabled=…)` → that value.
3. Otherwise → `NOT (WEB_SEARCH_ENABLED is explicitly falsy)`.

| `PRIVACY_MODE` | provider local? | `WEB_SEARCH_ENABLED` | per-run option | resolved |
|---|---|---|---|---|
| unset/false | no | unset/truthy | `None` | True |
| unset/false | no | unset/truthy | `True` | True |
| unset/false | no | unset/truthy | `False` | False |
| unset/false | no | falsy | `None` | False |
| unset/false | no | falsy | `True` | **True** — legacy default, preserved |
| true | no | any | `None` | False |
| true | no | any | `True` | **False** — locked |
| any | yes | any | any | **False** — locked |

Two layers implement this: `config.web_search_enabled()` lowers the *default*
when `PRIVACY_MODE` is set, and `graph/engine.py::seed_state()` applies the
*lock*. The lock cannot live in `graph/config.py`, because an explicit per-run
option bypasses that module entirely — putting it there would silently produce
a default rather than a lock. Because the LangSmith guard keys off the resolved
`initial_state["web_search_enabled"]`, trace suppression follows with no second
edit.

### Provider resolution

| `FULLY_LOCAL_MODE` | `LLM_PROVIDER` | Result |
|---|---|---|
| unset or false | unset | `openai` |
| unset or false | `openai` | `openai` |
| unset or false | `ollama` | **`ollama`** |
| true | unset | `ollama` |
| true | `ollama` | `ollama` |
| true | `openai` | **`ValueError`** naming both |

Explicit `false` means "this convenience flag asserts nothing", not "local
deployment is forbidden" — an operator who copies `FULLY_LOCAL_MODE=false` from
`.env.example` while separately setting `LLM_PROVIDER=ollama` holds a coherent
configuration that must keep working. Only the last row is a genuine
contradiction, and it raises for ADR 014's reason: guessing would leave the
operator believing the deployment is local while questions and retrieved chunks
flow to a third party.

### Value parsing and startup validation

Both new flags accept `true/1/yes/on` and `false/0/no/off`, case-insensitive
and whitespace-stripped. **Any other non-empty value raises `ValueError`.** This
is deliberately stricter than `WEB_SEARCH_ENABLED`, which treats any
unrecognized value as enabled — that leniency is ADR 002's published contract
with a test pinning it, and is left untouched. A new surface can afford the
stricter rule, matching `llm_provider()`.

Validation happens in `main.py::run_startup_preflight()` (renamed from
`run_local_mode_preflight()`, since it now runs three mode-independent checks).
Both flags and the provider are validated at the top, before the non-local
early return, so the error surfaces as a `PreflightError` in every mode.
Without this, the same `ValueError` would appear as a raw traceback in the CLI
and — worse — be swallowed by the eval harness's per-row `except Exception` and
reported as a generic failed row.

`evals/run_eval.py --validate-only` still returns before preflight and never
parses the flags, preserving its keys-free, dependency-free contract.

## Consequences

* An operator can now assert an absolute privacy lock without changing model
  provider — a state that was not previously reachable.
* `PRIVACY_MODE=true` and `WEB_SEARCH_ENABLED=false` are **not**
  interchangeable. The first is a lock, the second a default. Documentation
  that calls them equivalent is wrong.
* `PRIVACY_MODE=true` in `.env` will fail every web-fallback row of a **full
  eval**, because the lock beats the harness's per-row `AnswerOptions`. Correct
  behavior for a lock, but it means evals should set it per-invocation rather
  than globally. The same is already true of `FULLY_LOCAL_MODE` /
  `LLM_PROVIDER=ollama`.
* Configurations that previously started will now fail if a new flag holds an
  unparseable value or if `FULLY_LOCAL_MODE=true` contradicts
  `LLM_PROVIDER=openai`. Intended; messages name the variables and values.
* `tests/conftest.py` clears both new variables alongside the provider ones. A
  developer's `.env` must not decide what the mocked suites assert — before that
  fixture existed, an ambient `LLM_PROVIDER=ollama` broke twelve tests that were
  asserting correct behavior.
* One condition in `seed_state()` is the entire lock. A refactor that moves it
  before the `None` check, or folds it into `config.web_search_enabled()`, would
  silently downgrade it to a default.

## Trade-offs

* **Two names for overlapping state.** Accepted because the monotonic
  privacy rule makes every combination well-defined and safe, and because the
  new names carry a guarantee the old ones cannot express. The cost is that
  documentation must consistently present the legacy names as
  default-strength.
* **Asymmetric parsing.** `PRIVACY_MODE=maybe` raises while
  `WEB_SEARCH_ENABLED=maybe` means enabled. Inconsistent on its face, but
  changing the latter would break a published contract for no benefit.
* **Asymmetric treatment of explicit `false`.** For privacy, `false` is
  absorbed by a monotonic OR and simply loses; for the provider, `false` is a
  genuine "no opinion" that defers to `LLM_PROVIDER`. The difference is
  intentional: privacy composes as a ratchet, provider selection does not.
* **A rename touching 17 references.** `run_local_mode_preflight` →
  `run_startup_preflight` was mechanical, but the old name had become actively
  misleading once three of its checks ran in every mode.

## Alternatives considered

* **Making `PRIVACY_MODE` a per-run-overridable default**, exactly aliasing
  `WEB_SEARCH_ENABLED`. Rejected: it would make the new name redundant, and a
  control called "privacy mode" that a caller can switch off is a poor
  guarantee.
* **Promoting `WEB_SEARCH_ENABLED=false` to a lock.** Rejected: it is a
  published contract, and the eval harness depends on per-run override to run
  privacy and web rows in the same process.
* **Treating `FULLY_LOCAL_MODE=false` + `LLM_PROVIDER=ollama` as a
  contradiction.** Rejected on backward-compatibility grounds — see the
  provider table above. An earlier draft of the spec specified this; it would
  have broken operators who copy the `.env.example` default.
* **A new `AnswerOptions` or `GraphState` field for privacy.** Rejected: per-run
  privacy already exists as `AnswerOptions.web_search_enabled`, and a per-run
  field for a deployment lock is a contradiction in terms.
* **Deprecation warnings on the legacy variables.** Rejected as noise; both
  remain fully supported with unchanged semantics.
* **A general configuration schema or settings object.** Rejected as
  overengineering; plain module-level readers match `graph/config.py`.
