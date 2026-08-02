"""
Tests for the PRIVACY_MODE and FULLY_LOCAL_MODE deployment flags.

Fully mocked -- no API keys, no network, no running local model server.

The distinction these tests exist to pin down:

* PRIVACY_MODE=true is an absolute LOCK. A per-run
  AnswerOptions(web_search_enabled=True) cannot reopen web search or LangSmith
  export.
* WEB_SEARCH_ENABLED=false remains a per-run-overridable DEFAULT (ADR 002).
  The eval harness depends on that, running privacy rows and web-fallback rows
  in the same process.
* FULLY_LOCAL_MODE=false asserts nothing. LLM_PROVIDER=ollama still selects the
  local provider on its own, so an operator who copies the .env.example default
  while setting LLM_PROVIDER keeps a working configuration.

Only one provider configuration is a genuine contradiction:
FULLY_LOCAL_MODE=true with LLM_PROVIDER=openai.
"""

import importlib
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

import graph.engine as engine_module
import graph.graph as graph_module
import main as main_module
from graph.config import (
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    fully_local_mode,
    llm_provider,
    local_mode_enabled,
    privacy_mode,
    web_search_enabled,
)
from graph.consts import RETRIEVE, STOP_REASON_BUDGET_EXHAUSTED, WEBSEARCH
from graph.engine import AnswerOptions, answer_question, seed_state

TRUTHY = ["true", "1", "yes", "on", "TRUE", "  Yes  ", "ON"]
FALSY = ["false", "0", "no", "off", "FALSE", "  No  ", "OFF"]
INVALID = ["maybe", "perhaps", "enabled", "2", "y"]


# ---------------------------------------------------------------------------
# Value parsing
# ---------------------------------------------------------------------------


def test_both_flags_default_to_off_when_unset(monkeypatch):
    monkeypatch.delenv("PRIVACY_MODE", raising=False)
    monkeypatch.delenv("FULLY_LOCAL_MODE", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("WEB_SEARCH_ENABLED", raising=False)

    assert privacy_mode() is False
    assert fully_local_mode() is False
    # Today's behavior, unchanged.
    assert web_search_enabled() is True
    assert llm_provider() == PROVIDER_OPENAI


@pytest.mark.parametrize("flag", ["PRIVACY_MODE", "FULLY_LOCAL_MODE"])
@pytest.mark.parametrize("value", ["", "   "])
def test_empty_value_is_off(monkeypatch, flag, value):
    monkeypatch.setenv(flag, value)

    reader = privacy_mode if flag == "PRIVACY_MODE" else fully_local_mode
    assert reader() is False


@pytest.mark.parametrize("value", TRUTHY)
def test_privacy_mode_truthy_values(monkeypatch, value):
    monkeypatch.setenv("PRIVACY_MODE", value)

    assert privacy_mode() is True
    assert web_search_enabled() is False


@pytest.mark.parametrize("value", FALSY)
def test_privacy_mode_falsy_values_assert_nothing(monkeypatch, value):
    monkeypatch.setenv("PRIVACY_MODE", value)
    monkeypatch.delenv("WEB_SEARCH_ENABLED", raising=False)

    assert privacy_mode() is False
    assert web_search_enabled() is True


@pytest.mark.parametrize("value", TRUTHY)
def test_fully_local_mode_truthy_values(monkeypatch, value):
    monkeypatch.setenv("FULLY_LOCAL_MODE", value)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    assert fully_local_mode() is True
    assert llm_provider() == PROVIDER_OLLAMA


@pytest.mark.parametrize("value", FALSY)
def test_fully_local_mode_falsy_values_assert_nothing(monkeypatch, value):
    monkeypatch.setenv("FULLY_LOCAL_MODE", value)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    assert fully_local_mode() is False
    assert llm_provider() == PROVIDER_OPENAI


@pytest.mark.parametrize("flag", ["PRIVACY_MODE", "FULLY_LOCAL_MODE"])
@pytest.mark.parametrize("value", INVALID)
def test_invalid_flag_value_raises_naming_variable_value_and_options(monkeypatch, flag, value):
    # These flags gate external egress, so a typo must not quietly resolve to
    # either answer.
    monkeypatch.setenv(flag, value)

    reader = privacy_mode if flag == "PRIVACY_MODE" else fully_local_mode
    with pytest.raises(ValueError) as excinfo:
        reader()

    message = str(excinfo.value)
    assert flag in message
    assert value in message
    assert "true" in message and "false" in message


def test_web_search_enabled_keeps_its_lenient_parsing(monkeypatch):
    # ADR 002's published contract: any unrecognized value still means enabled.
    # The new flags are strict; this one deliberately is not.
    monkeypatch.delenv("PRIVACY_MODE", raising=False)
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "anything-else")

    assert web_search_enabled() is True


