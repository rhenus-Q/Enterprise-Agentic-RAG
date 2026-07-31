"""
Tests for answer provenance (the "Sources:" section).

format_sources / format_answer in main.py build a deterministic Sources
section from the final working documents' metadata after the graph finishes —
no LLM is involved, no document content is exposed. Local corpus documents
and the web supplement are distinguished by the shared WEB_SEARCH_SOURCE
metadata marker.

The last section covers the other end of the same contract: the pure helpers in
ingestion.py that WRITE that metadata (title, source key, chunk ids), so the
producer and the consumer of a citation are pinned in one place.

All external seams are mocked -- no API keys or network required.
"""

import importlib
from types import SimpleNamespace

from langchain_core.documents import Document

import graph.graph as graph_module
import ingestion as ingestion_module
from graph.consts import (
    STOP_REASON_WEB_SEARCH_ERROR,
    WEB_SEARCH_SOURCE,
    WEBSEARCH,
)
from main import (
    LOCAL_SOURCE_FALLBACK_LABEL,
    SOURCES_HEADER,
    WEB_SEARCH_ERROR_NOTE,
    WEB_SOURCE_FALLBACK_LABEL,
    format_answer,
    format_sources,
)


def _local_doc(content="chunk", **metadata):
    return Document(page_content=content, metadata=metadata)


def _web_doc(content="web content", search_query="some query"):
    return Document(
        page_content=content,
        metadata={
            "source": WEB_SEARCH_SOURCE,
            "source_type": "web",
            "search_query": search_query,
        },
    )


# ---------------------------------------------------------------------------
# format_sources: labels, fallbacks, deduplication
# ---------------------------------------------------------------------------


def test_local_doc_labeled_by_title_when_present():
    sources = format_sources([_local_doc(title="RAG Concepts", source="https://x/rag")])

    assert sources == f"{SOURCES_HEADER}\n- Local corpus: RAG Concepts"


def test_local_doc_falls_back_to_source_url():
    sources = format_sources([_local_doc(source="https://x/rag")])

    assert sources == f"{SOURCES_HEADER}\n- Local corpus: https://x/rag"


def test_local_doc_without_metadata_uses_safe_label():
    sources = format_sources([_local_doc()])

    assert sources == f"{SOURCES_HEADER}\n- {LOCAL_SOURCE_FALLBACK_LABEL}"


def test_web_doc_labeled_by_search_query():
    sources = format_sources([_web_doc(search_query="rewritten query")])

    assert sources == f'{SOURCES_HEADER}\n- Web search: "rewritten query"'


def test_web_doc_without_query_uses_safe_label():
    bare_web = Document(page_content="w", metadata={"source": WEB_SEARCH_SOURCE})

    sources = format_sources([bare_web])

    assert sources == f"{SOURCES_HEADER}\n- {WEB_SOURCE_FALLBACK_LABEL}"


def _web_doc_with_pages(*entries, content="web content", search_query="some query"):
    return Document(
        page_content=content,
        metadata={
            "source": WEB_SEARCH_SOURCE,
            "source_type": "web",
            "search_query": search_query,
            "web_sources": list(entries),
        },
    )


def test_web_doc_with_pages_shows_title_and_url():
    sources = format_sources([_web_doc_with_pages({"title": "Page A", "url": "https://a.example"})])

    assert sources == f"{SOURCES_HEADER}\n- Web search: Page A — https://a.example"


def test_web_doc_with_pages_lists_each_page_once():
    sources = format_sources(
        [
            _web_doc_with_pages(
                {"title": "Page A", "url": "https://a.example"},
                {"title": "Page B", "url": "https://b.example"},
            )
        ]
    )

    assert sources == (
        f"{SOURCES_HEADER}\n"
        "- Web search: Page A — https://a.example\n"
        "- Web search: Page B — https://b.example"
    )


