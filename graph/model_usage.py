"""Run-scoped, metadata-only chat-model usage collection and aggregation."""

from __future__ import annotations

import math
import threading
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field, replace
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from graph import config
from graph.chains.model_tasks import (
    MODEL_TASK_METADATA_KEY,
    MODEL_TASK_TAG_PREFIX,
    ModelTask,
)

MODEL_USAGE_SCHEMA_VERSION = 1

STATUS_SUCCESS = "success"
STATUS_PROVIDER_ERROR = "provider_error"
STATUS_STRUCTURED_OUTPUT_ERROR = "structured_output_error"

_VALID_STATUSES = {
    STATUS_SUCCESS,
    STATUS_PROVIDER_ERROR,
    STATUS_STRUCTURED_OUTPUT_ERROR,
}
_STRUCTURED_TASKS = {
    ModelTask.QUESTION_ROUTER.value,
    ModelTask.RETRIEVAL_GRADER.value,
    ModelTask.ANSWER_GRADER.value,
    ModelTask.HALLUCINATION_GRADER.value,
}
_LEGACY_TIERS = {
    ModelTask.QUESTION_ROUTER.value: "cheap",
    ModelTask.RETRIEVAL_GRADER.value: "cheap",
    ModelTask.ANSWER_GRADER.value: "cheap",
    ModelTask.GENERATION.value: "primary",
    ModelTask.HALLUCINATION_GRADER.value: "primary",
    ModelTask.QUERY_REWRITER.value: "primary",
}
_TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, Mapping):
            return dumped
    as_dict = getattr(value, "dict", None)
    if callable(as_dict):
        dumped = as_dict()
        if isinstance(dumped, Mapping):
            return dumped
    return {}


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, float) and value >= 0 and value.is_integer():
        return int(value)
    return None


