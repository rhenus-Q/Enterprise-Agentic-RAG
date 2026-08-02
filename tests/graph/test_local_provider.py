"""
Tests for the LLM_PROVIDER local-provider switch.

Four layers, all fully mocked -- no API keys, no network, no running local
model server, no ingestion:

1. graph.config env parsing, including the deliberate fail-fast on an invalid
   LLM_PROVIDER value (silently degrading a typo to "openai" would ship
   questions and retrieved chunks to a third party).
2. The shared chat-model factory, and proof that each of the six chains obtains
   its model through it. An end-to-end local-mode run cannot prove this: the
   router is skipped in privacy mode and the query rewriter is unreachable
   because REWRITE_QUERY only edges into WEBSEARCH, so two modules would stay
   silently unproven.
3. main.run_startup_preflight() -- every failure branch, plus the
   --validate-only bypass.
4. Composition with privacy mode, plus egress tripwires: local mode must never
   construct an OpenAI client, never invoke Tavily, never export a LangSmith
   trace, and never fall back to any of them when the local model fails.

These are WIRING tests. They assert where a model comes from and what is never
contacted -- never what a model outputs. Answer quality is explicitly not a
success criterion of local mode.
"""

import importlib
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document
from langchain_core.runnables import Runnable

import graph.chains._llm as llm_module
import graph.engine as engine_module
import graph.graph as graph_module
import ingestion as ingestion_module
import main as main_module
from graph.config import (
    DEFAULT_LOCAL_CHAT_MODEL,
    DEFAULT_LOCAL_EMBEDDING_MODEL,
    DEFAULT_OLLAMA_BASE_URL,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    llm_provider,
    local_chat_model,
    local_embedding_model,
    local_mode_enabled,
    ollama_base_url,
)
from graph.consts import (
    RETRIEVE,
    STOP_REASON_GENERATION_ERROR,
    STOP_REASON_WEB_SEARCH_DISABLED,
    WEBSEARCH,
)
from graph.engine import AnswerOptions, answer_question

# The six chain factories that must all draw their model from get_chat_model().
CHAIN_FACTORIES = (
    ("graph.chains.generation", "get_generation_chain"),
    ("graph.chains.retrieval_grader", "get_retrieval_grader"),
    ("graph.chains.question_router", "get_question_router"),
    ("graph.chains.hallucination_grader", "get_hallucination_grader"),
    ("graph.chains.answer_grader", "get_answer_grader"),
    ("graph.chains.query_rewriter", "get_query_rewriter"),
)

# Fixed test identifiers, so no assertion depends on a real installed model.
CHAT_MODEL = "test-chat:1b"
EMBED_MODEL = "test-embed:1b"
BASE_URL = "http://localhost:11434"


@pytest.fixture(autouse=True)
def _clear_provider_caches():
    """
    Every factory involved here is @lru_cache'd, so a test that changes
    LLM_PROVIDER would otherwise observe a client built under the previous
    environment. Cleared before and after, so neither this suite nor its
    neighbours inherit a stale client.
    """

    def clear():
        llm_module.get_chat_model.cache_clear()
        ingestion_module.get_retriever.cache_clear()
        for module_name, factory_name in CHAIN_FACTORIES:
            getattr(importlib.import_module(module_name), factory_name).cache_clear()

    clear()
    yield
    clear()


# ---------------------------------------------------------------------------
# graph.config -- env parsing
# ---------------------------------------------------------------------------


def test_provider_defaults_to_openai_when_unset(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    assert llm_provider() == PROVIDER_OPENAI
    assert local_mode_enabled() is False


@pytest.mark.parametrize("value", ["", "   "])
def test_provider_empty_value_defaults_to_openai(monkeypatch, value):
    monkeypatch.setenv("LLM_PROVIDER", value)

    assert llm_provider() == PROVIDER_OPENAI


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("openai", PROVIDER_OPENAI),
        ("OpenAI", PROVIDER_OPENAI),
        ("  openai  ", PROVIDER_OPENAI),
        ("ollama", PROVIDER_OLLAMA),
        ("OLLAMA", PROVIDER_OLLAMA),
        ("  Ollama\t", PROVIDER_OLLAMA),
    ],
)
def test_provider_accepts_known_values_ignoring_case_and_whitespace(monkeypatch, value, expected):
    monkeypatch.setenv("LLM_PROVIDER", value)

    assert llm_provider() == expected
    assert local_mode_enabled() is (expected == PROVIDER_OLLAMA)


