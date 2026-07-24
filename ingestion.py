"""
ingestion.py

Purpose:
- Load the synthetic AcmeCorp internal-document corpus (local Markdown files)
- Split documents into smaller chunks
- Convert chunks into embeddings
- Store them in a Chroma vector database (idempotent rebuild)
- Expose a retriever for the LangGraph retrieve node

The corpus under data/acmecorp_internal_docs/ is entirely fictional synthetic
content (no real company data) — replace it with real internal documents in
an actual deployment. Each document carries provenance metadata (source,
title, source_type, document_category) that survives chunking and feeds the
user-facing Sources section in main.py.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from graph.config import (
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    local_embedding_model,
    local_mode_enabled,
    ollama_base_url,
)

load_dotenv()


# Corpus location, anchored to this file's directory so ingestion works from any CWD.
CORPUS_DIR = Path(__file__).parent / "data" / "acmecorp_internal_docs"

# document_category metadata per file (provenance / future filtering).
# Files not listed here fall back to "internal_document".
DOCUMENT_CATEGORIES = {
    "vpn_policy.md": "it_security",
    "incident_response_playbook.md": "it_security",
    "expense_reimbursement_policy.md": "finance",
    "on_call_escalation_policy.md": "operations",
    "data_retention_policy.md": "compliance",
    "employee_onboarding_guide.md": "hr",
}


CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "agentic_rag_docs"

# Local-provider index. A separate directory and collection so the two indexes
# coexist: switching LLM_PROVIDER between two already-built matching indexes
# needs no re-ingestion, and ingesting for one provider never drops the other
# provider's collection. The OpenAI path and collection name above are
# deliberately unchanged, so indexes built before local mode existed stay valid.
LOCAL_CHROMA_PATH = "chroma_db_local"
LOCAL_COLLECTION_NAME = "agentic_rag_docs_local"

# The model OpenAIEmbeddings() uses when constructed with no arguments
# (langchain-openai's default). Recorded in the fingerprint below so an index
# is never queried with an embedding model other than the one that built it.
OPENAI_EMBEDDING_MODEL = "text-embedding-ada-002"

# Sidecar file holding the index fingerprint, written inside the persist
# directory so it travels with the index it describes and is covered by the
# same .gitignore entry. Chroma's collection metadata would be the tidier home,
# but langchain-chroma accepts `collection_metadata` only as a constructor
# argument and exposes no public reader for it (see docs/adr/014).
FINGERPRINT_FILENAME = "embedding_fingerprint.json"


def _extract_title(text: str, fallback: str) -> str:
    """Return the first Markdown H1 heading, or the fallback if none exists."""

    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def load_documents():
    """
    Load the local Markdown corpus from CORPUS_DIR.

    Each file becomes one Document with provenance metadata:
    - source: repo-relative path (stable citation key)
    - title: the document's H1 heading (shown in the Sources section)
    - source_type: "local_corpus" (distinguishes from the web supplement)
    - document_category: coarse policy domain

    Returns:
        List[Document]: LangChain Document objects.
    """

    docs = []

    for path in sorted(CORPUS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        docs.append(
            Document(
                page_content=text,
                metadata={
                    "source": f"data/acmecorp_internal_docs/{path.name}",
                    "title": _extract_title(text, path.stem),
                    "source_type": "local_corpus",
                    "document_category": DOCUMENT_CATEGORIES.get(path.name, "internal_document"),
                },
            )
        )

    print(f"Loaded {len(docs)} corpus documents from {CORPUS_DIR}.")
    return docs


def split_documents(documents):
    """
    Split documents into overlapping chunks sized for embedding and retrieval.

    Returns:
        List[Document]: Chunked documents (metadata is copied to every chunk).
    """

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )

    splits = text_splitter.split_documents(documents)

    print(f"Split into {len(splits)} chunks.")
    return splits


def _chunk_ids(splits):
    """
    Deterministic per-chunk ids: "<source>::chunk-<index>".

    Stable ids plus the collection reset in build_vectorstore make ingestion
    idempotent — re-running replaces the index instead of appending
    duplicate chunks.
    """

    ids = []
    counters = {}

    for chunk in splits:
        source = chunk.metadata["source"]
        index = counters.get(source, 0)
        counters[source] = index + 1
        ids.append(f"{source}::chunk-{index}")

    return ids


def _ollama_embeddings_class() -> Any:
    """
    Import OllamaEmbeddings lazily.

    langchain-ollama is only needed when local mode is selected, so importing
    it here keeps this module importable (and the OpenAI path working) where
    the package is absent, and gives tests a seam to patch.
    """

    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings


def get_embeddings() -> Any:
    """
    Build the embedding model for the active provider (LLM_PROVIDER).

    Called from build_vectorstore() and get_retriever(), never at import time,
    so importing this module still needs no API key, no network, and no
    langchain-ollama install.
    """

    if local_mode_enabled():
        ollama_embeddings = _ollama_embeddings_class()
        return ollama_embeddings(model=local_embedding_model(), base_url=ollama_base_url())

    return OpenAIEmbeddings()


def active_index_config() -> tuple[str, str]:
    """(persist_directory, collection_name) of the active provider's index."""

    if local_mode_enabled():
        return LOCAL_CHROMA_PATH, LOCAL_COLLECTION_NAME

    return CHROMA_PATH, COLLECTION_NAME


