"""Keys-free tests for metadata-only model usage collection and task wiring."""

import importlib
import json
from uuid import uuid4

import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from langchain_core.runnables import Runnable, RunnableLambda
from langgraph.graph import END, START, StateGraph

from graph.chains.model_tasks import ModelTask
from graph.model_usage import (
    STATUS_PROVIDER_ERROR,
    STATUS_STRUCTURED_OUTPUT_ERROR,
    ModelUsageCollector,
    aggregate_attempt_dicts,
    normalize_token_usage,
)


def _start(
    collector,
    task,
    run_id,
    *,
    parent_run_id=None,
    model="gpt-5-mini",
):
    collector.on_chat_model_start(
        {},
        [[]],
        run_id=run_id,
        parent_run_id=parent_run_id,
        metadata={"model_task": task.value},
        tags=[f"model-task:{task.value}"],
        invocation_params={"model": model, "temperature": 0},
    )


def _response(*, usage_metadata=None, response_metadata=None, llm_output=None):
    message = AIMessage(
        content="ignored output",
        usage_metadata=usage_metadata,
        response_metadata=response_metadata or {},
    )
    return LLMResult(
        generations=[[ChatGeneration(message=message)]],
        llm_output=llm_output or {},
    )


def test_six_stable_task_identities_are_exact():
    assert {task.value for task in ModelTask} == {
        "question_router",
        "retrieval_grader",
        "answer_grader",
        "generation",
        "hallucination_grader",
        "query_rewriter",
    }


def test_normalize_token_usage_prefers_ai_message_standard_shape():
    response = _response(
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 25,
            "total_tokens": 125,
            "input_token_details": {"cache_read": 40, "cache_creation": 5},
            "output_token_details": {"reasoning": 7},
        },
        llm_output={"token_usage": {"prompt_tokens": 999}},
    )

    assert normalize_token_usage(response) == {
        "input_tokens": 100,
        "cached_input_tokens": 40,
        "cache_write_tokens": 5,
        "output_tokens": 25,
        "reasoning_tokens": 7,
        "total_tokens": 125,
    }


def test_normalize_token_usage_supports_legacy_llm_output_and_derives_total():
    response = _response(
        llm_output={
            "token_usage": {
                "prompt_tokens": 11,
                "completion_tokens": 4,
                "prompt_tokens_details": {"cached_tokens": 3},
                "completion_tokens_details": {"reasoning_tokens": 2},
            }
        }
    )

    assert normalize_token_usage(response) == {
        "input_tokens": 11,
        "cached_input_tokens": 3,
        "cache_write_tokens": None,
        "output_tokens": 4,
        "reasoning_tokens": 2,
        "total_tokens": 15,
    }


def test_normalize_token_usage_preserves_reported_zero_detail_counts():
    response = _response(
        usage_metadata={
            "input_tokens": 3,
            "output_tokens": 1,
            "total_tokens": 4,
            "input_token_details": {"cache_read": 0, "cache_creation": 0},
            "output_token_details": {"reasoning": 0},
        }
    )

    usage = normalize_token_usage(response)

    assert usage["cached_input_tokens"] == 0
    assert usage["cache_write_tokens"] == 0
    assert usage["reasoning_tokens"] == 0


