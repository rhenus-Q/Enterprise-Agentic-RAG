"""Quiet, keys-free corpus metadata access."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ingestion import CORPUS_DIR, DOCUMENT_CATEGORIES, corpus_source_key
from server.schemas import DocumentInfo


def _extract_title(path: Path) -> str:
    """
    Return the first Markdown H1 title without loading the document body.

    Falls back to the file stem when the document has no H1, and also when it
    cannot be read at all — an unreadable or non-UTF-8 file still has usable
    metadata, so it degrades to a weaker title instead of failing the listing.
    """

    try:
        with path.open(encoding="utf-8") as document:
            for line in document:
                if line.startswith("# "):
                    return line[2:].strip()
    except (OSError, UnicodeDecodeError):
        return path.stem

    return path.stem


def list_corpus_documents() -> list[DocumentInfo]:
    """
    List public metadata for every Markdown document in the corpus.

    Failures are isolated per file: one document that vanished between the
    glob and the stat, or that the process cannot read, must not turn the
    whole listing into an error. A file whose stat fails is skipped, because
    size and mtime cannot be reported honestly without it. Ordering stays
    deterministic (sorted by path), and no exception detail reaches the
    response.
    """

    documents = []

    for path in sorted(CORPUS_DIR.glob("*.md")):
        try:
            metadata = path.stat()
        except OSError:
            continue

        documents.append(
            DocumentInfo(
                source=corpus_source_key(path),
                file_name=path.name,
                title=_extract_title(path),
                document_category=DOCUMENT_CATEGORIES.get(path.name, "internal_document"),
                source_type="local_corpus",
                size_bytes=metadata.st_size,
                modified_at=datetime.fromtimestamp(metadata.st_mtime, UTC).isoformat(),
            )
        )

    return documents
