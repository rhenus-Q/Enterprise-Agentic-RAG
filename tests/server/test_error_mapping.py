"""Failure mapping and non-recording tests for the HTTP adapter."""

from fastapi.testclient import TestClient

import ingestion
import main
from graph import config, engine
from server.app import CONFIG_ERROR_MESSAGE, PREFLIGHT_FAILURE_MESSAGE, create_app

FINGERPRINT = {
    "embedding_provider": "openai",
    "embedding_model": "text-embedding-ada-002",
}


def _answer_result() -> engine.AnswerResult:
    return engine.AnswerResult(
        question="Question",
        answer="Answer",
        stop_reason="",
        sources=[],
        raw_state={"documents": []},
        run_id="run-error-test",
        question_sha256="a" * 64,
    )


def _patch_status_index(monkeypatch) -> None:
    monkeypatch.setattr(
        ingestion,
        "active_index_config",
        lambda: ("chroma_db", "agentic_rag_docs"),
    )
    monkeypatch.setattr(ingestion, "active_embedding_fingerprint", lambda: FINGERPRINT)
    monkeypatch.setattr(ingestion, "index_exists", lambda _path: True)
    monkeypatch.setattr(ingestion, "read_index_fingerprint", lambda _path: FINGERPRINT)


def test_preflight_failure_starts_server_but_sanitizes_public_responses(
    monkeypatch,
    capsys,
):
    internal_message = (
        "Local endpoint https://private-host.internal:11434 failed; "
        "index C:\\private\\absolute\\chroma_db is missing."
    )

    def fail_preflight():
        raise main.PreflightError(internal_message)

    monkeypatch.setattr(main, "run_startup_preflight", fail_preflight)
    _patch_status_index(monkeypatch)
    engine_calls = []
    monkeypatch.setattr(
        engine,
        "answer_question",
        lambda *_args, **_kwargs: engine_calls.append(True),
    )
    application = create_app()

    with TestClient(application) as client:
        status_response = client.get("/api/status")
        ask_response = client.post("/api/ask", json={"question": "Question"})
        runs_response = client.get("/api/runs")

    assert status_response.status_code == 200
    assert status_response.json()["preflight"] == {
        "ok": False,
        "message": PREFLIGHT_FAILURE_MESSAGE,
    }
    assert ask_response.status_code == 503
    assert ask_response.json() == {
        "error": "preflight_failed",
        "message": PREFLIGHT_FAILURE_MESSAGE,
    }
    assert internal_message not in status_response.text
    assert internal_message not in ask_response.text
    assert "private-host.internal" not in status_response.text
    assert "private-host.internal" not in ask_response.text
    assert internal_message in capsys.readouterr().out
    assert engine_calls == []
    assert runs_response.json()["count"] == 0


def test_engine_runtime_error_returns_type_only_and_is_not_recorded(monkeypatch):
    secret_message = "secret runtime detail must not escape"
    monkeypatch.setattr(main, "run_startup_preflight", lambda: None)

    def fail_engine(_question, _options):
        raise RuntimeError(secret_message)

    monkeypatch.setattr(engine, "answer_question", fail_engine)
    application = create_app()

    with TestClient(application) as client:
        response = client.post("/api/ask", json={"question": "Question"})
        runs_response = client.get("/api/runs")

    assert response.status_code == 500
    assert response.json() == {
        "error": "internal_error",
        "exception_type": "RuntimeError",
    }
    assert secret_message not in response.text
    assert runs_response.json()["count"] == 0


def test_request_time_config_error_returns_503_and_is_not_recorded(monkeypatch):
    monkeypatch.setattr(main, "run_startup_preflight", lambda: None)
    monkeypatch.setattr(engine, "answer_question", lambda _question, _options: _answer_result())

    raw_message = "Invalid LLM_PROVIDER value 'bogus-SENTINEL'."

    def fail_provider():
        raise ValueError(raw_message)

    monkeypatch.setattr(config, "llm_provider", fail_provider)
    application = create_app()

    with TestClient(application) as client:
        response = client.post("/api/ask", json={"question": "Question"})
        runs_response = client.get("/api/runs")

    assert response.status_code == 503
    # Business endpoints never echo the raw config error: it quotes the
    # offending environment value. /api/status carries the diagnostic instead.
    assert response.json() == {
        "error": "config_error",
        "message": CONFIG_ERROR_MESSAGE,
    }
    assert raw_message not in response.text
    assert "SENTINEL" not in response.text
    assert runs_response.json()["count"] == 0