def test_web_page_without_title_falls_back_to_url():
    sources = format_sources([_web_doc_with_pages({"title": "", "url": "https://a.example"})])

    assert sources == f"{SOURCES_HEADER}\n- Web search: https://a.example"


def test_web_doc_with_empty_web_sources_falls_back_to_query():
    # No usable URLs -> the existing query-level citation.
    sources = format_sources([_web_doc_with_pages(search_query="fallback query")])

    assert sources == f'{SOURCES_HEADER}\n- Web search: "fallback query"'


def test_malformed_web_source_entries_are_skipped():
    sources = format_sources(
        [
            _web_doc_with_pages(
                "not-a-dict",
                {"title": "No URL"},
                {"title": "Good", "url": "https://good.example"},
            )
        ]
    )

    assert sources == f"{SOURCES_HEADER}\n- Web search: Good — https://good.example"


def test_web_page_sources_never_expose_document_content():
    secret_content = "SECRET-WEB-CONTENT"
    sources = format_sources(
        [
            _web_doc_with_pages(
                {"title": "Page A", "url": "https://a.example"},
                content=secret_content,
            )
        ]
    )

    assert secret_content not in sources


def test_local_and_web_sources_are_distinguished():
    sources = format_sources(
        [_local_doc(title="RAG Concepts"), _web_doc(search_query="latest news")]
    )

    assert "- Local corpus: RAG Concepts" in sources
    assert '- Web search: "latest news"' in sources


def test_duplicate_sources_are_deduplicated():
    # Several chunks of the same page must cite it once.
    docs = [
        _local_doc("chunk 1", source="https://x/rag"),
        _local_doc("chunk 2", source="https://x/rag"),
        _local_doc("chunk 3", source="https://x/other"),
    ]

    sources = format_sources(docs)

    assert sources.count("https://x/rag") == 1
    assert sources.count("https://x/other") == 1


def test_no_documents_means_no_sources_section():
    assert format_sources([]) == ""
    assert format_sources(None) == ""


def test_sources_never_expose_document_content():
    secret_content = "SECRET-INTERNAL-CONTENT"
    sources = format_sources(
        [_local_doc(secret_content, source="https://x/rag"), _web_doc(secret_content)]
    )

    assert secret_content not in sources


# ---------------------------------------------------------------------------
# format_answer: composition with answers and caveats
# ---------------------------------------------------------------------------


def test_format_answer_appends_sources_after_the_answer():
    result = {
        "generation": "The answer.",
        "stop_reason": "",
        "documents": [_local_doc(title="RAG Concepts")],
    }

    assert format_answer(result) == ("The answer.\n\nSources:\n- Local corpus: RAG Concepts")


def test_format_answer_without_documents_is_unchanged():
    assert format_answer({"generation": "Plain.", "stop_reason": "", "documents": []}) == "Plain."


def test_format_answer_caveat_and_sources_coexist_caveat_first():
    # An error caveat must stay directly under the answer so the sources
    # listed afterwards never imply the answer was fully verified.
    result = {
        "generation": "Partial answer.",
        "stop_reason": STOP_REASON_WEB_SEARCH_ERROR,
        "documents": [_local_doc(title="RAG Concepts")],
    }

    formatted = format_answer(result)

    assert formatted.startswith("Partial answer.")
    assert WEB_SEARCH_ERROR_NOTE in formatted
    assert "- Local corpus: RAG Concepts" in formatted
    assert formatted.index(WEB_SEARCH_ERROR_NOTE) < formatted.index(SOURCES_HEADER)


# ---------------------------------------------------------------------------
# Compiled graph end-to-end
# ---------------------------------------------------------------------------