# ---------------------------------------------------------------------------
# Default-layer truth table (config.web_search_enabled)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("privacy", "web_search", "expected"),
    [
        (None, None, True),  # nothing set -> today's default
        (None, "true", True),
        (None, "false", False),
        ("false", "false", False),  # ratchet: false cannot raise it back up
        ("true", "true", False),  # privacy wins over an explicit truthy legacy value
        ("true", None, False),
    ],
)
def test_default_layer_resolution(monkeypatch, privacy, web_search, expected):
    for name, value in (("PRIVACY_MODE", privacy), ("WEB_SEARCH_ENABLED", web_search)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    assert web_search_enabled() is expected


# ---------------------------------------------------------------------------
# Provider resolution table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fully_local", "provider", "expected"),
    [
        (None, None, PROVIDER_OPENAI),
        (None, "openai", PROVIDER_OPENAI),
        (None, "ollama", PROVIDER_OLLAMA),
        ("false", None, PROVIDER_OPENAI),
        ("false", "openai", PROVIDER_OPENAI),
        # The backward-compatibility case: explicit false asserts nothing, so
        # LLM_PROVIDER stays in control.
        ("false", "ollama", PROVIDER_OLLAMA),
        ("true", None, PROVIDER_OLLAMA),
        ("true", "ollama", PROVIDER_OLLAMA),
    ],
)
def test_provider_resolution_table(monkeypatch, fully_local, provider, expected):
    for name, value in (("FULLY_LOCAL_MODE", fully_local), ("LLM_PROVIDER", provider)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    assert llm_provider() == expected
    assert local_mode_enabled() is (expected == PROVIDER_OLLAMA)


def test_fully_local_true_with_openai_provider_is_the_only_contradiction(monkeypatch):
    monkeypatch.setenv("FULLY_LOCAL_MODE", "true")
    monkeypatch.setenv("LLM_PROVIDER", "openai")

    with pytest.raises(ValueError) as excinfo:
        llm_provider()

    message = str(excinfo.value)
    assert "FULLY_LOCAL_MODE" in message
    assert "LLM_PROVIDER" in message
    assert PROVIDER_OLLAMA in message and PROVIDER_OPENAI in message


def test_fully_local_mode_implies_the_privacy_lock(monkeypatch):
    monkeypatch.setenv("FULLY_LOCAL_MODE", "true")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    assert local_mode_enabled() is True
    # Even with an explicit per-run request for web search.
    assert seed_state("Q", web_search_enabled=True)["web_search_enabled"] is False


def test_invalid_provider_message_is_unchanged(monkeypatch):
    monkeypatch.delenv("FULLY_LOCAL_MODE", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "ollma")

    with pytest.raises(ValueError) as excinfo:
        llm_provider()

    assert "ollma" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Lock vs. default at the seeding layer
# ---------------------------------------------------------------------------


def test_privacy_mode_locks_out_a_per_run_override(monkeypatch):
    monkeypatch.setenv("PRIVACY_MODE", "true")

    assert seed_state("Q", web_search_enabled=True)["web_search_enabled"] is False


def test_web_search_enabled_false_remains_a_per_run_overridable_default(monkeypatch):
    # The contract ADR 002 published and the eval harness depends on: a per-run
    # option still wins over the legacy variable. Promoting it to a lock would
    # break web-fallback rows for any operator who sets it globally.
    monkeypatch.delenv("PRIVACY_MODE", raising=False)
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "false")

    assert seed_state("Q", web_search_enabled=True)["web_search_enabled"] is True
    assert seed_state("Q")["web_search_enabled"] is False


def test_privacy_mode_unset_leaves_per_run_behavior_untouched(monkeypatch):
    monkeypatch.delenv("PRIVACY_MODE", raising=False)
    monkeypatch.delenv("WEB_SEARCH_ENABLED", raising=False)

    assert seed_state("Q", web_search_enabled=True)["web_search_enabled"] is True
    assert seed_state("Q", web_search_enabled=False)["web_search_enabled"] is False
    assert seed_state("Q")["web_search_enabled"] is True


# ---------------------------------------------------------------------------
# End-to-end: the lock holds through a real (mocked) run
# ---------------------------------------------------------------------------


