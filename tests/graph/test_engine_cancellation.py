"""Cooperative cancellation in graph/engine.py."""

import threading

import pytest

import graph.graph as graph_runtime
from graph import engine

NODES = ["retrieve", "grade_documents", "generate"]


class _FakeCompiledGraph:
    """
    Stands in for the compiled graph's update stream.

    Yields one chunk per completed node, exactly like LangGraph's
    `stream_mode="updates"`, and records which nodes actually started so a
    test can tell a stop *at* a boundary from a stop that never happened.
    """

    def __init__(self, cancel_event=None, cancel_after=None):
        self.nodes_started: list[str] = []
        self._cancel_event = cancel_event
        self._cancel_after = cancel_after

    def stream(self, state, stream_mode=None):
        for node in NODES:
            self.nodes_started.append(node)
            if self._cancel_event is not None and self._cancel_after == node:
                # The caller cancels while this node's work is already done.
                self._cancel_event.set()
            yield {node: {"generation": f"after {node}"}}


def test_cancel_event_stops_the_run_at_the_next_node_boundary(monkeypatch):
    cancel_event = threading.Event()
    fake = _FakeCompiledGraph(cancel_event=cancel_event, cancel_after="retrieve")
    monkeypatch.setattr(graph_runtime, "app", fake)

    with pytest.raises(engine.RunCancelled):
        engine.answer_question("a question", engine.AnswerOptions(cancel_event=cancel_event))

    # Cooperative, not pre-emptive: the running node finished, the next one
    # never started, and no AnswerResult was produced.
    assert fake.nodes_started == ["retrieve"]


def test_an_unset_cancel_event_leaves_the_run_untouched(monkeypatch):
    fake = _FakeCompiledGraph()
    monkeypatch.setattr(graph_runtime, "app", fake)

    result = engine.answer_question(
        "a question",
        engine.AnswerOptions(cancel_event=threading.Event()),
    )

    assert fake.nodes_started == NODES
    assert result.node_path == NODES


def test_runs_without_a_cancel_event_are_unaffected(monkeypatch):
    """The CLI and eval path: no cancel_event, no behavior change."""

    fake = _FakeCompiledGraph()
    monkeypatch.setattr(graph_runtime, "app", fake)

    result = engine.answer_question("a question")

    assert fake.nodes_started == NODES
    assert result.node_path == NODES
    assert result.answer == "after generate"


def test_default_answer_options_carry_no_cancel_event():
    assert engine.AnswerOptions().cancel_event is None
