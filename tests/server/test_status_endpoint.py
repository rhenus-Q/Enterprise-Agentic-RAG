"""Contract and sanitization tests for GET /api/status."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import ingestion
import main
from server.app import create_app

OPENAI_FINGERPRINT = {
    "embedding_provider": "openai",
    "embedding_model": "text-embedding-ada-002",
}
LOCAL_FINGERPRINT = {
    "embedding_provider": "ollama",
    "embedding_model": "local-embedding-model",
}


def _patch_preflight(monkeypatch) -> None:
    monkeypatch.setattr(main, "run_startup_preflight", lambda: None)


def _patch_index(
    monkeypatch,
    *,
    expected,
    exists: bool = True,
    stored=None,
    persist_directory: str = "chroma_db",
) -> None:
    monkeypatch.setattr(
        ingestion,
        "active_index_config",
        lambda: (persist_directory, "agentic_rag_docs"),
    )
    monkeypatch.setattr(ingestion, "active_embedding_fingerprint", lambda: expected)
    monkeypatch.setattr(ingestion, "index_exists", lambda _path: exists)
    monkeypatch.setattr(ingestion, "read_index_fingerprint", lambda _path: stored)


def _get_status(monkeypatch) -> dict:
    _patch_preflight(monkeypatch)
    with TestClient(create_app()) as client:
        response = client.get("/api/status")
    assert response.status_code == 200
    return response.json()


def test_status_reports_openai_default_mode(monkeypatch):
    _patch_index(monkeypatch, expected=OPENAI_FINGERPRINT, stored=OPENAI_FINGERPRINT)

    payload = _get_status(monkeypatch)

    assert payload["provider"] == "openai"
    assert payload["chat_model"] == "gpt-5-mini"
    assert payload["embedding_provider"] == "openai"
    assert payload["privacy_mode"] is False
    assert payload["fully_local_mode"] is False
    assert payload["web_search_enabled_default"] is True
    assert payload["web_search_locked"] is False
    assert payload["config_error"] is None


def test_status_reports_privacy_lock(monkeypatch):
    monkeypatch.setenv("PRIVACY_MODE", "true")
    _patch_index(monkeypatch, expected=OPENAI_FINGERPRINT, stored=OPENAI_FINGERPRINT)

    payload = _get_status(monkeypatch)

    assert payload["privacy_mode"] is True
    assert payload["fully_local_mode"] is False
    assert payload["web_search_enabled_default"] is False
    assert payload["web_search_locked"] is True


def test_status_reports_resolved_local_mode(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LOCAL_CHAT_MODEL", "local-chat-model")
    monkeypatch.setenv("LOCAL_EMBEDDING_MODEL", "local-embedding-model")
    _patch_index(
        monkeypatch,
        expected=LOCAL_FINGERPRINT,
        stored=LOCAL_FINGERPRINT,
        persist_directory="chroma_db_local",
    )

    payload = _get_status(monkeypatch)

    assert payload["provider"] == "ollama"
    assert payload["chat_model"] == "local-chat-model"
    assert payload["embedding_provider"] == "ollama"
    assert payload["embedding_model"] == "local-embedding-model"
    assert payload["fully_local_mode"] is True
    assert payload["web_search_locked"] is True


def test_invalid_provider_is_a_structured_200_config_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bogus")

    payload = _get_status(monkeypatch)

    assert payload["provider"] is None
    assert payload["index"] is None
    assert payload["config_error"]
    assert "Invalid LLM_PROVIDER" in payload["config_error"]


@pytest.mark.parametrize(
    ("exists", "stored", "compatibility", "reindex_required"),
    [
        (False, None, "missing_index", True),
        (True, None, "legacy_no_fingerprint", False),
        (
            True,
            {
                "embedding_provider": "ollama",
                "embedding_model": "text-embedding-ada-002",
            },
            "provider_mismatch",
            True,
        ),
        (
            True,
            {
                "embedding_provider": "openai",
                "embedding_model": "different-model",
            },
            "model_mismatch",
            True,
        ),
        (True, OPENAI_FINGERPRINT, "compatible", False),
    ],
)
def test_status_reports_all_index_compatibility_states(
    monkeypatch,
    exists,
    stored,
    compatibility,
    reindex_required,
):
    _patch_index(
        monkeypatch,
        expected=OPENAI_FINGERPRINT,
        exists=exists,
        stored=stored,
    )

    payload = _get_status(monkeypatch)

    assert payload["index"]["compatibility"] == compatibility
    assert payload["index"]["reindex_required"] is reindex_required


def test_legacy_local_index_requires_reindex(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    _patch_index(
        monkeypatch,
        expected=LOCAL_FINGERPRINT,
        stored=None,
        persist_directory="chroma_db_local",
    )

    payload = _get_status(monkeypatch)

    assert payload["index"]["compatibility"] == "legacy_no_fingerprint"
    assert payload["index"]["reindex_required"] is True


def test_status_never_exposes_local_endpoint_or_absolute_paths(monkeypatch):
    sentinel = "https://private-ollama.internal.example:11434"
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", sentinel)
    _patch_index(
        monkeypatch,
        expected=LOCAL_FINGERPRINT,
        stored=LOCAL_FINGERPRINT,
        persist_directory="chroma_db_local",
    )

    payload = _get_status(monkeypatch)
    serialized = json.dumps(payload)

    assert sentinel not in serialized
    assert "private-ollama.internal.example" not in serialized
    assert "OLLAMA_BASE_URL" not in serialized
    assert "base_url" not in serialized
    assert Path(payload["index"]["persist_directory"]).is_absolute() is False
