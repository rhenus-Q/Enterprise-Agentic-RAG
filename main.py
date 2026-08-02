import json
import sys
import urllib.request

from dotenv import load_dotenv

# Load .env up front.
# Imports are intentionally side-effect-free: every external client
# (ChatOpenAI / OpenAIEmbeddings / Chroma retriever / Tavily) lives behind a
# lazy @lru_cache factory, so importing the engine needs no API keys and no
# network — that is what lets the mocked test suites and CI run without
# secrets. The clients still read env vars (OPENAI_API_KEY, etc.) when first
# constructed at runtime, so .env must be loaded before the graph runs.
load_dotenv()

from graph.config import (
    PROVIDER_OLLAMA,
    fully_local_mode,
    llm_provider,
    local_chat_model,
    local_embedding_model,
    ollama_base_url,
    privacy_mode,
    web_search_enabled,
)
from graph.engine import answer_question

# Presentation lives in graph/formatting.py (shared with the eval harness and
# the engine). Re-exported here so existing imports `from main import ...`
# keep working.
from graph.formatting import (
    BUDGET_EXHAUSTED_NOTE,
    GENERATION_ERROR_NOTE,
    LOCAL_SOURCE_FALLBACK_LABEL,
    MAX_RETRIES_NOT_GROUNDED_NOTE,
    MAX_RETRIES_NOT_USEFUL_NOTE,
    RETRIEVAL_ERROR_NOTE,
    SOURCES_HEADER,
    STOP_REASON_NOTES,
    TOOL_ERROR_NOTE,
    WEB_FALLBACK_DISABLED_NOTE,
    WEB_SEARCH_DISABLED_NOTE,
    WEB_SEARCH_ERROR_NOTE,
    WEB_SOURCE_FALLBACK_LABEL,
    format_answer,
    format_sources,
)
from ingestion import (
    active_embedding_fingerprint,
    active_index_config,
    index_exists,
    read_index_fingerprint,
)

# Seconds to wait for the local endpoint during startup checks. Deliberately
# short: this probes reachability and the installed-model list, never inference.
PREFLIGHT_TIMEOUT_SECONDS = 5


class PreflightError(RuntimeError):
    """
    A startup check failed before the graph ran.

    Preflight lives outside the graph on purpose. ADR 006 requires in-graph
    failures to degrade rather than crash, so a misconfigured endpoint reaching
    a node can only become a generic *_error whose message is discarded (only
    the exception type is logged). Checking first keeps both properties:
    graceful degradation inside the graph, an actionable message outside it.
    """


def installed_ollama_models(base_url, timeout=PREFLIGHT_TIMEOUT_SECONDS):
    """
    Model identifiers installed on the local endpoint (GET /api/tags).

    Its own helper so preflight's "endpoint reachable" and "model installed"
    branches can each be exercised with monkeypatch — no network, no running
    Ollama, no API key.
    """

    url = f"{base_url.rstrip('/')}/api/tags"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    names = []
    for entry in payload.get("models", []):
        if isinstance(entry, dict):
            name = entry.get("model") or entry.get("name")
            if name:
                names.append(str(name))

    return names


def _model_installed(model, installed):
    """
    Exact tag match, plus Ollama's own "a bare name means :latest" rule, so a
    configured `qwen3` matches an installed `qwen3:latest`.
    """

    if model in installed:
        return True

    return ":" not in model and f"{model}:latest" in installed