def test_collector_records_all_six_attempts_in_run_local_order(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    ticks = iter(float(value) for value in range(20))
    collector = ModelUsageCollector(clock=lambda: next(ticks))

    for task in ModelTask:
        run_id = uuid4()
        _start(collector, task, run_id)
        collector.on_llm_end(
            _response(
                usage_metadata={
                    "input_tokens": 2,
                    "output_tokens": 1,
                    "total_tokens": 3,
                },
                response_metadata={"model_name": "gpt-5-mini-2026-01-01"},
            ),
            run_id=run_id,
        )

    usage = collector.aggregate().to_dict()

    assert [attempt["sequence"] for attempt in usage["attempts"]] == list(range(1, 7))
    assert [attempt["task"] for attempt in usage["attempts"]] == [task.value for task in ModelTask]
    assert usage["attempt_count"] == 6
    assert usage["usage_complete_attempts"] == 6
    assert usage["tokens"]["total_tokens"] == 18
    assert usage["duration_ms"]["samples"] == [1000.0] * 6
    assert {attempt["provider"] for attempt in usage["attempts"]} == {"openai"}
    assert {attempt["requested_model"] for attempt in usage["attempts"]} == {"gpt-5-mini"}
    assert {attempt["reported_model"] for attempt in usage["attempts"]} == {"gpt-5-mini-2026-01-01"}


def test_provider_failure_serializes_exception_type_only(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    collector = ModelUsageCollector()
    run_id = uuid4()
    secret = "sk-SECRET-CALLBACK-MESSAGE"

    _start(collector, ModelTask.GENERATION, run_id)
    collector.on_llm_error(RuntimeError(secret), run_id=run_id)
    usage = collector.aggregate().to_dict()

    attempt = usage["attempts"][0]
    assert attempt["status"] == STATUS_PROVIDER_ERROR
    assert attempt["error_type"] == "RuntimeError"
    assert attempt["input_tokens"] is None
    assert secret not in json.dumps(usage)


def test_structured_parse_failure_reclassifies_completed_provider_attempt(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    collector = ModelUsageCollector()
    outer_chain_id = uuid4()
    model_parent_id = uuid4()
    model_run_id = uuid4()

    collector.on_chain_start({}, {}, run_id=outer_chain_id)
    collector.on_chain_start({}, {}, run_id=model_parent_id, parent_run_id=outer_chain_id)
    _start(
        collector,
        ModelTask.RETRIEVAL_GRADER,
        model_run_id,
        parent_run_id=model_parent_id,
    )
    collector.on_llm_end(
        _response(
            usage_metadata={
                "input_tokens": 5,
                "output_tokens": 1,
                "total_tokens": 6,
            }
        ),
        run_id=model_run_id,
    )
    collector.on_chain_error(ValueError("raw invalid output"), run_id=outer_chain_id)

    attempt = collector.aggregate().to_dict()["attempts"][0]
    assert attempt["status"] == STATUS_STRUCTURED_OUTPUT_ERROR
    assert attempt["error_type"] == "ValueError"
    assert attempt["total_tokens"] == 6
    assert "raw invalid output" not in json.dumps(attempt)


def test_plain_output_parser_failure_is_not_mislabeled_as_structured(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    collector = ModelUsageCollector()
    chain_id = uuid4()
    model_run_id = uuid4()

    collector.on_chain_start({}, {}, run_id=chain_id)
    _start(
        collector,
        ModelTask.QUERY_REWRITER,
        model_run_id,
        parent_run_id=chain_id,
    )
    collector.on_llm_end(_response(), run_id=model_run_id)
    collector.on_chain_error(ValueError("plain parser"), run_id=chain_id)

    assert collector.aggregate().to_dict()["attempts"][0]["status"] == "success"


def test_aggregation_groups_and_retains_failed_usage_incomplete_attempts():
    aggregate = aggregate_attempt_dicts(
        [
            {
                "sequence": 1,
                "task": "generation",
                "requested_profile": "legacy",
                "effective_profile": "legacy",
                "tier": "primary",
                "provider": "openai",
                "requested_model": "gpt-5-mini",
                "reported_model": "gpt-5-mini-2026-01-01",
                "status": "success",
                "error_type": None,
                "duration_ms": 10,
                "input_tokens": 10,
                "output_tokens": 2,
                "total_tokens": 12,
            },
            {
                "sequence": 2,
                "task": "generation",
                "requested_profile": "legacy",
                "effective_profile": "legacy",
                "tier": "primary",
                "provider": "openai",
                "requested_model": "gpt-5-mini",
                "reported_model": None,
                "status": "provider_error",
                "error_type": "TimeoutError",
                "duration_ms": 30,
            },
        ]
    ).to_dict()

    assert aggregate["attempt_count"] == 2
    assert aggregate["usage_complete_attempts"] == 1
    assert aggregate["usage_incomplete_attempts"] == 1
    assert aggregate["status_counts"] == {"provider_error": 1, "success": 1}
    assert aggregate["duration_ms"]["p50"] == 10.0
    assert aggregate["duration_ms"]["p95"] == 30.0
    assert aggregate["groups"][0]["attempt_count"] == 2


def test_collectors_are_run_scoped_and_do_not_share_attempts(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    first = ModelUsageCollector()
    second = ModelUsageCollector()
    run_id = uuid4()

    _start(first, ModelTask.GENERATION, run_id)
    first.on_llm_end(_response(), run_id=run_id)

    assert first.aggregate().to_dict()["attempt_count"] == 1
    assert second.aggregate().to_dict()["attempt_count"] == 0


class _CapturingRunnable(Runnable):
    def __init__(self, sink, schema=None):
        self.sink = sink
        self.schema = schema

    def invoke(self, input, config=None, **kwargs):
        del input, kwargs
        self.sink.append(config)
        if self.schema is None:
            return AIMessage(content="rewritten or generated text")
        field_name = next(iter(self.schema.model_fields))
        value = "retrieve" if field_name == "datasource" else True
        return self.schema(**{field_name: value})

    def with_structured_output(self, schema, **kwargs):
        del kwargs
        return _CapturingRunnable(self.sink, schema=schema)


@pytest.mark.parametrize(
    ("module_name", "factory_name", "task", "payload"),
    [
        (
            "graph.chains.question_router",
            "get_question_router",
            ModelTask.QUESTION_ROUTER,
            {"question": "Q"},
        ),
        (
            "graph.chains.retrieval_grader",
            "get_retrieval_grader",
            ModelTask.RETRIEVAL_GRADER,
            {"question": "Q", "document": "D"},
        ),
        (
            "graph.chains.answer_grader",
            "get_answer_grader",
            ModelTask.ANSWER_GRADER,
            {"question": "Q", "generation": "A"},
        ),
        (
            "graph.chains.generation",
            "get_generation_chain",
            ModelTask.GENERATION,
            {"question": "Q", "documents": [Document(page_content="D")]},
        ),
        (
            "graph.chains.hallucination_grader",
            "get_hallucination_grader",
            ModelTask.HALLUCINATION_GRADER,
            {"documents": [Document(page_content="D")], "generation": "A"},
        ),
        (
            "graph.chains.query_rewriter",
            "get_query_rewriter",
            ModelTask.QUERY_REWRITER,
            {"question": "Q", "previous_answer": "A"},
        ),
    ],
)
def test_each_chain_propagates_static_task_metadata(
    monkeypatch, module_name, factory_name, task, payload
):
    module = importlib.import_module(module_name)
    factory = getattr(module, factory_name)
    captured = []
    monkeypatch.setattr(module, "get_chat_model", lambda: _CapturingRunnable(captured))
    factory.cache_clear()
    try:
        factory().invoke(payload)
    finally:
        factory.cache_clear()

    assert len(captured) == 1
    assert captured[0]["metadata"]["model_task"] == task.value
    assert f"model-task:{task.value}" in captured[0]["tags"]


def test_conditional_edge_inherits_run_callbacks_and_task_metadata():
    captured = []

    def record_config(payload, config):
        del payload
        captured.append(config)
        return "retrieve"

    router = RunnableLambda(record_config).with_config(
        metadata={"model_task": ModelTask.QUESTION_ROUTER.value},
        tags=[f"model-task:{ModelTask.QUESTION_ROUTER.value}"],
    )

    def conditional_edge(state):
        del state
        return router.invoke({})

    builder = StateGraph(dict)
    builder.add_node("start", lambda state: state)
    builder.add_edge(START, "start")
    builder.add_conditional_edges("start", conditional_edge, {"retrieve": END})
    app = builder.compile()
    collector = ModelUsageCollector()

    list(app.stream({}, config={"callbacks": [collector]}, stream_mode="updates"))

    assert len(captured) == 1
    assert captured[0]["metadata"]["model_task"] == ModelTask.QUESTION_ROUTER.value
    assert captured[0]["callbacks"] is not None


@pytest.mark.parametrize("task", list(ModelTask))
def test_task_tags_can_supply_identity_without_metadata(monkeypatch, task):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    collector = ModelUsageCollector()
    run_id = uuid4()
    collector.on_chat_model_start(
        {},
        [[]],
        run_id=run_id,
        tags=[f"model-task:{task.value}"],
    )
    collector.on_llm_end(_response(), run_id=run_id)

    assert collector.aggregate().to_dict()["attempts"][0]["task"] == task.value
