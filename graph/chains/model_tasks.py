"""Stable provider-independent identities for the six chat-model tasks."""

from enum import StrEnum
from typing import Any

MODEL_TASK_METADATA_KEY = "model_task"
MODEL_TASK_TAG_PREFIX = "model-task:"


class ModelTask(StrEnum):
    """One stable identity for each kind of chat-model work in the graph."""

    QUESTION_ROUTER = "question_router"
    RETRIEVAL_GRADER = "retrieval_grader"
    ANSWER_GRADER = "answer_grader"
    GENERATION = "generation"
    HALLUCINATION_GRADER = "hallucination_grader"
    QUERY_REWRITER = "query_rewriter"


def bind_model_task(runnable: Any, task: ModelTask) -> Any:
    """Attach inherited task metadata and a searchable tag to an LCEL runnable."""

    return runnable.with_config(
        tags=[f"{MODEL_TASK_TAG_PREFIX}{task.value}"],
        metadata={MODEL_TASK_METADATA_KEY: task.value},
    )