def run_startup_preflight():
    """
    Validate the mode and provider configuration before the graph runs.

    The mode flags and the provider value are checked in BOTH modes: an
    unparseable PRIVACY_MODE / FULLY_LOCAL_MODE, an invalid LLM_PROVIDER, or a
    FULLY_LOCAL_MODE/LLM_PROVIDER contradiction must fail here with a readable
    message. Without this the same ValueError would surface as a raw traceback
    in the CLI (the banner below reads web_search_enabled()) or, worse, be
    swallowed by the eval harness's per-row handler and reported as a generic
    failed row.

    Index presence is checked in BOTH modes. A missing index is not a loud
    failure at runtime: Chroma happily opens an empty collection, every
    retrieve returns [], and the graph answers from an empty corpus — the
    honest-sounding insufficient-context answer, with nothing anywhere saying
    the knowledge base was never built.

    The remaining checks — endpoint reachable, both models installed, index
    fingerprint matching — apply only in local mode, so an OpenAI deployment
    keeps working with an index that predates fingerprints and needs no
    re-ingestion.

    Returns a banner string in local mode and None in OpenAI mode. Raises
    PreflightError on the first failed check, with a message naming what to fix.
    """

    try:
        privacy_mode()
        fully_local_mode()
        provider = llm_provider()
    except ValueError as exc:
        raise PreflightError(str(exc)) from exc

    if provider != PROVIDER_OLLAMA:
        openai_index_directory, _openai_collection_name = active_index_config()

        if not index_exists(openai_index_directory):
            raise PreflightError(
                f"No knowledge-base index found at {openai_index_directory}. "
                "Build it with `uv run python ingestion.py`."
            )

        # No fingerprint check here on purpose: in OpenAI mode a missing
        # fingerprint means a legacy index, which stays valid.
        return None

    base_url = ollama_base_url()
    chat_model = local_chat_model()
    embedding_model = local_embedding_model()

    try:
        installed = installed_ollama_models(base_url)
    except Exception as exc:
        raise PreflightError(
            f"Local provider endpoint is not reachable at {base_url} "
            f"({type(exc).__name__}). Start the local model server, or point "
            "OLLAMA_BASE_URL at the correct endpoint."
        ) from exc

    # Reported separately so the operator knows which model is missing. A
    # reachable endpoint without the model is a distinct and likely failure.
    for role, model, env_var in (
        ("chat", chat_model, "LOCAL_CHAT_MODEL"),
        ("embedding", embedding_model, "LOCAL_EMBEDDING_MODEL"),
    ):
        if not _model_installed(model, installed):
            raise PreflightError(
                f"Local {role} model '{model}' is not installed at {base_url}. "
                f"Pull it with `ollama pull {model}`, or set {env_var} to an "
                "installed model."
            )

    persist_directory, _collection_name = active_index_config()

    if not index_exists(persist_directory):
        raise PreflightError(
            f"No local knowledge-base index found at {persist_directory}. "
            "Build it with `uv run python ingestion.py` while LLM_PROVIDER=ollama."
        )

    expected = active_embedding_fingerprint()
    stored = read_index_fingerprint(persist_directory)

    if stored is None:
        raise PreflightError(
            f"The index at {persist_directory} has no embedding fingerprint, so it "
            "was not built by local mode. Re-run `uv run python ingestion.py` "
            "while LLM_PROVIDER=ollama."
        )

    if stored.get("embedding_provider") != expected["embedding_provider"]:
        raise PreflightError(
            f"The index at {persist_directory} was built with embedding provider "
            f"'{stored.get('embedding_provider')}', but the active provider is "
            f"'{expected['embedding_provider']}'. Re-run "
            "`uv run python ingestion.py` for the active provider."
        )

    if stored.get("embedding_model") != expected["embedding_model"]:
        raise PreflightError(
            f"The index at {persist_directory} was built with embedding model "
            f"'{stored.get('embedding_model')}', but LOCAL_EMBEDDING_MODEL is "
            f"'{expected['embedding_model']}'. Two embedding models of the same "
            "dimension produce no error and would silently retrieve meaningless "
            "neighbours, so re-run `uv run python ingestion.py` before continuing."
        )

    return (
        "Local provider mode is ON (LLM_PROVIDER=ollama) — EXPERIMENTAL.\n"
        f"  - Chat model:      {chat_model}\n"
        f"  - Embedding model: {embedding_model}\n"
        f"  - Endpoint:        {base_url}\n"
        f"  - Index:           {persist_directory}\n"
        "  - No data is sent to OpenAI, Tavily, or LangSmith, and no failure\n"
        "    path falls back to them. The endpoint above is itself the trust\n"
        "    boundary: it may be this machine or your own private infrastructure.\n"
        "  - Web search is disabled for every run in this mode, and a per-run\n"
        "    option cannot re-enable it.\n"
        "  - Answer quality depends entirely on the model you point this at.\n"
    )


def main():
    print("Agentic RAG Assistant for Enterprise Document Q&A")
    print("Type 'exit' to quit.\n")

    try:
        local_banner = run_startup_preflight()
    except PreflightError as exc:
        print(f"Startup check failed:\n  {exc}")
        return 1

    if local_banner:
        print(local_banner)

    # Privacy mode: questions are never sent to an external web search service
    # (Tavily), and no LangSmith trace is exported. The suppression itself
    # lives in graph/engine.py so that it covers every caller, not just this
    # CLI. Skipped in local mode, whose banner above already states the
    # (stronger) guarantee. Two variables can reach this state, so name the one
    # responsible — PRIVACY_MODE additionally locks out per-run overrides.
    if not local_banner and not web_search_enabled():
        locked = privacy_mode()
        source = "PRIVACY_MODE=true" if locked else "WEB_SEARCH_ENABLED=false"
        lock_note = (
            "  - This is an absolute lock: a per-run option cannot re-enable it.\n"
            if locked
            else ""
        )
        print(
            f"Privacy mode is ON ({source}):\n"
            "  - Web search is disabled; answers come from the local knowledge base only.\n"
            "  - LangSmith tracing is disabled; no trace leaves this machine.\n"
            f"{lock_note}"
            "  Note: questions and retrieved chunks are still sent to OpenAI.\n"
        )

    while True:
        question = input("Enter your question:\n> ").strip()

        if question.lower() in ["exit", "quit", "q"]:
            print("Bye.")
            break

        if not question:
            continue

        # The engine seeds the full GraphState (including the per-run
        # web_search_enabled / web_fallback_policy resolution) and runs the
        # compiled graph.
        result = answer_question(question)

        print("\nAnswer:")
        print(format_answer(result.raw_state))
        print("-" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
