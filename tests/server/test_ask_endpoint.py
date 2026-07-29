"""Contract tests for POST /api/ask."""

import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document

import main
from graph import engine, formatting
from graph.consts import WEB_SEARCH_SOURCE
from server.app import create_app


def _answer_result(*, stop_reason: str = "") -> engine.AnswerResult:
    local_content = "L" * 350
    local_metadata = {
        "source": "data/acmecorp_internal_docs/vpn_policy.md",
        "title": "VPN Access Policy",
        "document_category": "it_security",
    }
    documents = [
        Document(page_content=local_content, metadata=local_metadata),
        Document(page_content="duplicate chunk", metadata=local_metadata),
        Document(
            page_content="web supplement",
            metadata={
                "source": WEB_SEARCH_SOURCE,
                "web_sources": [
                    {
                        "title": "Zero Trust Architecture",
                        "url": "https://example.com/zero-trust",
                    },
                    {
                        "title": "Zero Trust Architecture",
                        "url": "https://example.com/zero-trust",
                    },
                    {"title": "Missing URL"},
                ],
                "search_query": "unused because page citations exist",
            },
        ),
        Document(
            page_content="query-only supplement",
            metadata={
                "source": WEB_SEARCH_SOURCE,
                "search_query": "current remote access guidance",
            },
        ),
    ]
    return engine.AnswerResult(
        question="What is the VPN policy?",
        answer="Use an approved device and MFA.",
        stop_reason=stop_reason,
        sources=[
            "- Local corpus: VPN Access Policy",
            "- Web search: Zero Trust Architecture — https://example.com/zero-trust",
        ],
        retries=1,
        tracked_llm_calls=4,
        web_search_count=1,
        web_result_grading_count=2,
        web_search_enabled=True,
        web_fallback_policy="conservative",
        raw_state={"documents": documents},
        run_id="run-ask-1",
        node_path=["retrieve", "grade_documents", "websearch", "generate"],
        node_timings_ms=[
            {"node": "retrieve", "duration_ms": 1.25},
            {"node": "generate", "duration_ms": 2.5},
        ],
        total_duration_ms=3.75,
        question_sha256="a" * 64,
        input_redacted=False,
    )


def _patch_successful_preflight(monkeypatch) -> None:
    monkeypatch.setattr(main, "run_startup_preflight", lambda: None)


def test_ask_success_builds_deduplicated_citations_and_records_trace(monkeypatch):
    _patch_successful_preflight(monkeypatch)
    result = _answer_result()
    calls = []

    def fake_answer_question(question, options):
        calls.append((question, options))
        return result

    monkeypatch.setattr(engine, "answer_question", fake_answer_question)
    application = create_app()

    with TestClient(application) as client:
        response = client.post(
            "/api/ask",
            json={
                "question": "  What is the VPN policy?  ",
                "web_search_enabled": True,
                "web_fallback_policy": "conservative",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["run_id"] == "run-ask-1"
        assert payload["question"] == result.question
        assert payload["answer"] == result.answer
        assert payload["status"] == "ok"
        assert payload["caveat"] is None
        assert payload["runtime"] == {
            "provider": "openai",
            "web_search_enabled": True,
            "web_fallback_policy": "conservative",
        }

        assert [citation["kind"] for citation in payload["citations"]] == [
            "local",
            "web",
            "web_query",
        ]
        local, web, query = payload["citations"]
        assert local["title"] == "VPN Access Policy"
        assert local["source"] == "data/acmecorp_internal_docs/vpn_policy.md"
        assert local["document_category"] == "it_security"
        assert local["snippet"] == ("L" * 300)
        assert web["title"] == "Zero Trust Architecture"
        assert web["url"] == "https://example.com/zero-trust"
        assert query["query"] == "current remote access guidance"
        assert len(payload["citations"]) == 3

        assert len(calls) == 1
        question, options = calls[0]
        assert question == "What is the VPN policy?"
        assert isinstance(options, engine.AnswerOptions)
        assert options.web_search_enabled is True
        assert options.web_fallback_policy == "conservative"

        stored = application.state.run_store.get("run-ask-1")
        assert stored is not None
        assert stored["status"] == "ok"
        for forbidden_key in ("answer", "snippet", "page_content", "raw_state", "documents"):
            assert forbidden_key not in stored
        serialized = json.dumps(stored)
        assert "L" * 50 not in serialized


def test_graph_stop_reason_returns_200_with_exact_caveat_and_is_recorded(monkeypatch):
    _patch_successful_preflight(monkeypatch)
    result = _answer_result(stop_reason="budget_exhausted")
    monkeypatch.setattr(engine, "answer_question", lambda _question, _options: result)
    application = create_app()

    with TestClient(application) as client:
        response = client.post("/api/ask", json={"question": "Question"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["stop_reason"] == "budget_exhausted"
        assert payload["status"] == "caveat"
        assert payload["caveat"] == formatting.STOP_REASON_NOTES["budget_exhausted"]
        assert application.state.run_store.get("run-ask-1")["status"] == "caveat"


@pytest.mark.parametrize("question", ["", "   ", "x" * 4001])
def test_invalid_questions_return_422_without_running_or_recording(monkeypatch, question):
    _patch_successful_preflight(monkeypatch)
    calls = []
    monkeypatch.setattr(
        engine,
        "answer_question",
        lambda *_args, **_kwargs: calls.append(True),
    )
    application = create_app()

    with TestClient(application) as client:
        response = client.post("/api/ask", json={"question": question})

        assert response.status_code == 422
        assert calls == []
        assert application.state.run_store.list_summaries() == []


def test_concurrent_ask_returns_409_without_engine_call_or_history(monkeypatch):
    _patch_successful_preflight(monkeypatch)
    calls = []
    monkeypatch.setattr(
        engine,
        "answer_question",
        lambda *_args, **_kwargs: calls.append(True),
    )
    application = create_app()

    with TestClient(application) as client:
        application.state.ask_lock.acquire()
        try:
            response = client.post("/api/ask", json={"question": "Question"})
        finally:
            application.state.ask_lock.release()

        assert response.status_code == 409
        assert response.json() == {
            "error": "run_in_progress",
            "message": "Another question is currently being processed.",
        }
        assert calls == []
        assert application.state.run_store.list_summaries() == []
