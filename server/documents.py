"""Quiet, keys-free corpus metadata access."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ingestion import CORPUS_DIR, DOCUMENT_CATEGORIES
from server.schemas import DocumentInfo


def _extract_title(path: Path) -> str:
    """Return the first Markdown H1 title without loading the document body."""

    with path.open(encoding="utf-8") as document:
        for line in document:
            if line.startswith("# "):
                return line[2:].strip()

    return path.stem


def list_corpus_documents() -> list[DocumentInfo]:
    """List public metadata for every Markdown document in the corpus."""

    documents = []

    for path in sorted(CORPUS_DIR.glob("*.md")):
        metadata = path.stat()
        documents.append(
            DocumentInfo(
                source=f"data/acmecorp_internal_docs/{path.name}",
                file_name=path.name,
                title=_extract_title(path),
                document_category=DOCUMENT_CATEGORIES.get(path.name, "internal_document"),
                source_type="local_corpus",
                size_bytes=metadata.st_size,
                modified_at=datetime.fromtimestamp(metadata.st_mtime, UTC).isoformat(),
            )
        )

    return documents