def _first_int(mapping: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = _nonnegative_int(mapping.get(key))
        if value is not None:
            return value
    return None


def _first_known(*values: int | None) -> int | None:
    return next((value for value in values if value is not None), None)


def _usage_candidate(value: Any) -> dict[str, int | None]:
    mapping = _as_mapping(value)
    input_details = _as_mapping(
        mapping.get("input_token_details") or mapping.get("prompt_tokens_details")
    )
    output_details = _as_mapping(
        mapping.get("output_token_details") or mapping.get("completion_tokens_details")
    )
    return {
        "input_tokens": _first_int(mapping, "input_tokens", "prompt_tokens"),
        "cached_input_tokens": _first_known(
            _first_int(mapping, "cached_input_tokens", "cache_read_input_tokens"),
            _first_int(input_details, "cache_read", "cached_tokens"),
        ),
        "cache_write_tokens": _first_known(
            _first_int(mapping, "cache_write_tokens", "cache_creation_input_tokens"),
            _first_int(
                input_details,
                "cache_creation",
                "cache_write",
                "cache_write_tokens",
            ),
        ),
        "output_tokens": _first_int(mapping, "output_tokens", "completion_tokens"),
        "reasoning_tokens": _first_known(
            _first_int(mapping, "reasoning_tokens"),
            _first_int(output_details, "reasoning", "reasoning_tokens"),
        ),
        "total_tokens": _first_int(mapping, "total_tokens"),
    }


def _response_messages(response: Any) -> Iterable[Any]:
    for generation_list in getattr(response, "generations", None) or []:
        for generation in generation_list or []:
            message = getattr(generation, "message", None)
            if message is not None:
                yield message


def normalize_token_usage(response: Any) -> dict[str, int | None]:
    """Normalize standard and provider response token shapes without inventing zeros."""

    candidates: list[Any] = []
    for message in _response_messages(response):
        candidates.append(getattr(message, "usage_metadata", None))
        response_metadata = _as_mapping(getattr(message, "response_metadata", None))
        candidates.extend(
            [
                response_metadata.get("token_usage"),
                response_metadata.get("usage"),
                response_metadata,
            ]
        )

    llm_output = _as_mapping(getattr(response, "llm_output", None))
    candidates.extend([llm_output.get("token_usage"), llm_output.get("usage"), llm_output])

    normalized: dict[str, int | None] = {field_name: None for field_name in _TOKEN_FIELDS}
    for candidate in candidates:
        if candidate is None:
            continue
        extracted = _usage_candidate(candidate)
        for field_name, value in extracted.items():
            if normalized[field_name] is None and value is not None:
                normalized[field_name] = value

    if (
        normalized["total_tokens"] is None
        and normalized["input_tokens"] is not None
        and normalized["output_tokens"] is not None
    ):
        normalized["total_tokens"] = normalized["input_tokens"] + normalized["output_tokens"]

    return normalized


def _reported_model(response: Any) -> str | None:
    llm_output = _as_mapping(getattr(response, "llm_output", None))
    for key in ("model_name", "model"):
        value = llm_output.get(key)
        if isinstance(value, str) and value:
            return value
    for message in _response_messages(response):
        metadata = _as_mapping(getattr(message, "response_metadata", None))
        for key in ("model_name", "model"):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _percentile(samples: list[float], percentile: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 2)


def _sum_known(attempts: Iterable[ModelUsageAttempt], field_name: str) -> int | None:
    values = [getattr(attempt, field_name) for attempt in attempts]
    known = [value for value in values if value is not None]
    return sum(known) if known else None


@dataclass(frozen=True)
class ModelUsageAttempt:
    """Sanitized metadata for one provider request attempt."""

    sequence: int
    task: str
    requested_profile: str
    effective_profile: str
    tier: str
    provider: str
    requested_model: str
    reported_model: str | None
    status: str
    error_type: str | None
    duration_ms: float
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    cache_write_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    request_settings: dict[str, Any] = field(default_factory=dict)

    @property
    def usage_complete(self) -> bool:
        return (
            self.input_tokens is not None
            and self.output_tokens is not None
            and self.total_tokens is not None
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["usage_complete"] = self.usage_complete
        return payload


@dataclass(frozen=True)
class ModelUsageAggregate:
    """Immutable run/eval aggregate retaining metadata-only raw attempts."""

    attempts: tuple[ModelUsageAttempt, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        attempts = tuple(sorted(self.attempts, key=lambda attempt: attempt.sequence))
        durations = [attempt.duration_ms for attempt in attempts]
        status_counts = Counter(attempt.status for attempt in attempts)
        complete = sum(1 for attempt in attempts if attempt.usage_complete)

        grouped: dict[tuple[str, ...], list[ModelUsageAttempt]] = defaultdict(list)
        for attempt in attempts:
            grouped[
                (
                    attempt.requested_profile,
                    attempt.effective_profile,
                    attempt.task,
                    attempt.tier,
                    attempt.provider,
                    attempt.requested_model,
                )
            ].append(attempt)

        groups = []
        for key in sorted(grouped):
            group_attempts = grouped[key]
            group_durations = [attempt.duration_ms for attempt in group_attempts]
            group_statuses = Counter(attempt.status for attempt in group_attempts)
            group_complete = sum(1 for attempt in group_attempts if attempt.usage_complete)
            groups.append(
                {
                    "requested_profile": key[0],
                    "effective_profile": key[1],
                    "task": key[2],
                    "tier": key[3],
                    "provider": key[4],
                    "requested_model": key[5],
                    "reported_models": sorted(
                        {
                            attempt.reported_model
                            for attempt in group_attempts
                            if attempt.reported_model is not None
                        }
                    ),
                    "attempt_count": len(group_attempts),
                    "status_counts": dict(sorted(group_statuses.items())),
                    "usage_complete_attempts": group_complete,
                    "usage_incomplete_attempts": len(group_attempts) - group_complete,
                    "tokens": {
                        field_name: _sum_known(group_attempts, field_name)
                        for field_name in _TOKEN_FIELDS
                    },
                    "duration_ms": {
                        "total": round(sum(group_durations), 2),
                        "p50": _percentile(group_durations, 0.50),
                        "p95": _percentile(group_durations, 0.95),
                        "samples": group_durations,
                    },
                }
            )

        return {
            "schema_version": MODEL_USAGE_SCHEMA_VERSION,
            "attempt_count": len(attempts),
            "status_counts": dict(sorted(status_counts.items())),
            "usage_complete_attempts": complete,
            "usage_incomplete_attempts": len(attempts) - complete,
            "tokens": {
                field_name: _sum_known(attempts, field_name) for field_name in _TOKEN_FIELDS
            },
            "duration_ms": {
                "total": round(sum(durations), 2),
                "p50": _percentile(durations, 0.50),
                "p95": _percentile(durations, 0.95),
                "samples": durations,
            },
            "groups": groups,
            "attempts": [attempt.to_dict() for attempt in attempts],
        }


def _attempt_from_dict(payload: Mapping[str, Any], sequence: int) -> ModelUsageAttempt:
    tokens = {field_name: _nonnegative_int(payload.get(field_name)) for field_name in _TOKEN_FIELDS}
    status = str(payload.get("status") or STATUS_PROVIDER_ERROR)
    if status not in _VALID_STATUSES:
        status = STATUS_PROVIDER_ERROR
    return ModelUsageAttempt(
        sequence=_nonnegative_int(payload.get("sequence")) or sequence,
        task=str(payload.get("task") or "unknown"),
        requested_profile=str(payload.get("requested_profile") or "legacy"),
        effective_profile=str(payload.get("effective_profile") or "legacy"),
        tier=str(payload.get("tier") or "unknown"),
        provider=str(payload.get("provider") or "unknown"),
        requested_model=str(payload.get("requested_model") or "unknown"),
        reported_model=(
            str(payload["reported_model"]) if payload.get("reported_model") is not None else None
        ),
        status=status,
        error_type=(str(payload["error_type"]) if payload.get("error_type") else None),
        duration_ms=max(float(payload.get("duration_ms") or 0.0), 0.0),
        request_settings=dict(_as_mapping(payload.get("request_settings"))),
        **tokens,
    )


def aggregate_attempt_dicts(attempts: Iterable[Mapping[str, Any]]) -> ModelUsageAggregate:
    """Re-aggregate serialized attempts from multiple runs without raw content."""

    return ModelUsageAggregate(
        tuple(_attempt_from_dict(payload, index) for index, payload in enumerate(attempts, 1))
    )


@dataclass
class _PendingAttempt:
    sequence: int
    task: str
    requested_profile: str
    effective_profile: str
    tier: str
    provider: str
    requested_model: str
    request_settings: dict[str, Any]
    started: float
    parent_run_id: UUID | None


class ModelUsageCollector(BaseCallbackHandler):
    """A thread-safe callback collector owned by exactly one graph run."""

    def __init__(self, *, clock: Any = time.perf_counter) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._next_sequence = 1
        self._pending: dict[UUID, _PendingAttempt] = {}
        self._attempts: list[ModelUsageAttempt] = []
        self._chain_parents: dict[UUID, UUID | None] = {}
        self._success_by_chain: dict[UUID, int] = {}

    @staticmethod
    def _task(metadata: Mapping[str, Any], tags: list[str] | None) -> str | None:
        value = metadata.get(MODEL_TASK_METADATA_KEY)
        if value is None:
            for tag in tags or []:
                if tag.startswith(MODEL_TASK_TAG_PREFIX):
                    value = tag.removeprefix(MODEL_TASK_TAG_PREFIX)
                    break
        try:
            return ModelTask(str(value)).value
        except ValueError:
            return None

    @staticmethod
    def _target(
        task: str,
        metadata: Mapping[str, Any],
        invocation_params: Mapping[str, Any],
    ) -> tuple[str, str, str, str, str, dict[str, Any]]:
        local = config.local_mode_enabled()
        provider = "ollama" if local else "openai"
        provider_value = metadata.get("model_provider") or metadata.get("ls_provider")
        if provider_value in {"openai", "together", "ollama"}:
            provider = str(provider_value)

        requested_model = (
            metadata.get("requested_model")
            or metadata.get("ls_model_name")
            or invocation_params.get("model_name")
            or invocation_params.get("model")
            or (config.local_chat_model() if local else config.OPENAI_CHAT_MODEL)
        )
        requested_profile = str(metadata.get("requested_profile") or "legacy")
        effective_profile = str(
            metadata.get("effective_profile") or ("local" if local else "legacy")
        )
        tier = str(metadata.get("model_tier") or ("local" if local else _LEGACY_TIERS[task]))

        temperature = invocation_params.get("temperature")
        if not isinstance(temperature, (int, float)) or isinstance(temperature, bool):
            temperature = 0
        settings = {
            "temperature": temperature,
            "timeout_seconds": config.llm_request_timeout_seconds(),
        }
        policy_settings = metadata.get("model_request_settings")
        if isinstance(policy_settings, Mapping):
            reasoning_enabled = policy_settings.get("reasoning_enabled")
            if isinstance(reasoning_enabled, bool):
                settings["reasoning_enabled"] = reasoning_enabled
        return (
            requested_profile,
            effective_profile,
            tier,
            provider,
            str(requested_model),
            settings,
        )

    def _start(
        self,
        *,
        run_id: UUID,
        metadata: Mapping[str, Any] | None,
        tags: list[str] | None,
        invocation_params: Mapping[str, Any] | None,
        parent_run_id: UUID | None,
    ) -> None:
        safe_metadata = metadata or {}
        task = self._task(safe_metadata, tags)
        if task is None:
            return
        target = self._target(task, safe_metadata, invocation_params or {})
        with self._lock:
            self._pending[run_id] = _PendingAttempt(
                sequence=self._next_sequence,
                task=task,
                requested_profile=target[0],
                effective_profile=target[1],
                tier=target[2],
                provider=target[3],
                requested_model=target[4],
                request_settings=target[5],
                started=self._clock(),
                parent_run_id=parent_run_id,
            )
            self._next_sequence += 1

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        del serialized, messages
        self._start(
            run_id=run_id,
            metadata=metadata,
            tags=tags,
            invocation_params=_as_mapping(kwargs.get("invocation_params")),
            parent_run_id=parent_run_id,
        )

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        del serialized, prompts
        self._start(
            run_id=run_id,
            metadata=metadata,
            tags=tags,
            invocation_params=_as_mapping(kwargs.get("invocation_params")),
            parent_run_id=parent_run_id,
        )

    def _finish(
        self,
        run_id: UUID,
        *,
        status: str,
        error_type: str | None,
        response: Any = None,
    ) -> None:
        with self._lock:
            pending = self._pending.pop(run_id, None)
            if pending is None:
                return
            usage = (
                normalize_token_usage(response)
                if response is not None
                else {field_name: None for field_name in _TOKEN_FIELDS}
            )
            attempt = ModelUsageAttempt(
                sequence=pending.sequence,
                task=pending.task,
                requested_profile=pending.requested_profile,
                effective_profile=pending.effective_profile,
                tier=pending.tier,
                provider=pending.provider,
                requested_model=pending.requested_model,
                reported_model=_reported_model(response) if response is not None else None,
                status=status,
                error_type=error_type,
                duration_ms=round(max(self._clock() - pending.started, 0.0) * 1000.0, 2),
                request_settings=dict(pending.request_settings),
                **usage,
            )
            self._attempts.append(attempt)
            if status == STATUS_SUCCESS:
                index = len(self._attempts) - 1
                chain_run_id = pending.parent_run_id
                while chain_run_id is not None:
                    self._success_by_chain[chain_run_id] = index
                    chain_run_id = self._chain_parents.get(chain_run_id)

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        del parent_run_id, tags, kwargs
        self._finish(run_id, status=STATUS_SUCCESS, error_type=None, response=response)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        del parent_run_id, tags, kwargs
        self._finish(
            run_id,
            status=STATUS_PROVIDER_ERROR,
            error_type=type(error).__name__,
        )

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        del parent_run_id, tags, kwargs
        with self._lock:
            index = self._success_by_chain.pop(run_id, None)
            self._chain_parents.pop(run_id, None)
            if index is None:
                return
            attempt = self._attempts[index]
            if attempt.status != STATUS_SUCCESS or attempt.task not in _STRUCTURED_TASKS:
                return
            self._attempts[index] = replace(
                attempt,
                status=STATUS_STRUCTURED_OUTPUT_ERROR,
                error_type=type(error).__name__,
            )

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        del serialized, inputs, tags, metadata, kwargs
        with self._lock:
            self._chain_parents[run_id] = parent_run_id

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        del outputs, parent_run_id, kwargs
        with self._lock:
            self._chain_parents.pop(run_id, None)
            self._success_by_chain.pop(run_id, None)

    def aggregate(self) -> ModelUsageAggregate:
        with self._lock:
            return ModelUsageAggregate(tuple(self._attempts))