def _patch_seams(monkeypatch, retrieved_docs):
    """Mock every external seam for an end-to-end provenance run."""

    retrieve_module = importlib.import_module("graph.nodes.retrieve")
    grade_module = importlib.import_module("graph.nodes.grade_documents")
    generate_module = importlib.import_module("graph.nodes.generate")
    web_module = importlib.import_module("graph.nodes.web_search")

    monkeypatch.setattr(
        retrieve_module,
        "get_node_retriever",
        lambda: SimpleNamespace(invoke=lambda q: retrieved_docs),
    )
    monkeypatch.setattr(
        grade_module,
        "get_retrieval_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_relevant=True)),
    )
    monkeypatch.setattr(
        web_module,
        "get_retrieval_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_relevant=True)),
    )
    monkeypatch.setattr(
        web_module,
        "get_web_search_tool",
        lambda: SimpleNamespace(invoke=lambda p: [{"content": "web result"}]),
    )
    monkeypatch.setattr(
        generate_module,
        "generate_answer",
        lambda question, documents, retry_feedback="": "FINAL ANSWER",
    )
    monkeypatch.setattr(
        graph_module,
        "get_hallucination_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_grounded=True)),
    )
    monkeypatch.setattr(
        graph_module,
        "get_answer_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(answers_question=True)),
    )


def _initial_state(question="Q"):
    return {
        "question": question,
        "documents": [],
        "generation": "",
        "web_search": False,
        "web_search_enabled": True,
        "retries": 0,
        "stop_reason": "",
        "retry_feedback": "",
        "search_query": "",
        "llm_call_count": 0,
        "web_search_count": 0,
        "web_result_grading_count": 0,
    }


def test_app_local_answer_cites_retrieved_sources(monkeypatch):
    monkeypatch.setattr(
        graph_module,
        "get_question_router",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(datasource="retrieve")),
    )
    _patch_seams(
        monkeypatch,
        retrieved_docs=[
            _local_doc("c1", source="https://x/rag", title="RAG Concepts"),
            _local_doc("c2", source="https://x/rag", title="RAG Concepts"),
        ],
    )

    result = graph_module.app.invoke(_initial_state())
    formatted = format_answer(result)

    assert formatted.startswith("FINAL ANSWER")
    assert formatted.count("- Local corpus: RAG Concepts") == 1  # deduplicated
    assert "Web search" not in formatted


def test_app_web_routed_answer_cites_the_search(monkeypatch):
    # The mocked tool returns no URLs, so provenance falls back to the
    # query-level citation.
    monkeypatch.setattr(
        graph_module,
        "get_question_router",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(datasource=WEBSEARCH)),
    )
    _patch_seams(monkeypatch, retrieved_docs=[])

    result = graph_module.app.invoke(_initial_state(question="current events"))
    formatted = format_answer(result)

    assert formatted.startswith("FINAL ANSWER")
    assert '- Web search: "current events"' in formatted
    assert "Local corpus" not in formatted


def test_app_web_routed_answer_cites_actual_pages_when_urls_present(monkeypatch):
    # With URL-bearing Tavily results (langchain-tavily dict shape), the
    # Sources section cites the actual pages instead of the query.
    monkeypatch.setattr(
        graph_module,
        "get_question_router",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(datasource=WEBSEARCH)),
    )
    _patch_seams(monkeypatch, retrieved_docs=[])

    web_module = importlib.import_module("graph.nodes.web_search")
    monkeypatch.setattr(
        web_module,
        "get_web_search_tool",
        lambda: SimpleNamespace(
            invoke=lambda p: {
                "results": [
                    {
                        "content": "web result",
                        "url": "https://news.example/story",
                        "title": "Big Story",
                    }
                ]
            }
        ),
    )

    result = graph_module.app.invoke(_initial_state(question="current events"))
    formatted = format_answer(result)

    assert formatted.startswith("FINAL ANSWER")
    assert "- Web search: Big Story — https://news.example/story" in formatted
    assert '"current events"' not in formatted  # page-level beats query-level
    assert "Local corpus" not in formatted


