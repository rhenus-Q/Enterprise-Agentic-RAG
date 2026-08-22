"""Keys-free contract tests for the supported static model profiles."""

from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

import graph.chains._llm as llm_module
from graph import config
from graph.chains.model_policy import (
    DEEPSEEK_V4_FLASH_MODEL,
    GPT_5_6_LUNA_MODEL,
    LOCAL_EFFECTIVE_PROFILE,
    ModelProfile,
    ModelTier,
    get_model_policy,
)
from graph.chains.model_tasks import ModelTask
from graph.engine import AnswerOptions
from server.schemas import AskRequest

CHEAP_TASKS = {
    ModelTask.QUESTION_ROUTER,
    ModelTask.RETRIEVAL_GRADER,
    ModelTask.ANSWER_GRADER,
}

FLASH_LUNA_TASK_MODELS = {
    ModelTask.QUESTION_ROUTER: ("together", DEEPSEEK_V4_FLASH_MODEL),
    ModelTask.RETRIEVAL_GRADER: ("together", DEEPSEEK_V4_FLASH_MODEL),
    ModelTask.ANSWER_GRADER: (config.PROVIDER_OPENAI, GPT_5_6_LUNA_MODEL),
    ModelTask.GENERATION: (config.PROVIDER_OPENAI, GPT_5_6_LUNA_MODEL),
    ModelTask.HALLUCINATION_GRADER: ("together", DEEPSEEK_V4_FLASH_MODEL),
    ModelTask.QUERY_REWRITER: (config.PROVIDER_OPENAI, GPT_5_6_LUNA_MODEL),
}


@pytest.fixture(autouse=True)
def _clear_model_caches():
    llm_module.clear_model_caches()
    yield
    llm_module.clear_model_caches()


def _expected_target(profile: ModelProfile, task: ModelTask) -> tuple[str, str]:
    if profile is ModelProfile.LEGACY:
        return config.PROVIDER_OPENAI, config.OPENAI_CHAT_MODEL
    if profile is ModelProfile.LUNA_ALL:
        return config.PROVIDER_OPENAI, GPT_5_6_LUNA_MODEL
    return FLASH_LUNA_TASK_MODELS[task]


@pytest.mark.parametrize("profile", list(ModelProfile))
@pytest.mark.parametrize("task", list(ModelTask))
def test_every_supported_profile_pins_every_task_target(monkeypatch, profile, task):
    monkeypatch.setenv("MODEL_OPTIMIZATION_PROFILE", profile.value)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("PRIVACY_MODE", "false")

    policy = get_model_policy()
    target = policy.target_for(task)
    expected_tier = ModelTier.CHEAP if task in CHEAP_TASKS else ModelTier.PRIMARY

    assert policy.requested_profile is profile
    assert policy.effective_profile == profile.value
    assert target.tier is expected_tier
    assert (target.provider, target.model) == _expected_target(profile, task)
    expected_settings = {
        "temperature": 0,
        "timeout_seconds": config.DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS,
    }
    if target.provider == "together":
        expected_settings["reasoning_enabled"] = False
    assert target.request_settings_dict() == expected_settings
    assert policy.operational is True


def test_runtime_profile_catalog_contains_only_final_profiles():
    assert [profile.value for profile in ModelProfile] == [
        "legacy",
        "luna_all",
        "flash_luna",
    ]


def test_no_profile_uses_deepseek_as_an_inference_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")

    for profile in ModelProfile:
        monkeypatch.setenv("MODEL_OPTIMIZATION_PROFILE", profile.value)
        get_model_policy.cache_clear()
        for _task, target in get_model_policy().targets:
            assert target.provider != "deepseek"
            if target.model == DEEPSEEK_V4_FLASH_MODEL:
                assert target.provider == "together"