@pytest.mark.parametrize("value", ["ollma", "anthropic", "local", "true"])
def test_invalid_provider_raises_instead_of_silently_using_openai(monkeypatch, value):
    # The whole point of local mode is that no data reaches a third party. A
    # typo that quietly fell back to OpenAI would be a silent privacy failure,
    # so this is the one config reader that deliberately fails loudly.
    monkeypatch.setenv("LLM_PROVIDER", value)

    with pytest.raises(ValueError) as excinfo:
        llm_provider()

    message = str(excinfo.value)
    assert value in message  # names the bad value
    assert PROVIDER_OPENAI in message and PROVIDER_OLLAMA in message  # names valid options


def test_invalid_provider_also_raises_through_the_derived_helper(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollma")

    with pytest.raises(ValueError):
        local_mode_enabled()


def test_local_model_and_url_defaults(monkeypatch):
    for name in ("LOCAL_CHAT_MODEL", "LOCAL_EMBEDDING_MODEL", "OLLAMA_BASE_URL"):
        monkeypatch.delenv(name, raising=False)

    assert local_chat_model() == DEFAULT_LOCAL_CHAT_MODEL
    assert local_embedding_model() == DEFAULT_LOCAL_EMBEDDING_MODEL
    assert ollama_base_url() == DEFAULT_OLLAMA_BASE_URL


def test_local_model_and_url_overrides(monkeypatch):
    monkeypatch.setenv("LOCAL_CHAT_MODEL", "  llama3.1:8b  ")
    monkeypatch.setenv("LOCAL_EMBEDDING_MODEL", "nomic-embed-text")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.internal:11434/")

    assert local_chat_model() == "llama3.1:8b"
    assert local_embedding_model() == "nomic-embed-text"
    # Trailing slash normalized so URL joining never produces "//api/tags".
    assert ollama_base_url() == "http://ollama.internal:11434"


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_local_overrides_fall_back_to_defaults(monkeypatch, value):
    monkeypatch.setenv("LOCAL_CHAT_MODEL", value)
    monkeypatch.setenv("LOCAL_EMBEDDING_MODEL", value)
    monkeypatch.setenv("OLLAMA_BASE_URL", value)

    assert local_chat_model() == DEFAULT_LOCAL_CHAT_MODEL
    assert local_embedding_model() == DEFAULT_LOCAL_EMBEDDING_MODEL
    assert ollama_base_url() == DEFAULT_OLLAMA_BASE_URL


# ---------------------------------------------------------------------------
# Shared chat-model factory + six-chain wiring
# ---------------------------------------------------------------------------


class _SentinelChatModel(Runnable):
    """
    Minimal Runnable stand-in for a chat client.

    It has to be a real Runnable because every chain composes it with `|`.
    It never contacts a provider.
    """

    def __init__(self):
        self.structured_output_schemas = []

    def invoke(self, input, config=None, **kwargs):
        return "SENTINEL"

    def with_structured_output(self, schema, **kwargs):
        self.structured_output_schemas.append(schema)
        return self


def _tripwire(name):
    """A stand-in that fails the test if it is ever constructed or invoked."""

    def fail(*args, **kwargs):
        raise AssertionError(f"{name} must never be reached in local mode")

    return fail


@pytest.mark.parametrize(("module_name", "factory_name"), CHAIN_FACTORIES)
def test_every_chain_obtains_its_model_from_the_shared_factory(
    monkeypatch, module_name, factory_name
):
    module = importlib.import_module(module_name)
    sentinel = _SentinelChatModel()
    calls = []

    def fake_get_chat_model():
        calls.append(sentinel)
        return sentinel

    monkeypatch.setattr(module, "get_chat_model", fake_get_chat_model)
    factory = getattr(module, factory_name)
    factory.cache_clear()

    chain = factory()

    assert calls == [sentinel], f"{module_name} did not build its model via get_chat_model()"
    assert chain is not None


def test_no_chain_module_constructs_a_provider_client_directly():
    # A leftover ChatOpenAI(...) in any of these modules would keep sending
    # traffic to OpenAI even with LLM_PROVIDER=ollama.
    offenders = []

    for module_name, _factory_name in CHAIN_FACTORIES:
        module = importlib.import_module(module_name)
        source = Path(module.__file__).read_text(encoding="utf-8")
        if "ChatOpenAI(" in source or "ChatOllama(" in source:
            offenders.append(module_name)

    assert offenders == []


# The probe runs in a fresh interpreter on purpose: in this process the modules
# are already imported, so only a cold import proves what an import does. It is
# also why the check cannot use importlib.reload() -- reloading a chain module
# would leave graph.graph bound to the pre-reload factory object, whose cache no
# fixture clears afterwards.
_IMPORT_PROBE = """
import importlib

for name in ("graph.graph", "graph.nodes", "graph.chains", "graph.engine", "ingestion", "main"):
    importlib.import_module(name)

constructed = [
    module + "." + factory
    for module, factory in %s
    if getattr(importlib.import_module(module), factory).cache_info().currsize
]
print("CONSTRUCTED:" + ",".join(constructed))
"""


def test_importing_the_project_constructs_no_external_client():
    # CLAUDE.md's import rule, made executable: every external client lives
    # behind a lazy @lru_cache factory, so importing any module must leave all
    # of those caches empty. An eagerly built client that does not validate
    # credentials at construction time (Chroma, a local Ollama client) would
    # otherwise pass CI while breaking the invariant the whole mocked test
    # strategy rests on. The API-key variables are stripped from the child
    # environment as well, so CI additionally proves the imports need no keys.
    factories = list(CHAIN_FACTORIES) + [
        ("graph.chains._llm", "get_chat_model"),
        ("ingestion", "get_retriever"),
    ]
    environment = {key: value for key, value in os.environ.items() if not key.endswith("_API_KEY")}

    completed = subprocess.run(
        [sys.executable, "-c", _IMPORT_PROBE % (factories,)],
        cwd=str(ingestion_module.PROJECT_ROOT),
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert completed.returncode == 0, completed.stderr
    reported = [line for line in completed.stdout.splitlines() if line.startswith("CONSTRUCTED:")]
    assert reported == ["CONSTRUCTED:"], completed.stdout


def test_get_chat_model_returns_the_openai_client_by_default(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "45")
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_module, "ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr(llm_module, "_chat_ollama_class", _tripwire("ChatOllama"))
    llm_module.get_chat_model.cache_clear()

    model = llm_module.get_chat_model()

    assert isinstance(model, FakeChatOpenAI)
    assert captured == {"model": "gpt-5-mini", "temperature": 0, "timeout": 45}


def test_get_chat_model_returns_the_local_client_in_local_mode(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LOCAL_CHAT_MODEL", CHAT_MODEL)
    monkeypatch.setenv("OLLAMA_BASE_URL", BASE_URL)
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "90")
    captured = {}

    class FakeChatOllama:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_module, "_chat_ollama_class", lambda: FakeChatOllama)
    monkeypatch.setattr(llm_module, "ChatOpenAI", _tripwire("ChatOpenAI"))
    llm_module.get_chat_model.cache_clear()

    model = llm_module.get_chat_model()

    assert isinstance(model, FakeChatOllama)
    assert captured["model"] == CHAT_MODEL
    assert captured["temperature"] == 0
    assert captured["base_url"] == BASE_URL
    # ChatOllama has no `timeout` field and ignores unknown kwargs, so passing
    # it directly would be silently dropped; it must travel via client_kwargs.
    assert captured["client_kwargs"] == {"timeout": 90}


def test_local_mode_builds_a_real_chat_ollama_without_touching_the_network(monkeypatch):
    chat_ollama_module = pytest.importorskip("langchain_ollama")

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LOCAL_CHAT_MODEL", CHAT_MODEL)
    monkeypatch.setenv("OLLAMA_BASE_URL", BASE_URL)
    monkeypatch.setattr(llm_module, "ChatOpenAI", _tripwire("ChatOpenAI"))
    llm_module.get_chat_model.cache_clear()

    model = llm_module.get_chat_model()

    assert isinstance(model, chat_ollama_module.ChatOllama)
    assert model.model == CHAT_MODEL


# ---------------------------------------------------------------------------
# Embeddings and provider-scoped index
# ---------------------------------------------------------------------------


class _FakeChroma:
    """Records how the vector store was addressed; never touches disk."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        _FakeChroma.last_kwargs = kwargs

    def as_retriever(self, **kwargs):
        return SimpleNamespace(search_kwargs=kwargs.get("search_kwargs"))


def test_local_mode_retriever_uses_local_embeddings_and_the_local_index(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LOCAL_EMBEDDING_MODEL", EMBED_MODEL)
    monkeypatch.setenv("OLLAMA_BASE_URL", BASE_URL)
    monkeypatch.setattr(ingestion_module, "OpenAIEmbeddings", _tripwire("OpenAIEmbeddings"))

    embedding_kwargs = {}

    class FakeOllamaEmbeddings:
        def __init__(self, **kwargs):
            embedding_kwargs.update(kwargs)

    monkeypatch.setattr(ingestion_module, "_ollama_embeddings_class", lambda: FakeOllamaEmbeddings)
    monkeypatch.setattr(ingestion_module, "Chroma", _FakeChroma)
    ingestion_module.get_retriever.cache_clear()

    retriever = ingestion_module.get_retriever()

    assert embedding_kwargs == {"model": EMBED_MODEL, "base_url": BASE_URL}
    assert _FakeChroma.last_kwargs["persist_directory"] == ingestion_module.LOCAL_CHROMA_PATH
    assert _FakeChroma.last_kwargs["collection_name"] == ingestion_module.LOCAL_COLLECTION_NAME
    # Retrieval behavior itself is unchanged.
    assert retriever.search_kwargs == {"k": 3}


def test_openai_mode_keeps_the_original_index_path_and_collection(monkeypatch):
    # Backward compatibility: an index built before local mode existed must
    # stay valid, so neither the path nor the collection name may move.
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    class FakeOpenAIEmbeddings:
        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr(ingestion_module, "OpenAIEmbeddings", FakeOpenAIEmbeddings)
    monkeypatch.setattr(ingestion_module, "_ollama_embeddings_class", _tripwire("OllamaEmbeddings"))
    monkeypatch.setattr(ingestion_module, "Chroma", _FakeChroma)
    ingestion_module.get_retriever.cache_clear()

    ingestion_module.get_retriever()

    assert _FakeChroma.last_kwargs["persist_directory"] == "chroma_db"
    assert _FakeChroma.last_kwargs["collection_name"] == "agentic_rag_docs"


def test_the_two_indexes_never_share_a_location(monkeypatch):
    # Coexistence is what makes switching providers free of re-ingestion, and
    # what stops one ingest from dropping the other provider's collection.
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    openai_config = ingestion_module.active_index_config()

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    local_config = ingestion_module.active_index_config()

    assert openai_config == ("chroma_db", "agentic_rag_docs")
    assert local_config[0] != openai_config[0]
    assert local_config[1] != openai_config[1]


def test_fingerprint_round_trips_and_reads_back_none_when_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LOCAL_EMBEDDING_MODEL", EMBED_MODEL)
    directory = str(tmp_path / "index")

    assert ingestion_module.read_index_fingerprint(directory) is None

    ingestion_module.write_index_fingerprint(directory)

    assert ingestion_module.read_index_fingerprint(directory) == {
        "embedding_provider": PROVIDER_OLLAMA,
        "embedding_model": EMBED_MODEL,
    }


def test_unreadable_fingerprint_reads_back_as_missing(tmp_path):
    directory = tmp_path / "index"
    directory.mkdir()
    (directory / ingestion_module.FINGERPRINT_FILENAME).write_text("not json", encoding="utf-8")

    assert ingestion_module.read_index_fingerprint(str(directory)) is None


# ---------------------------------------------------------------------------
# Startup preflight
# ---------------------------------------------------------------------------


def _local_mode(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LOCAL_CHAT_MODEL", CHAT_MODEL)
    monkeypatch.setenv("LOCAL_EMBEDDING_MODEL", EMBED_MODEL)
    monkeypatch.setenv("OLLAMA_BASE_URL", BASE_URL)


def _patch_endpoint(monkeypatch, models=(CHAT_MODEL, EMBED_MODEL), error=None):
    def fake_installed(base_url, timeout=main_module.PREFLIGHT_TIMEOUT_SECONDS):
        if error is not None:
            raise error
        return list(models)

    monkeypatch.setattr(main_module, "installed_ollama_models", fake_installed)


_UNSET = object()


def _patch_index(monkeypatch, *, exists=True, fingerprint=_UNSET):
    """fingerprint defaults to one matching the active local configuration."""

    if fingerprint is _UNSET:
        fingerprint = {"embedding_provider": PROVIDER_OLLAMA, "embedding_model": EMBED_MODEL}

    monkeypatch.setattr(main_module, "index_exists", lambda directory: exists)
    monkeypatch.setattr(main_module, "read_index_fingerprint", lambda directory: fingerprint)


def test_preflight_rejects_an_invalid_provider_value(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollma")

    with pytest.raises(main_module.PreflightError) as excinfo:
        main_module.run_startup_preflight()

    assert "ollma" in str(excinfo.value)


def test_preflight_reports_an_unreachable_endpoint(monkeypatch):
    _local_mode(monkeypatch)
    _patch_endpoint(monkeypatch, error=OSError("connection refused"))

    with pytest.raises(main_module.PreflightError) as excinfo:
        main_module.run_startup_preflight()

    message = str(excinfo.value)
    assert "not reachable" in message
    assert BASE_URL in message


def test_preflight_names_a_missing_chat_model(monkeypatch):
    _local_mode(monkeypatch)
    _patch_endpoint(monkeypatch, models=(EMBED_MODEL,))
    _patch_index(monkeypatch)

    with pytest.raises(main_module.PreflightError) as excinfo:
        main_module.run_startup_preflight()

    message = str(excinfo.value)
    assert CHAT_MODEL in message
    assert "LOCAL_CHAT_MODEL" in message


def test_preflight_names_a_missing_embedding_model(monkeypatch):
    _local_mode(monkeypatch)
    _patch_endpoint(monkeypatch, models=(CHAT_MODEL,))
    _patch_index(monkeypatch)

    with pytest.raises(main_module.PreflightError) as excinfo:
        main_module.run_startup_preflight()

    message = str(excinfo.value)
    assert EMBED_MODEL in message
    assert "LOCAL_EMBEDDING_MODEL" in message


def test_preflight_requests_ingestion_when_the_local_index_is_missing(monkeypatch):
    _local_mode(monkeypatch)
    _patch_endpoint(monkeypatch)
    _patch_index(monkeypatch, exists=False)

    with pytest.raises(main_module.PreflightError) as excinfo:
        main_module.run_startup_preflight()

    assert "ingestion.py" in str(excinfo.value)


def test_preflight_treats_a_missing_fingerprint_as_a_mismatch_in_local_mode(monkeypatch):
    # A fingerprint-less index is a legacy OpenAI index; it is definitely not
    # the local one, so local mode must ask for ingestion rather than query it.
    _local_mode(monkeypatch)
    _patch_endpoint(monkeypatch)
    _patch_index(monkeypatch, fingerprint=None)

    with pytest.raises(main_module.PreflightError) as excinfo:
        main_module.run_startup_preflight()

    message = str(excinfo.value)
    assert "fingerprint" in message
    assert "ingestion.py" in message


def test_preflight_reports_a_fingerprint_provider_mismatch(monkeypatch):
    _local_mode(monkeypatch)
    _patch_endpoint(monkeypatch)
    _patch_index(
        monkeypatch,
        fingerprint={"embedding_provider": PROVIDER_OPENAI, "embedding_model": EMBED_MODEL},
    )

    with pytest.raises(main_module.PreflightError) as excinfo:
        main_module.run_startup_preflight()

    message = str(excinfo.value)
    assert PROVIDER_OPENAI in message
    assert "ingestion.py" in message


def test_preflight_reports_a_fingerprint_embedding_model_mismatch(monkeypatch):
    # The silent case the fingerprint exists for: two embedding models of the
    # same dimension raise no error, they just retrieve meaningless neighbours.
    _local_mode(monkeypatch)
    _patch_endpoint(monkeypatch)
    _patch_index(
        monkeypatch,
        fingerprint={"embedding_provider": PROVIDER_OLLAMA, "embedding_model": "some-other-embed"},
    )

    with pytest.raises(main_module.PreflightError) as excinfo:
        main_module.run_startup_preflight()

    message = str(excinfo.value)
    assert "some-other-embed" in message
    assert EMBED_MODEL in message
    assert "ingestion.py" in message


def test_preflight_passes_and_reports_the_mode_when_everything_matches(monkeypatch):
    _local_mode(monkeypatch)
    _patch_endpoint(monkeypatch)
    _patch_index(monkeypatch)

    banner = main_module.run_startup_preflight()

    assert banner is not None
    assert CHAT_MODEL in banner
    assert EMBED_MODEL in banner
    assert BASE_URL in banner
    # The boundary must be stated accurately: the endpoint may be remote.
    assert "nothing leaves the machine" not in banner.lower()


def test_preflight_accepts_a_bare_model_name_against_an_installed_latest_tag(monkeypatch):
    _local_mode(monkeypatch)
    monkeypatch.setenv("LOCAL_CHAT_MODEL", "qwen3")
    _patch_endpoint(monkeypatch, models=("qwen3:latest", EMBED_MODEL))
    _patch_index(monkeypatch)

    assert main_module.run_startup_preflight() is not None


def test_openai_mode_preflight_is_a_no_op_even_with_a_legacy_index(monkeypatch):
    # 7.7 case 3: an existing fingerprint-less OpenAI index must keep working
    # with no re-ingestion, and no endpoint must be probed.
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setattr(main_module, "installed_ollama_models", _tripwire("endpoint probe"))
    monkeypatch.setattr(main_module, "index_exists", _tripwire("index_exists"))
    monkeypatch.setattr(main_module, "read_index_fingerprint", _tripwire("read_index_fingerprint"))

    assert main_module.run_startup_preflight() is None


def test_validate_only_never_runs_preflight(monkeypatch, capsys):
    # evals/run_eval.py returns before importing the graph by design, so
    # dataset validation must keep working with no local model server running.
    from evals.run_eval import main as run_eval_main

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")  # nothing listening
    monkeypatch.setattr(main_module, "installed_ollama_models", _tripwire("endpoint probe"))
    monkeypatch.setattr(main_module, "run_startup_preflight", _tripwire("run_startup_preflight"))

    assert run_eval_main(["--validate-only"]) == 0
    assert "Dataset OK" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Privacy composition and egress tripwires
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


def _patch_node_seams(monkeypatch, *, docs_relevant):
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
        lambda question, documents, retry_feedback="": "LOCAL ANSWER",
    )

    web_calls = []

    class FakeWebTool:
        def search(self, query, *, max_results, timeout):
            web_calls.append(
                {"query": query, "max_results": max_results, "timeout": timeout}
            )
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


def _arm_third_party_tripwires(monkeypatch):
    monkeypatch.setattr(llm_module, "ChatOpenAI", _tripwire("ChatOpenAI"))
    monkeypatch.setattr(ingestion_module, "OpenAIEmbeddings", _tripwire("OpenAIEmbeddings"))


def test_local_mode_builds_no_openai_client_for_any_of_the_six_chains(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LOCAL_CHAT_MODEL", CHAT_MODEL)
    monkeypatch.setattr(llm_module, "ChatOpenAI", _tripwire("ChatOpenAI"))

    constructed = []

    class FakeChatOllama(_SentinelChatModel):
        def __init__(self, **kwargs):
            super().__init__()
            constructed.append(kwargs)

    monkeypatch.setattr(llm_module, "_chat_ollama_class", lambda: FakeChatOllama)

    for module_name, factory_name in CHAIN_FACTORIES:
        factory = getattr(importlib.import_module(module_name), factory_name)
        factory.cache_clear()
        factory()

    # One cached local client serves all six chains, and no OpenAI client exists.
    assert len(constructed) == 1
    assert constructed[0]["model"] == CHAT_MODEL


def test_local_mode_run_reaches_no_third_party_service(monkeypatch):
    # Worst case for the guarantee: the router WOULD choose the web, every
    # retrieved document grades irrelevant (normally triggering web fallback),
    # the answer is judged not useful (normally triggering a web supplement),
    # and the caller explicitly asks for web search.
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    _arm_third_party_tripwires(monkeypatch)

    router_calls = _patch_router(monkeypatch, WEBSEARCH)
    _patch_graders(monkeypatch, grounded=True, useful=False)
    web_calls = _patch_node_seams(monkeypatch, docs_relevant=False)

    recorder = _RecordingTracingContext()
    monkeypatch.setattr(engine_module, "tracing_context", recorder)

    result = answer_question("Q", AnswerOptions(web_search_enabled=True))

    # Local mode wins over an explicit per-run option.
    assert result.web_search_enabled is False
    assert web_calls == []  # Tavily never invoked
    assert result.web_search_count == 0
    assert router_calls["count"] == 0  # the question never reaches the router LLM
    assert recorder.calls == [{"enabled": False}]  # LangSmith export suppressed
    assert result.stop_reason == STOP_REASON_WEB_SEARCH_DISABLED


def test_local_mode_ignores_the_web_search_enabled_environment_variable(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "true")
    _arm_third_party_tripwires(monkeypatch)

    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_node_seams(monkeypatch, docs_relevant=True)

    result = answer_question("Q")

    assert result.web_search_enabled is False
    assert web_calls == []
    assert result.stop_reason == ""  # a clean local answer carries no caveat


def test_local_model_failure_never_falls_back_to_a_third_party(monkeypatch):
    # The sharpest test in the suite: a local failure must degrade honestly
    # through the existing stop_reason, never silently reroute to OpenAI or
    # the web.
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    _arm_third_party_tripwires(monkeypatch)

    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_node_seams(monkeypatch, docs_relevant=True)

    generate_module = importlib.import_module("graph.nodes.generate")

    def local_model_is_down(question, documents, retry_feedback=""):
        raise RuntimeError("local endpoint refused the connection")

    monkeypatch.setattr(generate_module, "generate_answer", local_model_is_down)

    result = answer_question("Q")

    assert result.stop_reason == STOP_REASON_GENERATION_ERROR
    assert web_calls == []


def test_openai_mode_still_honors_a_per_run_web_search_option(monkeypatch):
    # Regression guard: the local-mode override must not leak into the default
    # provider, where a per-run option still decides.
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("WEB_SEARCH_ENABLED", raising=False)

    _patch_router(monkeypatch, WEBSEARCH)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_node_seams(monkeypatch, docs_relevant=True)

    result = answer_question("Q", AnswerOptions(web_search_enabled=True))

    assert result.web_search_enabled is True
    assert web_calls == [{"query": "Q", "max_results": 3, "timeout": 30.0}]
    assert result.stop_reason == ""
