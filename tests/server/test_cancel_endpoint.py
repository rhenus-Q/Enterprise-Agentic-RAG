"""Contract tests for POST /api/ask/cancel."""

import threading

from fastapi.testclient import TestClient

import main
from graph import engine
from server.app import create_app

WAIT_TIMEOUT_SECONDS = 5.0


def _client_runs(client: TestClient) -> list[dict]:
    return client.get("/api/runs").json()["runs"]


def _minimal_result() -> engine.AnswerResult:
    return engine.AnswerResult(
        question="a later question",
        answer="an answer",
        stop_reason="",
        sources=[],
        retries=0,
        tracked_llm_calls=1,
        web_search_count=0,
        web_result_grading_count=0,
        web_search_enabled=False,
        web_fallback_policy="conservative",
        raw_state={"documents": []},
        run_id="run-after-cancel",
        node_path=["retrieve", "generate"],
        node_timings_ms=[{"node": "retrieve", "duration_ms": 1.0}],
        total_duration_ms=1.0,
        question_sha256="b" * 64,
        input_redacted=False,
    )


def _patch_successful_preflight(monkeypatch) -> None:
    monkeypatch.setattr(main, "run_startup_preflight", lambda: None)


def test_cancel_with_no_run_in_flight_reports_an_idle_server(monkeypatch):
    _patch_successful_preflight(monkeypatch)
    application = create_app()

    with TestClient(application) as client:
        response = client.post("/api/ask/cancel")

    assert response.status_code == 200
    assert response.json() == {"cancelled": False, "idle": True}


def test_cancel_reports_when_the_run_has_not_finished_unwinding(monkeypatch):
    _patch_successful_preflight(monkeypatch)
    application = create_app()
    cancel_event = threading.Event()
    seen_timeouts = []

    class BusyLock:
        def acquire(self, timeout):
            seen_timeouts.append(timeout)
            return False

        def release(self):
            raise AssertionError("a lock that was not acquired must not be released")

    with TestClient(application) as client:
        application.state.ask_cancel = cancel_event
        application.state.ask_lock = BusyLock()
        response = client.post("/api/ask/cancel")

    assert response.status_code == 200
    assert response.json() == {"cancelled": True, "idle": False}
    assert cancel_event.is_set()
    assert len(seen_timeouts) == 1


def test_cancel_stops_the_run_and_frees_the_slot_for_the_next_question(monkeypatch):
    """
    The whole point of the endpoint: after a cancel, the next question runs.

    Before cancellation existed, a stopped run kept the single-flight slot for
    its full remaining duration and the next POST /api/ask returned 409.
    """

    _patch_successful_preflight(monkeypatch)
    started = threading.Event()
    seen_options = []

    def fake_answer_question(question, options):
        # Stands in for the graph noticing the event at its next node boundary.
        seen_options.append(options)
        started.set()
        event = options.cancel_event
        if event is None or not event.wait(timeout=WAIT_TIMEOUT_SECONDS):
            return _minimal_result()
        raise engine.RunCancelled("cancelled in test")

    monkeypatch.setattr(engine, "answer_question", fake_answer_question)
    application = create_app()

    with TestClient(application) as ask_client:
        responses = []

        def run_ask() -> None:
            responses.append(ask_client.post("/api/ask", json={"question": "hold the slot"}))

        thread = threading.Thread(target=run_ask)
        thread.start()
        try:
            assert started.wait(timeout=WAIT_TIMEOUT_SECONDS)

            # A second client, so the cancel never shares a connection with the
            # request it is cancelling.
            cancel = TestClient(application).post("/api/ask/cancel")
        finally:
            thread.join(timeout=WAIT_TIMEOUT_SECONDS)

        assert cancel.status_code == 200
        # `idle` is the contract that matters: the slot is free on return.
        assert cancel.json() == {"cancelled": True, "idle": True}

        assert seen_options[0].cancel_event is not None
        assert responses[0].status_code == 499
        assert responses[0].json() == {"error": "run_cancelled"}

        # A cancelled run is abandoned, not recorded.
        assert _client_runs(ask_client) == []

        monkeypatch.setattr(engine, "answer_question", lambda question, options: _minimal_result())
        follow_up = ask_client.post("/api/ask", json={"question": "the next question"})

        assert follow_up.status_code == 200
        assert follow_up.json()["run_id"] == "run-after-cancel"
        assert [run["run_id"] for run in _client_runs(ask_client)] == ["run-after-cancel"]


def test_cancel_clears_the_switch_so_a_later_cancel_finds_nothing(monkeypatch):
    _patch_successful_preflight(monkeypatch)
    monkeypatch.setattr(engine, "answer_question", lambda question, options: _minimal_result())
    application = create_app()

    with TestClient(application) as client:
        assert client.post("/api/ask", json={"question": "a question"}).status_code == 200
        response = client.post("/api/ask/cancel")

    assert response.json() == {"cancelled": False, "idle": True}