# ---------------------------------------------------------------------------
# ingestion.py -- the pure helpers that produce the metadata above
# ---------------------------------------------------------------------------
# Loading, titling and chunking only: no Chroma, no embeddings, no API keys.
# The Sources section, /api/documents and the eval harness's provenance checks
# all read metadata written here, and idempotent re-ingestion is nothing more
# than _chunk_ids() being deterministic.


def test_extract_title_uses_the_h1_heading():
    text = "---\nfront matter\n---\n\n# VPN Access Policy\n\nBody text.\n"

    assert ingestion_module._extract_title(text, "vpn_policy") == "VPN Access Policy"


def test_extract_title_falls_back_when_the_document_has_no_h1():
    # A "## Section" heading is not an H1, so the fallback (the file stem) is
    # what ends up in the Sources line.
    text = "no heading here\n\n## Section\n"

    assert ingestion_module._extract_title(text, "vpn_policy") == "vpn_policy"


def test_corpus_source_key_is_a_repo_relative_posix_path():
    path = ingestion_module.CORPUS_DIR / "vpn_policy.md"

    assert ingestion_module.corpus_source_key(path) == "data/acmecorp_internal_docs/vpn_policy.md"


def test_corpus_source_key_outside_the_repository_degrades_to_the_file_name(tmp_path):
    # The key is a public identifier served over HTTP, so a corpus outside the
    # repo must not leak the server's filesystem layout.
    outside = tmp_path / "somewhere" / "private" / "doc.md"

    assert ingestion_module.corpus_source_key(outside) == "doc.md"


def test_load_documents_attaches_full_provenance_metadata(monkeypatch, tmp_path):
    (tmp_path / "vpn_policy.md").write_text("# VPN Access Policy\n\nBody.\n", encoding="utf-8")
    (tmp_path / "unlisted_note.md").write_text("plain note\n", encoding="utf-8")
    monkeypatch.setattr(ingestion_module, "CORPUS_DIR", tmp_path)

    metadata = {doc.metadata["source"]: doc.metadata for doc in ingestion_module.load_documents()}

    assert set(metadata) == {"vpn_policy.md", "unlisted_note.md"}
    assert metadata["vpn_policy.md"]["title"] == "VPN Access Policy"
    assert metadata["vpn_policy.md"]["document_category"] == "it_security"
    # Unmapped file: title falls back to the stem, category to the generic one.
    assert metadata["unlisted_note.md"]["title"] == "unlisted_note"
    assert metadata["unlisted_note.md"]["document_category"] == "internal_document"
    assert {entry["source_type"] for entry in metadata.values()} == {"local_corpus"}


def test_metadata_survives_chunking():
    # Provenance is attached per document but cited per chunk, so every chunk
    # has to carry the whole metadata dict unchanged.
    original = {
        "source": "data/acmecorp_internal_docs/vpn_policy.md",
        "title": "VPN Access Policy",
        "source_type": "local_corpus",
        "document_category": "it_security",
    }

    chunks = ingestion_module.split_documents(
        [Document(page_content="sentence. " * 400, metadata=dict(original))]
    )

    assert len(chunks) > 1  # the document really was split
    assert all(chunk.metadata == original for chunk in chunks)


def test_chunk_ids_are_deterministic_and_unique_within_a_document():
    # "Re-running ingestion never duplicates chunks" IS this determinism: the
    # same corpus must produce the same ids so the rebuild replaces rows.
    splits = [
        Document(page_content="a", metadata={"source": "docs/a.md"}),
        Document(page_content="b", metadata={"source": "docs/a.md"}),
        Document(page_content="c", metadata={"source": "docs/b.md"}),
    ]

    ids = ingestion_module._chunk_ids(splits)

    assert ids == ["docs/a.md::chunk-0", "docs/a.md::chunk-1", "docs/b.md::chunk-0"]
    assert ingestion_module._chunk_ids(splits) == ids
    assert len(set(ids)) == len(ids)
