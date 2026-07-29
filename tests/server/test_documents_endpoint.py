"""Filesystem-only contract tests for GET /api/documents."""

from datetime import datetime
from pathlib import Path

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
    # The key comes from the shared helper, not a literal prefix: a corpus
    # outside the repo degrades to the bare file name rather than keeping a
    # stale "data/acmecorp_internal_docs/" that no longer describes anything.
    assert alpha_info["source"] == ingestion.corpus_source_key(alpha)
    assert alpha_info["source"] == "alpha.md"
    assert alpha_info["source_type"] == "local_corpus"
    assert alpha_info["size_bytes"] == alpha.stat().st_size
    assert datetime.fromisoformat(alpha_info["modified_at"]).tzinfo is not None

    assert zeta_info["title"] == "Zeta Policy"
    assert zeta_info["document_category"] == "operations"
    assert zeta_info["source"] == ingestion.corpus_source_key(zeta)
    assert zeta_info["size_bytes"] == zeta.stat().st_size
    assert datetime.fromisoformat(zeta_info["modified_at"]).tzinfo is not None

    serialized = response.text
    assert alpha_body not in serialized
    assert zeta_body not in serialized
    for forbidden_key in ("body", "content", "page_content"):
        assert forbidden_key not in alpha_info
        assert forbidden_key not in zeta_info


def _patch_status_index(monkeypatch) -> None:
    monkeypatch.setattr(
        ingestion,
        "active_index_config",
        lambda: ("chroma_db", "agentic_rag_docs"),
    )
    monkeypatch.setattr(ingestion, "active_embedding_fingerprint", lambda: FINGERPRINT)
    monkeypatch.setattr(ingestion, "index_exists", lambda _path: True)
    monkeypatch.setattr(ingestion, "read_index_fingerprint", lambda _path: FINGERPRINT)


def test_document_sources_match_the_keys_ingestion_writes():
    """
    /api/documents and Ask citations must agree on the source key.

    Ask citations carry whatever `source` ingestion wrote into Document
    metadata, so comparing the listing against load_documents() over the real
    corpus is what proves the two cannot drift apart.
    """

    listed = {info.source for info in document_access.list_corpus_documents()}
    ingested = {document.metadata["source"] for document in ingestion.load_documents()}

    assert listed
    assert listed == ingested
    assert all(source.startswith("data/acmecorp_internal_docs/") for source in listed)
    assert not any(Path(source).is_absolute() for source in listed)
    assert not any("\\" in source for source in listed)


def test_unreadable_file_does_not_break_the_listing(monkeypatch, tmp_path):
    sentinel = "STAT-FAILURE-SENTINEL"
    good = tmp_path / "good.md"
    broken = tmp_path / "broken.md"
    undecodable = tmp_path / "undecodable.md"

    good.write_text("# Good Policy\n\nbody", encoding="utf-8")
    broken.write_text("# Broken Policy\n\nbody", encoding="utf-8")
    # Real latin-1 bytes: reading this as UTF-8 raises UnicodeDecodeError.
    undecodable.write_bytes(b"# Caf\xe9 Policy\n\nbody\n")

    real_stat = Path.stat

    def flaky_stat(self, *args, **kwargs):
        if self.name == "broken.md":
            raise OSError(f"[Errno 13] {sentinel}")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky_stat)
    monkeypatch.setattr(document_access, "CORPUS_DIR", tmp_path)
    monkeypatch.setattr(document_access, "DOCUMENT_CATEGORIES", {})
    monkeypatch.setattr(main, "run_startup_preflight", lambda: None)
    _patch_status_index(monkeypatch)

    with TestClient(create_app()) as client:
        response = client.get("/api/documents")

    assert response.status_code == 200
    payload = response.json()

    # The file whose stat failed is skipped; the rest survive, still sorted.
    assert [item["file_name"] for item in payload["documents"]] == [
        "good.md",
        "undecodable.md",
    ]
    assert payload["document_count"] == 2

    by_name = {item["file_name"]: item for item in payload["documents"]}
    assert by_name["good.md"]["title"] == "Good Policy"
    # Title unreadable as UTF-8 -> stem fallback, document still listed.
    assert by_name["undecodable.md"]["title"] == "undecodable"

    assert sentinel not in response.text
    assert "Errno" not in response.text
    assert "Broken Policy" not in response.text


def test_unreadable_title_falls_back_without_leaking_errors(monkeypatch, tmp_path):
    sentinel = "OPEN-FAILURE-SENTINEL"
    locked = tmp_path / "locked.md"
    locked.write_text("# Locked Policy\n\nbody", encoding="utf-8")

    real_open = Path.open

    def flaky_open(self, *args, **kwargs):
        if self.name == "locked.md":
            raise PermissionError(f"[Errno 13] {sentinel}")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", flaky_open)
    monkeypatch.setattr(document_access, "CORPUS_DIR", tmp_path)
    monkeypatch.setattr(document_access, "DOCUMENT_CATEGORIES", {})
    monkeypatch.setattr(main, "run_startup_preflight", lambda: None)
    _patch_status_index(monkeypatch)

    with TestClient(create_app()) as client:
        response = client.get("/api/documents")

    assert response.status_code == 200
    payload = response.json()

    assert payload["document_count"] == 1
    assert payload["documents"][0]["title"] == "locked"
    assert payload["documents"][0]["file_name"] == "locked.md"
    assert sentinel not in response.text
    assert "Locked Policy" not in response.text
