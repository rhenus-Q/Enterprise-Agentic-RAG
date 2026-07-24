"""
conftest.py

pytest loads conftest.py before collecting tests.
We load env vars from .env (OPENAI_API_KEY, etc.) here, before any
`from graph.chains.question_router import ...` triggers ChatOpenAI construction.
"""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()


# Skip the whole integration suite (instead of erroring) when no API key is set.
requires_openai = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY is required to call the real gpt-5-mini for these tests",
)


# Environment variables selecting and configuring the LLM/embedding provider.
PROVIDER_ENV_VARS = (
    "LLM_PROVIDER",
    "LOCAL_CHAT_MODEL",
    "LOCAL_EMBEDDING_MODEL",
    "OLLAMA_BASE_URL",
)


@pytest.fixture(autouse=True)
def isolate_provider_env(monkeypatch):
    """
    Run every test as if no provider configuration existed, so a developer's
    local .env cannot change what the suite asserts.

    load_dotenv() above deliberately loads .env before collection, which means
    an operator who sets LLM_PROVIDER=ollama to actually use local mode would
    otherwise import that setting into the test run. That is not hypothetical:
    local mode forces web_search_enabled=False for every run, so twelve tests
    across test_engine.py, test_security_behavior.py, test_observability.py,
    and test_web_search_toggle.py would fail while asserting perfectly correct
    web-enabled behavior — failures that look like regressions but are only
    ambient configuration leaking in.

    Clearing the variables here makes provider selection opt-in: a test that
    cares sets it explicitly with monkeypatch (see
    tests/graph/test_local_provider.py, which sets or deletes them in every
    test and is therefore unaffected either way). It also pins tests/chains/ to
    the real gpt-5-mini those integration tests are written against, rather
    than silently redirecting them to a local endpoint.

    monkeypatch restores the original environment after each test.
    """

    for name in PROVIDER_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