class _RecordingTracingContext:
    """Stands in for langsmith.tracing_context; records how it was used."""

    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _patch_node_seams(monkeypatch, *, docs_relevant=True):
    """Mock every external seam the compiled graph uses; return web-call log."""

    retrieve_module = importlib.import_module("graph.nodes.retrieve")
    grade_module = importlib.import_module("graph.nodes.grade_documents")
    generate_module = importlib.import_module("graph.nodes.generate")
    web_module = importlib.import_module("graph.nodes.web_search")
    rewrite_module = importlib.import_module("graph.nodes.rewrite_query")

    monkeypatch.setattr(
        retrieve_module,
        "get_node_retriever",
        lambda: SimpleNamespace(invoke=lambda q: [Document(page_content="chunk")]),
    )
    monkeypatch.setattr(
        grade_module,
        "get_retrieval_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_relevant=docs_relevant)),
    )
    monkeypatch.setattr(
        generate_module,
        "generate_answer",
        lambda question, documents, retry_feedback="": "ANSWER",
    )

    web_calls = []

    class FakeWebTool:
        def search(self, query, *, max_results, timeout):
            web_calls.append({"query": query, "max_results": max_results, "timeout": timeout})
            return [{"content": "web result"}]

    monkeypatch.setattr(web_module, "get_web_search_tool", lambda: FakeWebTool())
    monkeypatch.setattr(
        web_module,
        "get_retrieval_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_relevant=True)),
    )
    monkeypatch.setattr(
        rewrite_module,
        "get_query_rewriter",
        lambda: SimpleNamespace(invoke=lambda p: "rewritten query"),
    )
    return web_calls


def _patch_router(monkeypatch, datasource):
    calls = {"count": 0}

    class FakeRouter:
        def invoke(self, payload):
            calls["count"] += 1
            return SimpleNamespace(datasource=datasource)

    monkeypatch.setattr(graph_module, "get_question_router", lambda: FakeRouter())
    return calls


def _patch_graders(monkeypatch, grounded, useful):
    monkeypatch.setattr(
        graph_module,
        "get_hallucination_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_grounded=grounded)),
    )
    monkeypatch.setattr(
        graph_module,
        "get_answer_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(answers_question=useful)),
    )


def test_privacy_mode_run_blocks_web_and_tracing_despite_a_per_run_request(monkeypatch):
    # Worst case: the router WOULD choose the web, every document grades
    # irrelevant (normally triggering fallback), the answer is judged not
    # useful (normally triggering a web supplement), and the caller explicitly
    # asks for web search.
    monkeypatch.setenv("PRIVACY_MODE", "true")

    router_calls = _patch_router(monkeypatch, WEBSEARCH)
    _patch_graders(monkeypatch, grounded=True, useful=False)
    web_calls = _patch_node_seams(monkeypatch, docs_relevant=False)

    recorder = _RecordingTracingContext()
    monkeypatch.setattr(engine_module, "tracing_context", recorder)

    result = answer_question("Q", AnswerOptions(web_search_enabled=True))

    assert result.web_search_enabled is False
    assert web_calls == []  # Tavily never invoked
    assert result.web_search_count == 0
    assert router_calls["count"] == 0  # the question never reaches the router LLM
    assert recorder.calls == [{"enabled": False}]  # LangSmith export suppressed


def test_web_search_enabled_false_still_yields_to_a_per_run_request(monkeypatch):
    # The counterpart to the test above: the legacy variable is a default, so
    # the same per-run option DOES reopen web search.
    monkeypatch.delenv("PRIVACY_MODE", raising=False)
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "false")

    _patch_router(monkeypatch, WEBSEARCH)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_node_seams(monkeypatch)

    result = answer_question("Q", AnswerOptions(web_search_enabled=True))

    assert result.web_search_enabled is True
    assert web_calls == [{"query": "Q", "max_results": 3, "timeout": 30.0}]
    assert result.stop_reason == ""


def test_privacy_mode_clean_local_answer_carries_no_caveat(monkeypatch):
    monkeypatch.setenv("PRIVACY_MODE", "true")

    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_node_seams(monkeypatch)

    result = answer_question("Q")

    assert result.web_search_enabled is False
    assert web_calls == []
    assert result.stop_reason == ""


# ---------------------------------------------------------------------------
# Startup validation
# ---------------------------------------------------------------------------


def _endpoint_tripwire(*args, **kwargs):
    raise AssertionError("preflight must fail on configuration before probing an endpoint")


