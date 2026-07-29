"""Keys-free runtime and index status assembly."""

from __future__ import annotations

import ingestion
from graph import config
from graph.chains._llm import OPENAI_CHAT_MODEL
from server.schemas import IndexStatus, PreflightStatus, RuntimeStatus

# Compatibility state used when the index could not be inspected at all
# (permission denied, unreadable directory). Deliberately distinct from
# "missing_index": nothing is known about the index, so the status must not
# claim it is absent, and must not claim a reindex would fix anything.
INDEX_UNREADABLE = "index_unreadable"

# Sanitized, stable configuration diagnostics.
#
# /api/status is the diagnostic endpoint and may say what is misconfigured, but
# it never echoes the raw ValueError from graph/config.py: those messages embed
# the offending environment value (`Invalid LLM_PROVIDER value 'bogus'`). The
# text below is actionable without quoting anything read from the environment.
CONFIG_ERROR_PRIVACY_MODE = (
    "PRIVACY_MODE is not a recognized boolean value. Use true/1/yes/on or "
    "false/0/no/off, or unset it to leave privacy mode off."
)
CONFIG_ERROR_FULLY_LOCAL_MODE = (
    "FULLY_LOCAL_MODE is not a recognized boolean value. Use true/1/yes/on or "
    "false/0/no/off, or unset it to leave fully local mode off."
)
CONFIG_ERROR_LLM_PROVIDER = (
    "LLM_PROVIDER is not a valid provider selection. Use 'openai' or 'ollama'; "
    "note that FULLY_LOCAL_MODE=true requires 'ollama'."
)


def build_index_status() -> IndexStatus:
    """
    Report active-index compatibility using startup-preflight semantics.

    Assumes the provider configuration already resolved cleanly — the caller
    checks that first — so the only failures handled here are filesystem ones.
    An unreadable index is reported structurally rather than raised, because
    this endpoint exists to describe problems, and the one problem it must
    never turn into an opaque 500 is a problem with the index it inspects.
    """

    persist_directory, collection_name = ingestion.active_index_config()
    expected = ingestion.active_embedding_fingerprint()

    try:
        exists = ingestion.index_exists(persist_directory)
        stored = ingestion.read_index_fingerprint(persist_directory) if exists else None
    except OSError:
        # PermissionError included. No exception text is carried into the
        # payload: persist_directory is already a repo-relative constant, and
        # the message could name an absolute path.
        return IndexStatus(
            persist_directory=persist_directory,
            collection_name=collection_name,
            exists=None,
            stored_fingerprint=None,
            expected_fingerprint=expected,
            compatibility=INDEX_UNREADABLE,
            reindex_required=False,
        )

    if not exists:
        compatibility = "missing_index"
        reindex_required = True
    elif stored is None:
        compatibility = "legacy_no_fingerprint"
        reindex_required = expected["embedding_provider"] == config.PROVIDER_OLLAMA
    elif stored.get("embedding_provider") != expected["embedding_provider"]:
        compatibility = "provider_mismatch"
        reindex_required = True
    elif stored.get("embedding_model") != expected["embedding_model"]:
        compatibility = "model_mismatch"
        reindex_required = True
    else:
        compatibility = "compatible"
        reindex_required = False

    return IndexStatus(
        persist_directory=persist_directory,
        collection_name=collection_name,
        exists=exists,
        stored_fingerprint=stored,
        expected_fingerprint=expected,
        compatibility=compatibility,
        reindex_required=reindex_required,
    )


def _config_error_status(preflight: PreflightStatus, message: str) -> RuntimeStatus:
    """Runtime status for a deployment whose configuration does not resolve."""

    return RuntimeStatus(
        provider=None,
        chat_model=None,
        embedding_provider=None,
        embedding_model=None,
        privacy_mode=None,
        local_mode=None,
        web_search_enabled_default=None,
        web_search_locked=None,
        web_fallback_policy_default=None,
        budgets=None,
        llm_request_timeout_seconds=None,
        index=None,
        preflight=preflight,
        config_error=message,
    )


def build_runtime_status(preflight: PreflightStatus) -> RuntimeStatus:
    """
    Assemble sanitized runtime status, reporting config errors structurally.

    Configuration resolution and index inspection are kept apart on purpose.
    Each config read gets its own narrow handler so the reported diagnostic
    names the variable that actually failed, and so a filesystem error from
    index inspection can never be mislabeled as a configuration error.
    """

    try:
        privacy_enabled = config.privacy_mode()
    except ValueError:
        return _config_error_status(preflight, CONFIG_ERROR_PRIVACY_MODE)

    try:
        config.fully_local_mode()
    except ValueError:
        return _config_error_status(preflight, CONFIG_ERROR_FULLY_LOCAL_MODE)

    try:
        # Raises on an invalid value and on the FULLY_LOCAL_MODE/LLM_PROVIDER
        # contradiction; one message covers both, since both are fixed by
        # setting LLM_PROVIDER to a value consistent with FULLY_LOCAL_MODE.
        provider = config.llm_provider()
    except ValueError:
        return _config_error_status(preflight, CONFIG_ERROR_LLM_PROVIDER)

    # Canonical effective-mode helper rather than a local re-derivation.
    # Cannot raise here: llm_provider() above already resolved.
    local_mode = config.local_mode_enabled()

    # The same predicate graph/engine.py::seed_state() applies, so the reported
    # default matches what every run actually resolves to. config.web_search_enabled()
    # accounts for PRIVACY_MODE but NOT for local mode, so consulting it alone
    # would advertise web search as on in a deployment that always forces it off.
    web_search_locked = privacy_enabled or local_mode
    web_search_enabled_default = False if web_search_locked else config.web_search_enabled()

    index = build_index_status()
    expected = index.expected_fingerprint

    return RuntimeStatus(
        provider=provider,
        chat_model=config.local_chat_model() if local_mode else OPENAI_CHAT_MODEL,
        embedding_provider=expected["embedding_provider"],
        embedding_model=expected["embedding_model"],
        privacy_mode=privacy_enabled,
        local_mode=local_mode,
        web_search_enabled_default=web_search_enabled_default,
        web_search_locked=web_search_locked,
        web_fallback_policy_default=config.web_fallback_policy(),
        budgets={
            "max_llm_calls_per_run": config.max_llm_calls_per_run(),
            "max_web_searches_per_run": config.max_web_searches_per_run(),
            "max_web_results_to_grade": config.max_web_results_to_grade(),
        },
        llm_request_timeout_seconds=config.llm_request_timeout_seconds(),
        index=index,
        preflight=preflight,
        config_error=None,
    )