def test_model_target_is_immutable():
    target = get_model_policy().target_for(ModelTask.GENERATION)

    with pytest.raises(FrozenInstanceError):
        target.model = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "legacy"),
        ("", "legacy"),
        (" LEGACY ", "legacy"),
        ("LUNA_ALL", "luna_all"),
        ("FLASH_LUNA", "flash_luna"),
    ],
)
def test_profile_parser_is_strict_but_normalizes_valid_values(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("MODEL_OPTIMIZATION_PROFILE", raising=False)
    else:
        monkeypatch.setenv("MODEL_OPTIMIZATION_PROFILE", raw)

    assert config.model_optimization_profile() == expected


@pytest.mark.parametrize(
    "raw",
    [
        "unknown_profile",
        "invalid_profile",
        "unsupported-profile-SENTINEL",
    ],
)
def test_invalid_profiles_fail_instead_of_guessing(monkeypatch, raw):
    monkeypatch.setenv("MODEL_OPTIMIZATION_PROFILE", raw)

    with pytest.raises(ValueError, match="MODEL_OPTIMIZATION_PROFILE") as excinfo:
        get_model_policy()

    assert raw in str(excinfo.value)


@pytest.mark.parametrize("requested", [ModelProfile.LUNA_ALL, ModelProfile.FLASH_LUNA])
def test_privacy_mode_overrides_nonlegacy_profiles_to_legacy(monkeypatch, requested):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("PRIVACY_MODE", "true")
    monkeypatch.setenv("MODEL_OPTIMIZATION_PROFILE", requested.value)

    policy = get_model_policy()

    assert policy.requested_profile is requested
    assert policy.effective_profile == ModelProfile.LEGACY.value
    assert policy.override_reason == "privacy_mode"
    assert {(target.provider, target.model) for _task, target in policy.targets} == {
        (config.PROVIDER_OPENAI, config.OPENAI_CHAT_MODEL)
    }


@pytest.mark.parametrize("requested", list(ModelProfile))
def test_local_mode_overrides_every_profile_and_resolves_zero_cloud_targets(monkeypatch, requested):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL_OPTIMIZATION_PROFILE", requested.value)
    monkeypatch.setenv("LOCAL_CHAT_MODEL", "local-test-model")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://private-local-endpoint:11434")

    policy = get_model_policy()

    assert policy.requested_profile is requested
    assert policy.effective_profile == LOCAL_EFFECTIVE_PROFILE
    assert policy.override_reason == "local_mode"
    assert {(target.tier, target.provider, target.model) for _task, target in policy.targets} == {
        (ModelTier.LOCAL, config.PROVIDER_OLLAMA, "local-test-model")
    }
    assert "private-local-endpoint" not in str(policy.to_status_dict())


@pytest.mark.parametrize(
    "task",
    [
        ModelTask.QUESTION_ROUTER,
        ModelTask.RETRIEVAL_GRADER,
        ModelTask.HALLUCINATION_GRADER,
    ],
)
def test_flash_luna_together_targets_use_exact_openai_compatible_adapter(monkeypatch, task):
    captured = []
    monkeypatch.setenv("MODEL_OPTIMIZATION_PROFILE", ModelProfile.FLASH_LUNA.value)
    monkeypatch.setenv("TOGETHER_API_KEY", "test-together-key")
    monkeypatch.setattr(
        llm_module, "ChatOpenAI", lambda **kwargs: captured.append(kwargs) or kwargs
    )
    monkeypatch.setattr(llm_module, "_chat_ollama_class", lambda: pytest.fail("Ollama"))

    assert llm_module.get_chat_model(task) == captured[0]
    assert captured == [
        {
            "model": DEEPSEEK_V4_FLASH_MODEL,
            "temperature": 0,
            "timeout": config.DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS,
            "api_key": "test-together-key",
            "base_url": llm_module.TOGETHER_API_BASE_URL,
            "extra_body": {"reasoning": {"enabled": False}},
        }
    ]


@pytest.mark.parametrize(
    ("profile", "expected_model"),
    [
        (ModelProfile.LEGACY, config.OPENAI_CHAT_MODEL),
        (ModelProfile.LUNA_ALL, GPT_5_6_LUNA_MODEL),
        (ModelProfile.FLASH_LUNA, GPT_5_6_LUNA_MODEL),
    ],
)
def test_openai_targets_use_the_official_api_adapter(monkeypatch, profile, expected_model):
    captured = []
    monkeypatch.setenv("MODEL_OPTIMIZATION_PROFILE", profile.value)
    monkeypatch.setattr(
        llm_module, "ChatOpenAI", lambda **kwargs: captured.append(kwargs) or kwargs
    )

    assert llm_module.get_chat_model(ModelTask.GENERATION) == captured[0]
    assert captured == [
        {
            "model": expected_model,
            "temperature": 0,
            "timeout": config.DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS,
        }
    ]


def test_missing_together_key_never_falls_back_to_openai_credentials(monkeypatch):
    monkeypatch.setenv("MODEL_OPTIMIZATION_PROFILE", ModelProfile.FLASH_LUNA.value)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used-for-together")
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    monkeypatch.setattr(llm_module, "ChatOpenAI", lambda **_kwargs: pytest.fail("client"))

    with pytest.raises(llm_module.ModelCredentialMissing, match="TOGETHER_API_KEY"):
        llm_module.get_chat_model(ModelTask.QUESTION_ROUTER)

    assert llm_module._get_chat_model_for_target.cache_info().currsize == 0


def test_clear_helper_resets_policy_target_and_six_chain_caches(monkeypatch):
    monkeypatch.setattr(llm_module, "ChatOpenAI", lambda **kwargs: kwargs)

    llm_module.get_chat_model(ModelTask.QUESTION_ROUTER)
    assert get_model_policy.cache_info().currsize == 1
    assert llm_module._get_chat_model_for_target.cache_info().currsize == 1

    llm_module.clear_model_caches()

    assert get_model_policy.cache_info().currsize == 0
    assert llm_module._get_chat_model_for_target.cache_info().currsize == 0


def test_flash_luna_caches_one_client_per_tier_and_model_target(monkeypatch):
    constructed = []
    monkeypatch.setenv("MODEL_OPTIMIZATION_PROFILE", ModelProfile.FLASH_LUNA.value)
    monkeypatch.setenv("TOGETHER_API_KEY", "test-together-key")
    monkeypatch.setattr(
        llm_module,
        "ChatOpenAI",
        lambda **kwargs: constructed.append(kwargs) or kwargs,
    )

    for task in ModelTask:
        llm_module.get_chat_model(task)

    assert len(constructed) == 4
    assert llm_module._get_chat_model_for_target.cache_info().currsize == 4
    assert {item["model"] for item in constructed} == {
        DEEPSEEK_V4_FLASH_MODEL,
        GPT_5_6_LUNA_MODEL,
    }


def test_uniform_profiles_reuse_one_client_per_existing_tier(monkeypatch):
    constructed = []
    monkeypatch.setenv("MODEL_OPTIMIZATION_PROFILE", ModelProfile.LUNA_ALL.value)
    monkeypatch.setattr(
        llm_module,
        "ChatOpenAI",
        lambda **kwargs: constructed.append(kwargs) or kwargs,
    )

    for task in ModelTask:
        llm_module.get_chat_model(task)

    assert len(constructed) == 2
    assert {item["model"] for item in constructed} == {GPT_5_6_LUNA_MODEL}


def test_cache_reset_prevents_a_stale_client_after_profile_change(monkeypatch):
    constructed = []
    monkeypatch.setattr(
        llm_module,
        "ChatOpenAI",
        lambda **kwargs: constructed.append(kwargs) or kwargs,
    )

    monkeypatch.setenv("MODEL_OPTIMIZATION_PROFILE", ModelProfile.LEGACY.value)
    llm_module.get_chat_model(ModelTask.GENERATION)

    llm_module.clear_model_caches()
    monkeypatch.setenv("MODEL_OPTIMIZATION_PROFILE", ModelProfile.LUNA_ALL.value)
    llm_module.get_chat_model(ModelTask.GENERATION)

    assert [item["model"] for item in constructed] == [
        config.OPENAI_CHAT_MODEL,
        GPT_5_6_LUNA_MODEL,
    ]


def test_profile_selection_is_not_exposed_as_a_per_run_or_http_option():
    assert "model_optimization_profile" not in {field.name for field in fields(AnswerOptions)}
    assert "model_optimization_profile" not in AskRequest.model_fields


def test_model_factory_has_no_forbidden_provider_key_or_endpoint_path():
    sources = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (llm_module.__file__, Path(config.__file__))
    )

    assert "OPENROUTER_API_KEY" not in sources
    assert "DEEPSEEK_API_KEY" not in sources
    assert "openrouter.ai" not in sources.lower()
    assert "api.deepseek.com" not in sources.lower()