@pytest.mark.parametrize("flag", ["PRIVACY_MODE", "FULLY_LOCAL_MODE"])
@pytest.mark.parametrize("provider", [None, "ollama"])
def test_preflight_reports_an_invalid_flag_value(monkeypatch, flag, provider):
    # Must hold in both OpenAI and local configurations, and must fail before
    # any endpoint probe.
    monkeypatch.setenv(flag, "maybe")
    if provider is None:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
    else:
        monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setattr(main_module, "installed_ollama_models", _endpoint_tripwire)

    with pytest.raises(main_module.PreflightError) as excinfo:
        main_module.run_startup_preflight()

    message = str(excinfo.value)
    assert flag in message
    assert "maybe" in message


def test_preflight_reports_the_provider_contradiction(monkeypatch):
    monkeypatch.setenv("FULLY_LOCAL_MODE", "true")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setattr(main_module, "installed_ollama_models", _endpoint_tripwire)

    with pytest.raises(main_module.PreflightError) as excinfo:
        main_module.run_startup_preflight()

    message = str(excinfo.value)
    assert "FULLY_LOCAL_MODE" in message
    assert "LLM_PROVIDER" in message


def test_preflight_runs_no_local_checks_for_a_valid_openai_configuration(monkeypatch):
    monkeypatch.setenv("PRIVACY_MODE", "true")
    monkeypatch.delenv("FULLY_LOCAL_MODE", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setattr(main_module, "installed_ollama_models", _endpoint_tripwire)
    # Index presence is checked in both modes; stubbed so the assertion below
    # is about the mode flags rather than about this machine's chroma_db/.
    monkeypatch.setattr(main_module, "index_exists", lambda directory: True)

    # Privacy mode alone does not switch provider, so no local checks run.
    assert main_module.run_startup_preflight() is None


def test_validate_only_bypasses_preflight_with_an_invalid_flag(monkeypatch, capsys):
    # evals/run_eval.py returns before importing the graph by design; dataset
    # validation must keep working regardless of mode configuration.
    from evals.run_eval import main as run_eval_main

    monkeypatch.setenv("PRIVACY_MODE", "maybe")
    monkeypatch.setattr(main_module, "run_startup_preflight", _endpoint_tripwire)

    assert run_eval_main(["--validate-only"]) == 0
    assert "Dataset OK" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# CLI entry point (main.main())
# ---------------------------------------------------------------------------
# The startup checks above decide what main() does before its loop; these two
# tests cover the loop itself, the shipped surface both of them end in.


def _cli_tripwire(*_args, **_kwargs):
    raise AssertionError("main() must not reach this after a failed startup check")


def test_cli_prints_the_formatted_answer_with_the_caveat_above_the_sources(monkeypatch, capsys):
    # format_answer is well covered on its own; what is not is how main()
    # applies it. A regression that printed the caveat below the Sources
    # section would make a degraded answer look verified.
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "true")  # keep the privacy banner out of the way
    monkeypatch.setattr(main_module, "run_startup_preflight", lambda: None)

    replies = iter(["  What is the VPN policy?  ", "", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(replies))

    asked = []
    raw_state = {
        "generation": "ANSWER TEXT",
        "stop_reason": STOP_REASON_BUDGET_EXHAUSTED,
        "documents": [Document(page_content="chunk", metadata={"title": "VPN Access Policy"})],
    }

    def fake_answer_question(question):
        asked.append(question)
        return SimpleNamespace(raw_state=raw_state)

    monkeypatch.setattr(main_module, "answer_question", fake_answer_question)

    exit_code = main_module.main()

    out = capsys.readouterr().out
    note = main_module.STOP_REASON_NOTES[STOP_REASON_BUDGET_EXHAUSTED]

    assert exit_code == 0
    assert asked == ["What is the VPN policy?"]  # stripped; blank input and "exit" never run
    assert out.index("ANSWER TEXT") < out.index(note) < out.index(main_module.SOURCES_HEADER)
    assert "- Local corpus: VPN Access Policy" in out
    assert "Bye." in out


def test_cli_stops_on_a_failed_startup_check_without_running_the_graph(monkeypatch, capsys):
    def failing_preflight():
        raise main_module.PreflightError(
            "Local chat model 'test-chat:1b' is not installed at http://localhost:11434."
        )

    monkeypatch.setattr(main_module, "run_startup_preflight", failing_preflight)
    monkeypatch.setattr(main_module, "answer_question", _cli_tripwire)
    monkeypatch.setattr("builtins.input", _cli_tripwire)

    exit_code = main_module.main()

    out = capsys.readouterr().out

    assert exit_code == 1
    assert "Startup check failed" in out
    assert "is not installed" in out  # the actionable message reaches the operator
