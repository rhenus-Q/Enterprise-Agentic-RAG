"""Contract and sanitization tests for GET /api/status."""

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import ingestion
import main
import server
from graph import engine
from server.app import create_app
from server.status import (
    CONFIG_ERROR_FULLY_LOCAL_MODE,
    CONFIG_ERROR_LLM_PROVIDER,
    CONFIG_ERROR_PRIVACY_MODE,
)

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
    assert payload["local_mode"] is False
    assert payload["web_search_enabled_default"] is True
    assert payload["web_search_locked"] is False
    assert payload["config_error"] is None


def test_status_reports_privacy_lock(monkeypatch):
    monkeypatch.setenv("PRIVACY_MODE", "true")
    _patch_index(monkeypatch, expected=OPENAI_FINGERPRINT, stored=OPENAI_FINGERPRINT)

    payload = _get_status(monkeypatch)

    assert payload["privacy_mode"] is True
    assert payload["local_mode"] is False
    assert payload["web_search_enabled_default"] is False
    assert payload["web_search_locked"] is True


def test_status_reports_resolved_local_mode(monkeypatch):
    # WEB_SEARCH_ENABLED is explicitly ON so the assertions below prove the
    # local-mode lock rather than an ambient default: seed_state() forces web
    # search off for local mode, so the reported default must be False too.
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "true")
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
    assert payload["local_mode"] is True
    assert payload["web_search_enabled_default"] is False
    assert payload["web_search_locked"] is True


def test_local_mode_default_matches_the_engine_lock(monkeypatch):
    """The reported default must equal what seed_state() actually resolves."""

    monkeypatch.setenv("WEB_SEARCH_ENABLED", "true")
    monkeypatch.setenv("FULLY_LOCAL_MODE", "true")
    _patch_index(
        monkeypatch,
        expected=LOCAL_FINGERPRINT,
        stored=LOCAL_FINGERPRINT,
        persist_directory="chroma_db_local",
    )

    payload = _get_status(monkeypatch)
    seeded = engine.seed_state("Question")

    assert payload["web_search_enabled_default"] is False
    assert payload["web_search_locked"] is True
    assert seeded["web_search_enabled"] is False
    assert payload["web_search_enabled_default"] == seeded["web_search_enabled"]


def test_invalid_provider_is_a_structured_200_config_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bogus")

    payload = _get_status(monkeypatch)

    assert payload["provider"] is None
    assert payload["local_mode"] is None
    assert payload["index"] is None
    assert payload["config_error"] == CONFIG_ERROR_LLM_PROVIDER
    # Actionable, but the rejected value is never echoed back.
    assert "bogus" not in json.dumps(payload)


@pytest.mark.parametrize(
    ("variable", "expected_message"),
    [
        ("PRIVACY_MODE", CONFIG_ERROR_PRIVACY_MODE),
        ("FULLY_LOCAL_MODE", CONFIG_ERROR_FULLY_LOCAL_MODE),
    ],
)
def test_unparseable_mode_flags_name_the_failing_variable(
    monkeypatch,
    variable,
    expected_message,
):
    monkeypatch.setenv(variable, "sometimes-SENTINEL")

    payload = _get_status(monkeypatch)

    assert payload["config_error"] == expected_message
    assert variable in payload["config_error"]
    assert "SENTINEL" not in json.dumps(payload)


def test_contradictory_local_mode_reports_the_provider_diagnostic(monkeypatch):
    monkeypatch.setenv("FULLY_LOCAL_MODE", "true")
    monkeypatch.setenv("LLM_PROVIDER", "openai")

    payload = _get_status(monkeypatch)

    assert payload["config_error"] == CONFIG_ERROR_LLM_PROVIDER
    assert payload["provider"] is None


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


def _assert_index_unreadable(payload: dict, secret: str) -> None:
    """An unreadable index is structural, sanitized, and not a config error."""

    index = payload["index"]
    assert index["compatibility"] == "index_unreadable"
    # Unknown, not absent — and a permission problem is not fixed by reindexing.
    assert index["exists"] is None
    assert index["reindex_required"] is False
    assert index["stored_fingerprint"] is None
    assert payload["config_error"] is None
    # The rest of the runtime resolved fine and is still reported.
    assert payload["provider"] == "openai"

    serialized = json.dumps(payload)
    assert secret not in serialized
    assert "PermissionError" not in serialized
    assert "OSError" not in serialized
    assert Path(index["persist_directory"]).is_absolute() is False


def test_unreadable_index_directory_is_reported_structurally(monkeypatch):
    secret = "C:\\private\\absolute\\chroma_db"

    def deny(_path):
        raise PermissionError(f"[Errno 13] Permission denied: {secret}")

    _patch_preflight(monkeypatch)
    monkeypatch.setattr(
        ingestion,
        "active_index_config",
        lambda: ("chroma_db", "agentic_rag_docs"),
    )
    monkeypatch.setattr(ingestion, "active_embedding_fingerprint", lambda: OPENAI_FINGERPRINT)
    monkeypatch.setattr(ingestion, "index_exists", deny)

    with TestClient(create_app()) as client:
        response = client.get("/api/status")

    assert response.status_code == 200
    _assert_index_unreadable(response.json(), secret)


def test_unreadable_fingerprint_is_reported_structurally(monkeypatch):
    secret = "/srv/private/chroma_db/embedding_fingerprint.json"

    def fail_read(_path):
        raise OSError(f"[Errno 5] Input/output error: {secret}")

    _patch_preflight(monkeypatch)
    monkeypatch.setattr(
        ingestion,
        "active_index_config",
        lambda: ("chroma_db", "agentic_rag_docs"),
    )
    monkeypatch.setattr(ingestion, "active_embedding_fingerprint", lambda: OPENAI_FINGERPRINT)
    monkeypatch.setattr(ingestion, "index_exists", lambda _path: True)
    monkeypatch.setattr(ingestion, "read_index_fingerprint", fail_read)

    with TestClient(create_app()) as client:
        response = client.get("/api/status")

    assert response.status_code == 200
    _assert_index_unreadable(response.json(), secret)


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


def test_server_modules_do_not_import_chains_or_nodes():
    """ADR 016 / structure.md §14 / CLAUDE.md all state that server/ imports
    only graph.engine, graph.config, graph.consts, graph.formatting,
    ingestion, and main -- never graph.nodes.* or the chain factories.

    A sys.modules check would not catch a violation here: importing
    graph.engine already pulls in graph.graph (to compile the StateGraph),
    which legitimately imports graph.chains.* and graph.nodes for real, so
    both are already present in sys.modules by the time any server test runs.
    What must stay true is that no server/*.py file itself contains an import
    statement naming graph.chains or graph.nodes -- a lexical check on the
    source, not a runtime check on the import graph.
    """

    server_dir = Path(server.__file__).parent
    forbidden = re.compile(r"^\s*(from|import)\s+graph\.(chains|nodes)\b", re.MULTILINE)

    offending = [
        path.name
        for path in sorted(server_dir.glob("*.py"))
        if forbidden.search(path.read_text(encoding="utf-8"))
    ]

    assert offending == []
