"""
config.py

Runtime configuration flags read from environment variables.

Kept separate from the graph modules so that reading configuration stays
side-effect-free and easy to test: no client construction, no .env loading
(callers such as main.py load .env before invoking the graph).
"""

import os

# Values (case-insensitive, whitespace-stripped) that disable a boolean flag.
_FALSY_VALUES = {"false", "0", "no", "off"}

# Values that enable one. Used only by the default-off mode flags below;
# WEB_SEARCH_ENABLED keeps its own lenient "anything not falsy is on" rule.
_TRUTHY_VALUES = {"true", "1", "yes", "on"}


def _flag_from_env(name: str) -> bool:
    """
    Read a default-off boolean mode flag.

    Missing or empty is False. Recognized truthy/falsy spellings resolve
    normally. Anything else raises ValueError rather than being guessed: these
    flags gate external egress, so a typo must not quietly resolve to either
    answer.

    Deliberately stricter than web_search_enabled() below, which treats any
    unrecognized value as enabled. That leniency is a published contract
    (ADR 002) with tests pinning it, so it is left untouched; a new surface can
    afford the stricter rule, matching llm_provider().
    """

    raw = os.getenv(name)
    if raw is None:
        return False

    cleaned = raw.strip().lower()
    if not cleaned:
        return False

    if cleaned in _TRUTHY_VALUES:
        return True

    if cleaned in _FALSY_VALUES:
        return False

    raise ValueError(
        f"Invalid {name} value {raw.strip()!r}. "
        f"Valid options: {', '.join(sorted(_TRUTHY_VALUES))} to enable, "
        f"{', '.join(sorted(_FALSY_VALUES))} to disable. "
        f"Unset the variable to leave {name} off."
    )


def privacy_mode() -> bool:
    """
    Read the PRIVACY_MODE lock from the environment (default off).

    True is an absolute lock: no external web search and no LangSmith trace
    export, and — unlike WEB_SEARCH_ENABLED — a per-run
    AnswerOptions(web_search_enabled=True) cannot reopen either path.

    The lock itself is applied in graph/engine.py::seed_state(), because an
    explicit per-run option bypasses this module entirely. See ADR 015.

    False or unset asserts nothing, leaving WEB_SEARCH_ENABLED and per-run
    options in control.
    """

    return _flag_from_env("PRIVACY_MODE")


def web_search_enabled() -> bool:
    """
    Resolve the DEFAULT web-search setting from the environment.

    Web search is on unless something asks for privacy: PRIVACY_MODE=true, or
    an explicit falsy WEB_SEARCH_ENABLED ("false" / "0" / "no" / "off"). Any
    other WEB_SEARCH_ENABLED value still means enabled, preserving that
    variable's original contract.

    Only the disabling direction is ever applied, so PRIVACY_MODE=false cannot
    raise the default back up when WEB_SEARCH_ENABLED=false is also set.

    This is the DEFAULT layer: seed_state() consults it only when no per-run
    option was given, and the CLI banner reads it. The absolute lock lives in
    graph/engine.py::seed_state() — do not move it here, where an explicit
    per-run option would bypass it and silently downgrade it to a default.
    """

    if privacy_mode():
        return False

    return os.getenv("WEB_SEARCH_ENABLED", "true").strip().lower() not in _FALSY_VALUES


# Web-fallback policy values (WEB_FALLBACK_POLICY). Distinct from the
# WEB_SEARCH_ENABLED privacy switch: the switch decides whether external web
# search is allowed at all; the policy decides WHEN the system chooses
# retrieval-triggered web fallback while web search is otherwise allowed.
WEB_FALLBACK_CONSERVATIVE = (
    "conservative"  # web only when zero relevant local docs remain (default)
)
WEB_FALLBACK_AGGRESSIVE = (
    "aggressive"  # legacy CRAG behavior: any irrelevant doc triggers web fallback
)
WEB_FALLBACK_DISABLED = "disabled"  # local retrieval paths never fall back to the web

_WEB_FALLBACK_POLICIES = {
    WEB_FALLBACK_CONSERVATIVE,
    WEB_FALLBACK_AGGRESSIVE,
    WEB_FALLBACK_DISABLED,
}


