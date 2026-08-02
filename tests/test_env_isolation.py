"""Regression tests for the autouse environment isolation in tests/conftest.py.

The fixture's whole purpose is to remove values the process inherited before the
test started — from the developer's .env via load_dotenv(), or from the shell.
Nothing else in the suite proves that: every other test either sets what it
needs or asserts a default, so a fixture that quietly stopped clearing would
look fine until an operator with a configured .env ran the suite.

The module-scoped fixture below plants exactly that ambient configuration. It is
module-scoped on purpose: higher-scoped fixtures are set up before function-
scoped ones, so the values are in os.environ *before* the autouse fixture runs
for each test — the same ordering as a real inherited environment.

The two name tuples are spelled out here rather than imported from conftest.py,
so dropping a variable from the fixture's list fails this test instead of
silently agreeing with it.
"""

import os

import pytest

from graph import config

PROVIDER_ENV_VARS = (
    "PRIVACY_MODE",
    "FULLY_LOCAL_MODE",
    "LLM_PROVIDER",
    "LOCAL_CHAT_MODEL",
    "LOCAL_EMBEDDING_MODEL",
    "OLLAMA_BASE_URL",
)

RUNTIME_POLICY_ENV_VARS = (
    "WEB_SEARCH_ENABLED",
    "WEB_FALLBACK_POLICY",
    "MAX_LLM_CALLS_PER_RUN",
    "MAX_WEB_SEARCHES_PER_RUN",
    "MAX_WEB_RESULTS_TO_GRADE",
    "LLM_REQUEST_TIMEOUT_SECONDS",
)

# Values a real .env could plausibly hold, each one able to change an assertion.
AMBIENT_ENVIRONMENT = {
    "PRIVACY_MODE": "true",
    "FULLY_LOCAL_MODE": "true",
    "LLM_PROVIDER": "ollama",
    "LOCAL_CHAT_MODEL": "llama3.1",
    "LOCAL_EMBEDDING_MODEL": "nomic-embed-text",
    "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
    "WEB_SEARCH_ENABLED": "false",
    "WEB_FALLBACK_POLICY": "aggressive",
    "MAX_LLM_CALLS_PER_RUN": "1",
    "MAX_WEB_SEARCHES_PER_RUN": "1",
    "MAX_WEB_RESULTS_TO_GRADE": "1",
    "LLM_REQUEST_TIMEOUT_SECONDS": "5",
}


@pytest.fixture(scope="module", autouse=True)
def ambient_environment():
    """Stand in for a developer .env that configured every isolated variable."""

    previous = {name: os.environ.get(name) for name in AMBIENT_ENVIRONMENT}
    os.environ.update(AMBIENT_ENVIRONMENT)

    yield

    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


@pytest.mark.parametrize("name", RUNTIME_POLICY_ENV_VARS)
def test_inherited_runtime_policy_values_are_cleared_before_the_test_body(name):
    assert name in AMBIENT_ENVIRONMENT, f"{name} is not planted by the ambient fixture"
    assert name not in os.environ, (
        f"{name} leaked into the test from the ambient environment; the autouse "
        "fixture in tests/conftest.py must clear it."
    )


@pytest.mark.parametrize("name", PROVIDER_ENV_VARS)
def test_inherited_provider_values_are_cleared_before_the_test_body(name):
    assert name in AMBIENT_ENVIRONMENT, f"{name} is not planted by the ambient fixture"
    assert name not in os.environ, (
        f"{name} leaked into the test from the ambient environment; the autouse "
        "fixture in tests/conftest.py must clear it."
    )


def test_cleared_runtime_policy_values_yield_the_production_defaults():
    # The point of clearing: config reads its own defaults, not the ambient
    # AMBIENT_ENVIRONMENT values (which set every one of these differently).
    assert config.web_search_enabled() is True
    assert config.web_fallback_policy() == config.WEB_FALLBACK_CONSERVATIVE
    assert config.max_llm_calls_per_run() == config.DEFAULT_MAX_LLM_CALLS_PER_RUN
    assert config.max_web_searches_per_run() == config.DEFAULT_MAX_WEB_SEARCHES_PER_RUN
    assert config.max_web_results_to_grade() == config.DEFAULT_MAX_WEB_RESULTS_TO_GRADE
    assert config.llm_request_timeout_seconds() == config.DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS


def test_a_test_can_still_set_a_runtime_policy_variable(monkeypatch):
    # The autouse fixture runs before the test body, so an explicit opt-in wins.
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "aggressive")
    monkeypatch.setenv("MAX_LLM_CALLS_PER_RUN", "3")

    assert config.web_fallback_policy() == "aggressive"
    assert config.max_llm_calls_per_run() == 3


def test_the_next_test_still_starts_from_a_cleared_environment():
    # Runs after the setenv test above: monkeypatch undid it, and the autouse
    # fixture re-cleared the ambient value, so neither carries over.
    assert "WEB_FALLBACK_POLICY" not in os.environ
    assert "MAX_LLM_CALLS_PER_RUN" not in os.environ
