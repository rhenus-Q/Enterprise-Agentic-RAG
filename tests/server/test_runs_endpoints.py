"""Run-history storage and endpoint contract tests."""

import json

import pytest
from fastapi.testclient import TestClient

import main
from server.app import create_app
from server.runs import RunStore


def _record(run_id: str, generated_at: str, *, status: str = "ok") -> dict:
    return {
        "run_id": run_id,
        "generated_at": generated_at,
        "question_redacted": f"Question for {run_id}",
        "question_sha256": "a" * 64,
        "input_redacted": False,
        "node_path": ["retrieve", "generate"],
        "total_duration_ms": 12.5,
        "node_timings_ms": [
            {"node": "retrieve", "duration_ms": 4.0},
            {"node": "generate", "duration_ms": 8.5},
        ],
        "stop_reason": "" if status == "ok" else "budget_exhausted",
        "retries": 0,
        "web_search_count": 0,
        "counters": {
            "retries": 0,
            "tracked_llm_calls": 1,
            "web_search_count": 0,
            "web_result_grading_count": 0,
        },
        "web_search_enabled": False,
        "web_fallback_policy": "conservative",
        "sources": ["- Local corpus: VPN Access Policy"],
        "provider": "openai",
        "status": status,
        "answer": "FORBIDDEN-ANSWER-MARKER",
        "snippet": "FORBIDDEN-SNIPPET-MARKER",
        "page_content": "FORBIDDEN-PAGE-CONTENT-MARKER",
        "prompt": "FORBIDDEN-PROMPT-MARKER",
        "raw_state": {"documents": []},
        "secret": "FORBIDDEN-SECRET-MARKER",
    }


@pytest.mark.parametrize("limit", [0, -1])
def test_run_store_rejects_a_limit_that_cannot_hold_a_record(limit):
    # A store retaining nothing would report limit=0 and silently drop every
    # run, which is indistinguishable from "no runs happened".
    with pytest.raises(ValueError):
        RunStore(limit=limit)


def test_run_store_replaces_a_repeated_run_id_without_growing():
    store = RunStore(limit=2)
    store.add(_record("run-1", "2026-01-01T00:00:00+00:00"))
    store.add(_record("run-1", "2026-01-01T00:05:00+00:00", status="caveat"))

    summaries = store.list_summaries()

    assert [item["run_id"] for item in summaries] == ["run-1"]
    assert summaries[0]["generated_at"] == "2026-01-01T00:05:00+00:00"
    assert summaries[0]["status"] == "caveat"


def test_run_store_is_bounded_newest_first_and_evicts_lookup():
    store = RunStore(limit=2)
    store.add(_record("run-1", "2026-01-01T00:00:00+00:00"))
    store.add(_record("run-2", "2026-01-01T00:01:00+00:00"))
    store.add(_record("run-3", "2026-01-01T00:02:00+00:00"))

    assert [item["run_id"] for item in store.list_summaries()] == ["run-3", "run-2"]
    assert store.get("run-1") is None
    assert store.get("run-2") is not None


def test_runs_endpoints_return_summary_and_detail_shapes(monkeypatch):
    monkeypatch.setattr(main, "run_startup_preflight", lambda: None)
    application = create_app()

    with TestClient(application) as client:
        application.state.run_store.add(
            _record("run-old", "2026-01-01T00:00:00+00:00", status="caveat")
        )
        application.state.run_store.add(_record("run-new", "2026-01-01T00:01:00+00:00"))

        list_response = client.get("/api/runs")
        detail_response = client.get("/api/runs/run-new")

    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert [item["run_id"] for item in list_payload["runs"]] == ["run-new", "run-old"]
    assert list_payload["count"] == 2
    assert list_payload["limit"] == 50
    assert set(list_payload["runs"][0]) == {
        "run_id",
        "generated_at",
        "question_redacted",
        "status",
        "stop_reason",
        "total_duration_ms",
        "provider",
        "retries",
        "web_search_count",
    }

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert set(detail) == {
        "run_id",
        "generated_at",
        "question_redacted",
        "status",
        "stop_reason",
        "total_duration_ms",
        "provider",
        "retries",
        "web_search_count",
        "question_sha256",
        "input_redacted",
        "node_path",
        "node_timings_ms",
        "counters",
        "web_search_enabled",
        "web_fallback_policy",
        "sources",
    }
    assert detail["counters"]["tracked_llm_calls"] == 1

    serialized = json.dumps({"list": list_payload, "detail": detail})
    for forbidden in (
        "FORBIDDEN-ANSWER-MARKER",
        "FORBIDDEN-SNIPPET-MARKER",
        "FORBIDDEN-PAGE-CONTENT-MARKER",
        "FORBIDDEN-PROMPT-MARKER",
        "FORBIDDEN-SECRET-MARKER",
        "raw_state",
    ):
        assert forbidden not in serialized


def test_unknown_run_returns_404(monkeypatch):
    monkeypatch.setattr(main, "run_startup_preflight", lambda: None)

    with TestClient(create_app()) as client:
        response = client.get("/api/runs/unknown")

    assert response.status_code == 404
    assert response.json() == {"error": "run_not_found"}