def normalize_web_fallback_policy(value) -> str:
    """
    Normalize a web-fallback policy value (case-insensitive,
    whitespace-stripped). Unknown, missing, or None values fall back to
    "conservative" — for an enterprise internal-document assistant the safe
    default is to answer from the curated local corpus first and use the web
    only when nothing relevant remains.

    Shared by the env reader below and by per-run callers (graph/engine.py)
    that pass an explicit policy, so both resolve values identically.
    """

    if value is None:
        return WEB_FALLBACK_CONSERVATIVE

    cleaned = str(value).strip().lower()
    return cleaned if cleaned in _WEB_FALLBACK_POLICIES else WEB_FALLBACK_CONSERVATIVE


def web_fallback_policy() -> str:
    """
    Read the WEB_FALLBACK_POLICY default from the environment. This is the
    default source only: the engine resolves the effective policy into
    GraphState["web_fallback_policy"] once per run, and graph decisions read
    it from state.
    """

    return normalize_web_fallback_policy(os.getenv("WEB_FALLBACK_POLICY"))


# Per-run budget defaults. Sized above the worst case the MAX_RETRIES loop can
# produce today (5 generations + 4 query rewrites + 15 web-result grades = 24
# counted LLM calls, 5 searches, 15 grades), so the budgets never bind before
# the retry cap does unless explicitly tightened via environment variables.
DEFAULT_MAX_LLM_CALLS_PER_RUN = 30
DEFAULT_MAX_WEB_SEARCHES_PER_RUN = 5
DEFAULT_MAX_WEB_RESULTS_TO_GRADE = 15


def _positive_int_from_env(name: str, default: int) -> int:
    """
    Read a positive integer from the environment.
    Missing, malformed, zero, or negative values fall back to the default —
    a budget can be tightened or loosened, but never accidentally disabled.
    """

    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        value = int(raw.strip())
    except ValueError:
        return default

    return value if value > 0 else default


def max_llm_calls_per_run() -> int:
    """Budget for counted LLM calls per graph run (MAX_LLM_CALLS_PER_RUN)."""

    return _positive_int_from_env("MAX_LLM_CALLS_PER_RUN", DEFAULT_MAX_LLM_CALLS_PER_RUN)


def max_web_searches_per_run() -> int:
    """Budget for Tavily searches per graph run (MAX_WEB_SEARCHES_PER_RUN)."""

    return _positive_int_from_env("MAX_WEB_SEARCHES_PER_RUN", DEFAULT_MAX_WEB_SEARCHES_PER_RUN)


def max_web_results_to_grade() -> int:
    """Budget for web results graded for relevance per run (MAX_WEB_RESULTS_TO_GRADE)."""

    return _positive_int_from_env("MAX_WEB_RESULTS_TO_GRADE", DEFAULT_MAX_WEB_RESULTS_TO_GRADE)


# Per-request timeout (seconds) for an individual LLM call. Bounds wall-clock
# time on a single ChatOpenAI request so a hung dependency cannot stall a run;
# the existing per-call exception handlers map a timeout to the right *_error
# stop_reason, so the success path is unchanged.
DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS = 60


def llm_request_timeout_seconds() -> int:
    """Per-request timeout in seconds for LLM calls (LLM_REQUEST_TIMEOUT_SECONDS)."""

    return _positive_int_from_env(
        "LLM_REQUEST_TIMEOUT_SECONDS", DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS
    )


# --- Provider selection (LLM_PROVIDER) ---
#
# Which provider serves every LLM and embedding call. Deliberately coarse: a
# process-level deployment mode, not a per-run option and not a per-chain
# selection. It has to be process-level because get_retriever() is cached for
# the process and its Chroma collection is bound to one embedding space
# (OpenAI's default 1536 dims vs. a local model's 1024), so a run cannot swap
# providers halfway.
PROVIDER_OPENAI = "openai"
PROVIDER_OLLAMA = "ollama"

_LLM_PROVIDERS = (PROVIDER_OPENAI, PROVIDER_OLLAMA)

# The OpenAI chat model every chain uses whenever LLM_PROVIDER is unset or
# "openai" (graph/chains/_llm.py::get_chat_model()). Not env-configurable,
# unlike the local-provider models below. Lives here rather than in _llm.py
# so callers outside the graph (e.g. server/status.py) can read it without
# importing the chains package.
OPENAI_CHAT_MODEL = "gpt-5-mini"

