"""The single lazy chat-model factory shared by all six LCEL chains."""

from __future__ import annotations

import importlib
import os
from functools import cache
from typing import Any

from langchain_openai import ChatOpenAI

from graph import config
from graph.chains.model_policy import PROVIDER_TOGETHER, ModelTarget, get_model_policy
from graph.chains.model_tasks import ModelTask

_CHAIN_FACTORIES = (
    ("graph.chains.generation", "get_generation_chain"),
    ("graph.chains.retrieval_grader", "get_retrieval_grader"),
    ("graph.chains.question_router", "get_question_router"),
    ("graph.chains.hallucination_grader", "get_hallucination_grader"),
    ("graph.chains.answer_grader", "get_answer_grader"),
    ("graph.chains.query_rewriter", "get_query_rewriter"),
)

TOGETHER_API_BASE_URL = "https://api.together.ai/v1"


class ModelTargetNotOperational(RuntimeError):
    """The policy resolved a provider target without a supported client adapter."""


class ModelCredentialMissing(RuntimeError):
    """A selected provider credential is absent without exposing credential data."""


def _chat_ollama_class() -> Any:
    """Import ChatOllama only after the policy selects local mode."""

    from langchain_ollama import ChatOllama

    return ChatOllama


def _required_credential(name: str) -> str:
    """Return one non-empty provider credential or fail before client construction."""

    value = os.getenv(name)
    if value is None or not value.strip():
        raise ModelCredentialMissing(f"{name} is required by the resolved model target.")
    return value.strip()


@cache
def _get_chat_model_for_target(target: ModelTarget) -> Any:
    """Construct one client per immutable resolved target."""

    settings = target.request_settings_dict()
    timeout = settings["timeout_seconds"]
    temperature = settings["temperature"]

    if target.provider == config.PROVIDER_OLLAMA:
        chat_ollama = _chat_ollama_class()
        return chat_ollama(
            model=target.model,
            temperature=temperature,
            base_url=target.api_base_identity,
            client_kwargs={"timeout": timeout},
        )

    if target.provider == config.PROVIDER_OPENAI:
        return ChatOpenAI(
            model=target.model,
            temperature=temperature,
            timeout=timeout,
        )

    if target.provider == PROVIDER_TOGETHER:
        extra_body: dict[str, Any] = {}
        if settings.get("reasoning_enabled") is False:
            extra_body["reasoning"] = {"enabled": False}
        return ChatOpenAI(
            model=target.model,
            temperature=temperature,
            timeout=timeout,
            api_key=_required_credential("TOGETHER_API_KEY"),
            base_url=TOGETHER_API_BASE_URL,
            extra_body=extra_body,
        )

    raise ModelTargetNotOperational(
        f"Model target {target.provider}/{target.model} is defined by the policy "
        "but no supported client adapter is configured."
    )


def get_chat_model(task: ModelTask) -> Any:
    """Resolve one task through the process policy and return its cached client."""

    policy = get_model_policy()
    return _get_chat_model_for_target(policy.target_for(task))


def clear_model_caches() -> None:
    """Clear policy, target-client, and all six lazy chain caches for tests."""

    get_model_policy.cache_clear()
    _get_chat_model_for_target.cache_clear()
    for module_name, factory_name in _CHAIN_FACTORIES:
        factory = getattr(importlib.import_module(module_name), factory_name)
        factory.cache_clear()
