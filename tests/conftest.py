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


# Environment variables selecting the deployment mode and configuring the
# LLM/embedding provider.
PROVIDER_ENV_VARS = (
    "PRIVACY_MODE",
    "FULLY_LOCAL_MODE",
    "LLM_PROVIDER",
    "LOCAL_CHAT_MODEL",
    "LOCAL_EMBEDDING_MODEL",
    "OLLAMA_BASE_URL",
)


@pytest.fixture(autouse=True)
def isolate_provider_env(monkeypatch):
    """
    Run every test as if no mode or provider configuration existed, so a
    developer's local .env cannot change what the suite asserts.

    load_dotenv() above deliberately loads .env before collection, which means
    an operator who sets PRIVACY_MODE=true or LLM_PROVIDER=ollama to actually
    use those features would otherwise import the setting into the test run.
    That is not hypothetical: local mode forces web_search_enabled=False for
    every run, and twelve tests across test_engine.py,
    test_security_behavior.py, test_observability.py, and
    test_web_search_toggle.py failed exactly this way before this fixture
    existed — while asserting perfectly correct web-enabled behavior. Failures
    that look like regressions but are only ambient configuration leaking in.

    PRIVACY_MODE is the sharper case: it is an absolute lock that a per-run
    AnswerOptions(web_search_enabled=True) cannot override, so it would break
    the same tests even where an explicit per-run option is passed.

    Clearing the variables here makes mode selection opt-in: a test that cares
    sets it explicitly with monkeypatch (see tests/graph/test_mode_flags.py and
    tests/graph/test_local_provider.py, which set or delete them in every test
    and are therefore unaffected either way). It also pins tests/chains/ to the
    real gpt-5-mini those integration tests are written against, rather than
    silently redirecting them to a local endpoint.

    monkeypatch restores the original environment after each test.
    """

    for name in PROVIDER_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
