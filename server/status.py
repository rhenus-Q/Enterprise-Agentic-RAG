"""Keys-free runtime and index status assembly."""

from __future__ import annotations

import ingestion
from graph import config
from graph.chains._llm import OPENAI_CHAT_MODEL
from server.schemas import IndexStatus, PreflightStatus, RuntimeStatus


def build_index_status() -> IndexStatus:
    """Report active-index compatibility using startup-preflight semantics."""

    persist_directory, collection_name = ingestion.active_index_config()
    expected = ingestion.active_embedding_fingerprint()
    exists = ingestion.index_exists(persist_directory)
    stored = ingestion.read_index_fingerprint(persist_directory) if exists else None

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


def build_runtime_status(preflight: PreflightStatus) -> RuntimeStatus:
    """Assemble sanitized runtime status, reporting config errors structurally."""

    try:
        privacy_enabled = config.privacy_mode()
        provider = config.llm_provider()
        local_mode = provider == config.PROVIDER_OLLAMA
        index = build_index_status()
        expected = index.expected_fingerprint

        return RuntimeStatus(
            provider=provider,
            chat_model=config.local_chat_model() if local_mode else OPENAI_CHAT_MODEL,
            embedding_provider=expected["embedding_provider"],
            embedding_model=expected["embedding_model"],
            privacy_mode=privacy_enabled,
            fully_local_mode=local_mode,
            web_search_enabled_default=config.web_search_enabled(),
            web_search_locked=privacy_enabled or local_mode,
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
    except ValueError as exc:
        return RuntimeStatus(
            provider=None,
            chat_model=None,
            embedding_provider=None,
            embedding_model=None,
            privacy_mode=None,
            fully_local_mode=None,
            web_search_enabled_default=None,
            web_search_locked=None,
            web_fallback_policy_default=None,
            budgets=None,
            llm_request_timeout_seconds=None,
            index=None,
            preflight=preflight,
            config_error=str(exc),
        )
