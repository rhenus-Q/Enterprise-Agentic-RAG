"""
_llm.py

The single chat-model factory shared by all six LCEL chains.

Which provider a chain talks to is a process-level deployment mode
(LLM_PROVIDER), never a per-chain or per-run choice: every chain gets its
model from get_chat_model(). Routing all six through one factory also removes
the sixfold duplication of the model name, temperature=0, and the per-request
timeout that existed before.

Import stays side-effect-free in the repo's sense: no client is constructed at
import time, and the local-provider package is imported only when local mode
is actually selected, so an OpenAI deployment never needs langchain-ollama
present to import this module.
"""

from functools import lru_cache
from typing import Any

from langchain_openai import ChatOpenAI

from graph.config import (
    OPENAI_CHAT_MODEL,
    llm_request_timeout_seconds,
    local_chat_model,
    local_mode_enabled,
    ollama_base_url,
)


def _chat_ollama_class() -> Any:
    """
    Import ChatOllama lazily.

    langchain-ollama is only needed when local mode is selected. Importing it
    inside this helper keeps `import graph.chains._llm` (and the whole OpenAI
    path) working where the package is absent, and gives tests one seam to
    patch without installing a provider.
    """

    from langchain_ollama import ChatOllama

    return ChatOllama


@lru_cache(maxsize=1)
def get_chat_model() -> Any:
    """
    Build and cache the chat model for the active provider.

    temperature=0 and the LLM_REQUEST_TIMEOUT_SECONDS budget apply on both
    branches. The timeout reaches Ollama by a different route: ChatOllama has
    no `timeout` field and its model config ignores unknown keyword arguments,
    so a `timeout=` passed directly would be silently dropped. It travels via
    `client_kwargs`, which langchain-ollama forwards to
    `ollama.Client(host=base_url, **client_kwargs)` and on to httpx.

    Cached for the process, matching the deployment-mode semantics of
    LLM_PROVIDER. Tests that change the provider environment must call
    get_chat_model.cache_clear() first or they observe a stale client.
    """

    if local_mode_enabled():
        chat_ollama = _chat_ollama_class()
        return chat_ollama(
            model=local_chat_model(),
            temperature=0,
            base_url=ollama_base_url(),
            client_kwargs={"timeout": llm_request_timeout_seconds()},
        )

    return ChatOpenAI(
        model=OPENAI_CHAT_MODEL,
        temperature=0,
        timeout=llm_request_timeout_seconds(),
    )