# Local-mode development defaults. Both tags were verified as installed on the
# development endpoint rather than assumed — a wrong embedding tag would
# silently build an index against the wrong model. Any locally hosted model can
# be used instead via the environment variables below, with no graph changes.
DEFAULT_LOCAL_CHAT_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
DEFAULT_LOCAL_EMBEDDING_MODEL = "qwen3-embedding:0.6b"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


def fully_local_mode() -> bool:
    """
    Read the FULLY_LOCAL_MODE convenience flag (default off).

    True selects the local provider. False or unset asserts nothing and leaves
    LLM_PROVIDER in control — an operator who copies FULLY_LOCAL_MODE=false
    from .env.example while separately setting LLM_PROVIDER=ollama holds a
    coherent configuration that must keep working.

    Reads only its own variable: llm_provider() consults this function, so
    consulting llm_provider() here would recurse.
    """

    return _flag_from_env("FULLY_LOCAL_MODE")


def llm_provider() -> str:
    """
    Resolve the provider deployment mode from FULLY_LOCAL_MODE and LLM_PROVIDER.

    FULLY_LOCAL_MODE=true selects "ollama". Unset or false asserts nothing, so
    LLM_PROVIDER decides on its own: unset or empty returns the documented
    default ("openai"), and an explicit "openai"/"ollama" (case-insensitive,
    whitespace-stripped) returns that value.

    Two configurations raise ValueError: an invalid LLM_PROVIDER value, and the
    single genuine contradiction FULLY_LOCAL_MODE=true with LLM_PROVIDER=openai.

    Failing loudly here deliberately breaks this module's usual fail-safe
    pattern. normalize_web_fallback_policy() can fall back to conservative
    because every policy value is a benign variation; the provider is
    different in kind. Silently degrading a typo like "ollma" to "openai", or
    silently picking a side in a contradiction, would ship the question and
    every retrieved chunk to a third party while the operator believes the
    deployment is fully local — the exact silent privacy failure local mode
    exists to prevent. An unset value defaulting to OpenAI is fine, because
    that is an explicit documented default rather than a misread intention.
    """

    requested_local = fully_local_mode()

    raw = os.getenv("LLM_PROVIDER")
    if raw is None or not raw.strip():
        return PROVIDER_OLLAMA if requested_local else PROVIDER_OPENAI

    cleaned = raw.strip().lower()

    if cleaned not in _LLM_PROVIDERS:
        raise ValueError(
            f"Invalid LLM_PROVIDER value {raw.strip()!r}. "
            f"Valid options: {', '.join(_LLM_PROVIDERS)}. "
            f"Unset the variable to use the default provider ({PROVIDER_OPENAI})."
        )

    if requested_local and cleaned != PROVIDER_OLLAMA:
        raise ValueError(
            f"Contradictory configuration: FULLY_LOCAL_MODE=true requires the "
            f"'{PROVIDER_OLLAMA}' provider, but LLM_PROVIDER is {cleaned!r}. "
            f"Unset LLM_PROVIDER (or set it to '{PROVIDER_OLLAMA}') to run fully "
            f"locally, or set FULLY_LOCAL_MODE=false to use {cleaned!r}."
        )

    return cleaned


def local_mode_enabled() -> bool:
    """
    True when LLM_PROVIDER selects the local provider.

    Derived helper — it reads no environment variable of its own, so the
    fail-fast behavior of llm_provider() applies here too.
    """

    return llm_provider() == PROVIDER_OLLAMA


def _non_empty_str_from_env(name: str, default: str) -> str:
    """Read a whitespace-stripped string; missing or blank falls back to the default."""

    raw = os.getenv(name)
    if raw is None:
        return default

    return raw.strip() or default


def local_chat_model() -> str:
    """Chat model served by the local provider (LOCAL_CHAT_MODEL)."""

    return _non_empty_str_from_env("LOCAL_CHAT_MODEL", DEFAULT_LOCAL_CHAT_MODEL)


def local_embedding_model() -> str:
    """Embedding model served by the local provider (LOCAL_EMBEDDING_MODEL)."""

    return _non_empty_str_from_env("LOCAL_EMBEDDING_MODEL", DEFAULT_LOCAL_EMBEDDING_MODEL)


def ollama_base_url() -> str:
    """
    Base URL of the local provider endpoint (OLLAMA_BASE_URL).

    Any trailing slash is stripped so callers can join paths without producing
    a doubled separator. Note this is a real trust boundary: it defaults to
    localhost but may point at private infrastructure elsewhere.
    """

    return _non_empty_str_from_env("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")