def active_embedding_fingerprint() -> dict[str, str]:
    """
    Fingerprint of the active embedding configuration: provider plus model.

    Computed from configuration alone — no client is constructed — so startup
    checks can compare it against the stored fingerprint without an API key or
    a reachable endpoint.

    A dimension mismatch (1536 vs. 1024) already fails loudly on its own. The
    fingerprint exists for the silent case: two different embedding models of
    the *same* dimension produce no error, so retrieval would return
    meaningless neighbours and the graph would grade and answer over garbage.
    """

    if local_mode_enabled():
        return {
            "embedding_provider": PROVIDER_OLLAMA,
            "embedding_model": local_embedding_model(),
        }

    return {
        "embedding_provider": PROVIDER_OPENAI,
        "embedding_model": OPENAI_EMBEDDING_MODEL,
    }


def fingerprint_path(persist_directory: str) -> Path:
    """Location of the fingerprint sidecar for a persist directory."""

    return Path(persist_directory) / FINGERPRINT_FILENAME


def write_index_fingerprint(persist_directory: str) -> None:
    """Record which embedding configuration built the index in this directory."""

    path = fingerprint_path(persist_directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(active_embedding_fingerprint(), indent=2),
        encoding="utf-8",
    )


def read_index_fingerprint(persist_directory: str) -> dict[str, str] | None:
    """
    Read the stored fingerprint, or None when it is missing or unreadable.

    None is the legacy case — an index built before fingerprints existed. What
    that means is the caller's decision: accepted in OpenAI mode (no migration,
    no re-ingest), treated as a mismatch in local mode, since a missing
    fingerprint proves the index is not the local one.
    """

    try:
        data = json.loads(fingerprint_path(persist_directory).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    return data if isinstance(data, dict) else None


def index_exists(persist_directory: str) -> bool:
    """
    True when the persist directory exists and holds a built index.

    Deliberately checks only for a non-empty directory rather than Chroma's
    internal file layout, which is not a public contract.
    """

    path = Path(persist_directory)
    return path.is_dir() and any(path.iterdir())


def build_vectorstore():
    """
    Build the local Chroma vector store from the corpus (idempotent).

    The existing collection is dropped before re-indexing, so re-running
    ingestion never duplicates chunks and removed corpus files disappear
    from the index. Tradeoff: a run that fails mid-ingestion leaves the
    knowledge base empty until ingestion is re-run successfully.

    Returns:
        Chroma: A Chroma vector store instance.
    """

    documents = load_documents()
    splits = split_documents(documents)

    embeddings = get_embeddings()
    persist_directory, collection_name = active_index_config()

    # Idempotent rebuild: drop any previous index of the same collection.
    # Scoped to the ACTIVE provider's collection, so building the local index
    # can never delete the OpenAI one (or the other way round).
    Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_directory,
    ).delete_collection()
    print(f"Cleared existing collection '{collection_name}' (idempotent rebuild).")

    vectorstore = Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        ids=_chunk_ids(splits),
        collection_name=collection_name,
        persist_directory=persist_directory,
    )

    # Written after the index is built, so a fingerprint's presence means the
    # build finished.
    write_index_fingerprint(persist_directory)

    print(f"Vector store built successfully at {persist_directory} ('{collection_name}').")
    return vectorstore


@lru_cache(maxsize=1)
def get_retriever():
    """
    Create a retriever from the Chroma vector store.

    Cached so the Chroma client / embeddings are constructed only once, and only
    when first called at runtime (not at import time). The cache is also why
    the provider is a process-level mode: this retriever is bound to one
    embedding space for the lifetime of the process.

    Returns:
        VectorStoreRetriever
    """

    embeddings = get_embeddings()
    persist_directory, collection_name = active_index_config()

    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_directory,
    )

    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    return retriever


if __name__ == "__main__":
    build_vectorstore()
