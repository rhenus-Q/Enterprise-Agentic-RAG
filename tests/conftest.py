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

# Environment variables tuning per-run behavior: the web-search default, the
# fallback policy, the three budgets, and the per-request LLM timeout.
RUNTIME_POLICY_ENV_VARS = (
    "WEB_SEARCH_ENABLED",
    "WEB_FALLBACK_POLICY",
    "MAX_LLM_CALLS_PER_RUN",
    "MAX_WEB_SEARCHES_PER_RUN",
    "MAX_WEB_RESULTS_TO_GRADE",
    "LLM_REQUEST_TIMEOUT_SECONDS",
)

ISOLATED_ENV_VARS = PROVIDER_ENV_VARS + RUNTIME_POLICY_ENV_VARS


@pytest.fixture(autouse=True)
def isolate_provider_env(monkeypatch):
    """
    Run every test as if no mode, provider, or runtime-policy configuration
    existed, so a developer's local .env cannot change what the suite asserts.

    Both groups above are cleared: PROVIDER_ENV_VARS (deployment mode and
    LLM/embedding provider) and RUNTIME_POLICY_ENV_VARS (web-search default,
    fallback policy, the three per-run budgets, and the LLM request timeout).

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

    The runtime-policy variables carry the same class of risk, one register
    quieter: a developer running with WEB_FALLBACK_POLICY=aggressive or
    MAX_LLM_CALLS_PER_RUN=1 in .env would see budget and policy tests fail on
    their machine while passing in CI, or the reverse. Per-test delenv() calls
    already guard many of those tests; clearing here makes the guarantee
    structural instead of a convention, and leaves those calls harmlessly
    redundant.

    Clearing the variables here makes every setting opt-in: a test that cares
    sets it explicitly with monkeypatch (see tests/graph/test_mode_flags.py and
    tests/graph/test_local_provider.py, which set or delete them in every test
    and are therefore unaffected either way). Because this fixture runs before
    the test body, an explicit monkeypatch.setenv() inside a test still wins.
    It also pins tests/chains/ to the real gpt-5-mini those integration tests
    are written against, rather than silently redirecting them to a local
    endpoint.

    monkeypatch restores the original environment after each test.
    """

    for name in ISOLATED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
