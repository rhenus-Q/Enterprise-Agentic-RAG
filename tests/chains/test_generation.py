"""Real-model integration tests for the answer-generation LCEL chain.

Every test in this module calls gpt-5-mini, requires OPENAI_API_KEY, and is
gated by requires_openai. Keys-free tests for format_documents() and
generate_answer() live under tests/node/ so the default CI collection runs
them.

The chain expects {"question": str, "documents": List[Document]} and returns a
plain string answer.
"""

from langchain_core.documents import Document

from graph.chains.generation import generation_chain
from tests.conftest import requires_openai

GROUNDING_DOCS = [
    Document(
        page_content=(
            "Retrieval-Augmented Generation (RAG) retrieves relevant documents "
            "from an external knowledge source and passes them to a language "
            "model so it can generate grounded answers."
        )
    ),
]


@requires_openai
def test_generation_chain_returns_nonempty_string():
    """The chain should return a non-empty plain string answer."""

    result = generation_chain.invoke(
        {
            "question": "What is Retrieval-Augmented Generation?",
            "documents": GROUNDING_DOCS,
        }
    )

    assert isinstance(result, str)
    assert result.strip() != ""


@requires_openai
def test_generation_chain_answer_uses_unique_context_fact():
    """The chain should use a unique fact from the provided context."""

    unique_docs = [
        Document(
            page_content=(
                "In this test corpus, Retrieval-Augmented Generation is described "
                "as the Silver Bridge method. The Silver Bridge method retrieves "
                "company-approved documents before generating an answer."
            )
        )
    ]

    result = generation_chain.invoke(
        {
            "question": (
                "According to the documents, what method describes Retrieval-Augmented Generation?"
            ),
            "documents": unique_docs,
        }
    )

    assert isinstance(result, str)
    assert result.strip() != ""

    lowered = result.lower()

    assert "silver bridge" in lowered, (
        f"expected answer to use the unique context fact, got: {result!r}"
    )
