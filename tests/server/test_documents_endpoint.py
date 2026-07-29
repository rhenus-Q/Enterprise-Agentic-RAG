"""Filesystem-only contract tests for GET /api/documents."""

from datetime import datetime

from fastapi.testclient import TestClient

import ingestion
import main
from server import documents as document_access
from server.app import create_app

FINGERPRINT = {
    "embedding_provider": "openai",
    "embedding_model": "text-embedding-ada-002",
}


def test_documents_lists_sorted_metadata_without_document_bodies(monkeypatch, tmp_path):
    alpha_body = "ALPHA-DOCUMENT-BODY-MARKER"
    zeta_body = "ZETA-DOCUMENT-BODY-MARKER"
    alpha = tmp_path / "alpha.md"
    zeta = tmp_path / "zeta.md"
    zeta.write_text(f"# Zeta Policy\n\n{zeta_body}", encoding="utf-8")
    alpha.write_text(f"No H1 heading here.\n\n{alpha_body}", encoding="utf-8")

    monkeypatch.setattr(document_access, "CORPUS_DIR", tmp_path)
    monkeypatch.setattr(document_access, "DOCUMENT_CATEGORIES", {"zeta.md": "operations"})
    monkeypatch.setattr(main, "run_startup_preflight", lambda: None)
    monkeypatch.setattr(
        ingestion,
        "active_index_config",
        lambda: ("chroma_db", "agentic_rag_docs"),
    )
    monkeypatch.setattr(ingestion, "active_embedding_fingerprint", lambda: FINGERPRINT)
    monkeypatch.setattr(ingestion, "index_exists", lambda _path: True)
    monkeypatch.setattr(ingestion, "read_index_fingerprint", lambda _path: FINGERPRINT)

    with TestClient(create_app()) as client:
        response = client.get("/api/documents")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_count"] == 2
    assert [item["file_name"] for item in payload["documents"]] == [
        "alpha.md",
        "zeta.md",
    ]

    alpha_info, zeta_info = payload["documents"]
    assert alpha_info["title"] == "alpha"
    assert alpha_info["document_category"] == "internal_document"
    assert alpha_info["source"] == "data/acmecorp_internal_docs/alpha.md"
    assert alpha_info["source_type"] == "local_corpus"
    assert alpha_info["size_bytes"] == alpha.stat().st_size
    assert datetime.fromisoformat(alpha_info["modified_at"]).tzinfo is not None

    assert zeta_info["title"] == "Zeta Policy"
    assert zeta_info["document_category"] == "operations"
    assert zeta_info["source"] == "data/acmecorp_internal_docs/zeta.md"
    assert zeta_info["size_bytes"] == zeta.stat().st_size
    assert datetime.fromisoformat(zeta_info["modified_at"]).tzinfo is not None

    serialized = response.text
    assert alpha_body not in serialized
    assert zeta_body not in serialized
    for forbidden_key in ("body", "content", "page_content"):
        assert forbidden_key not in alpha_info
        assert forbidden_key not in zeta_info
