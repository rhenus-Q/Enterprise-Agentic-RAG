"""Static process-level model policy for the supported cloud profiles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Any

from graph import config
from graph.chains.model_tasks import ModelTask

PROVIDER_TOGETHER = "together"

DEEPSEEK_V4_FLASH_MODEL = "deepseek-ai/DeepSeek-V4-Flash-0731"
GPT_5_6_LUNA_MODEL = "gpt-5.6-luna"

LOCAL_EFFECTIVE_PROFILE = "local"

_OPENAI_API_BASE_IDENTITY = "openai-default"
_TOGETHER_API_BASE_IDENTITY = "together-openai-compatible"


class ModelProfile(StrEnum):
    """The fixed cloud profiles accepted by configuration."""

    LEGACY = config.MODEL_PROFILE_LEGACY
    LUNA_ALL = config.MODEL_PROFILE_LUNA_ALL
    FLASH_LUNA = config.MODEL_PROFILE_FLASH_LUNA


class ModelTier(StrEnum):
    """Static workload roles; a tier is not a provider or model identity."""

    CHEAP = "cheap"
    PRIMARY = "primary"
    LOCAL = "local"


RequestSetting = tuple[str, str | int | float | bool]


@dataclass(frozen=True)
class ModelTarget:
    """One immutable, cache-safe inference target resolved for a task."""

    provider: str
    model: str
    tier: ModelTier
    api_base_identity: str
    request_settings: tuple[RequestSetting, ...]

    def request_settings_dict(self) -> dict[str, str | int | float | bool]:
        """Return a serialization/client-friendly copy of the fixed settings."""

        return dict(self.request_settings)


@dataclass(frozen=True)
class ModelPolicy:
    """Requested/effective profile plus the resolved target for all six tasks."""

    requested_profile: ModelProfile
    effective_profile: str
    targets: tuple[tuple[ModelTask, ModelTarget], ...]
    override_reason: str | None
    operational: bool

    def target_for(self, task: ModelTask) -> ModelTarget:
        """Return the immutable target for one stable model task."""

        normalized = ModelTask(task)
        for candidate, target in self.targets:
            if candidate is normalized:
                return target
        raise ValueError(f"No model target is configured for task {normalized.value!r}.")

    def metadata_for(self, task: ModelTask) -> dict[str, Any]:
        """Metadata inherited by callbacks without prompts, content, or secrets."""

        target = self.target_for(task)
        return {
            "requested_profile": self.requested_profile.value,
            "effective_profile": self.effective_profile,
            "model_tier": target.tier.value,
            "model_provider": target.provider,
            "requested_model": target.model,
            "model_request_settings": target.request_settings_dict(),
        }

    def to_status_dict(self) -> dict[str, Any]:
        """Return the sanitized runtime-status view; endpoint identities stay private."""

        return {
            "requested_profile": self.requested_profile.value,
            "effective_profile": self.effective_profile,
            "override_reason": self.override_reason,
            "operational": self.operational,
            "targets": [
                {
                    "task": task.value,
                    "tier": target.tier.value,
                    "provider": target.provider,
                    "model": target.model,
                    "request_settings": target.request_settings_dict(),
                }
                for task, target in self.targets
            ],
        }


_TASK_TIERS = {
    ModelTask.QUESTION_ROUTER: ModelTier.CHEAP,
    ModelTask.RETRIEVAL_GRADER: ModelTier.CHEAP,
    ModelTask.ANSWER_GRADER: ModelTier.CHEAP,
    ModelTask.GENERATION: ModelTier.PRIMARY,
    ModelTask.HALLUCINATION_GRADER: ModelTier.PRIMARY,
    ModelTask.QUERY_REWRITER: ModelTier.PRIMARY,
}

_PROFILE_TARGETS = {
    ModelProfile.LEGACY: {
        ModelTier.CHEAP: (config.PROVIDER_OPENAI, config.OPENAI_CHAT_MODEL),
        ModelTier.PRIMARY: (config.PROVIDER_OPENAI, config.OPENAI_CHAT_MODEL),
    },
    ModelProfile.LUNA_ALL: {
        ModelTier.CHEAP: (config.PROVIDER_OPENAI, GPT_5_6_LUNA_MODEL),
        ModelTier.PRIMARY: (config.PROVIDER_OPENAI, GPT_5_6_LUNA_MODEL),
    },
}

_PROFILE_TASK_TARGETS = {
    ModelProfile.FLASH_LUNA: {
        ModelTask.QUESTION_ROUTER: (PROVIDER_TOGETHER, DEEPSEEK_V4_FLASH_MODEL),
        ModelTask.RETRIEVAL_GRADER: (PROVIDER_TOGETHER, DEEPSEEK_V4_FLASH_MODEL),
        ModelTask.ANSWER_GRADER: (config.PROVIDER_OPENAI, GPT_5_6_LUNA_MODEL),
        ModelTask.GENERATION: (config.PROVIDER_OPENAI, GPT_5_6_LUNA_MODEL),
        ModelTask.HALLUCINATION_GRADER: (
            PROVIDER_TOGETHER,
            DEEPSEEK_V4_FLASH_MODEL,
        ),
        ModelTask.QUERY_REWRITER: (config.PROVIDER_OPENAI, GPT_5_6_LUNA_MODEL),
    }
}


def _request_settings(provider: str) -> tuple[RequestSetting, ...]:
    settings: tuple[RequestSetting, ...] = (
        ("temperature", 0),
        ("timeout_seconds", config.llm_request_timeout_seconds()),
    )
    if provider == PROVIDER_TOGETHER:
        return (*settings, ("reasoning_enabled", False))
    return settings


def _cloud_target(profile: ModelProfile, task: ModelTask) -> ModelTarget:
    tier = _TASK_TIERS[task]
    task_targets = _PROFILE_TASK_TARGETS.get(profile)
    if task_targets is None:
        provider, model = _PROFILE_TARGETS[profile][tier]
    else:
        provider, model = task_targets[task]
    return ModelTarget(
        provider=provider,
        model=model,
        tier=tier,
        api_base_identity=(
            _TOGETHER_API_BASE_IDENTITY
            if provider == PROVIDER_TOGETHER
            else _OPENAI_API_BASE_IDENTITY
        ),
        request_settings=_request_settings(provider),
    )


def _local_target() -> ModelTarget:
    return ModelTarget(
        provider=config.PROVIDER_OLLAMA,
        model=config.local_chat_model(),
        tier=ModelTier.LOCAL,
        api_base_identity=config.ollama_base_url(),
        request_settings=_request_settings(config.PROVIDER_OLLAMA),
    )


@lru_cache(maxsize=1)
def get_model_policy() -> ModelPolicy:
    """Resolve the static process policy after applying local/privacy locks."""

    requested = ModelProfile(config.model_optimization_profile())
    provider = config.llm_provider()

    if provider == config.PROVIDER_OLLAMA:
        target = _local_target()
        return ModelPolicy(
            requested_profile=requested,
            effective_profile=LOCAL_EFFECTIVE_PROFILE,
            targets=tuple((task, target) for task in ModelTask),
            override_reason="local_mode",
            operational=True,
        )

    if config.privacy_mode() and requested is not ModelProfile.LEGACY:
        effective = ModelProfile.LEGACY
        override_reason = "privacy_mode"
    else:
        effective = requested
        override_reason = None

    targets = tuple((task, _cloud_target(effective, task)) for task in ModelTask)
    return ModelPolicy(
        requested_profile=requested,
        effective_profile=effective.value,
        targets=targets,
        override_reason=override_reason,
        operational=True,
    )
