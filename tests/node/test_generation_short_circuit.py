"""Keys-free unit tests for generation's empty-context short circuit.

These tests exercise graph.chains.generation.generate_answer directly. No model
client is constructed because empty or missing documents return the deterministic
insufficient-context answer before the lazy generation chain is requested.
"""

from graph.chains.generation import INSUFFICIENT_CONTEXT_ANSWER, generate_answer


def test_generate_answer_returns_fixed_message_when_no_context():
    """With no documents, generate_answer returns a fixed message without LLM."""

    result = generate_answer(
        "What is the internal SOP for expense approval?",
        [],
    )

    assert result == INSUFFICIENT_CONTEXT_ANSWER


def test_generate_answer_returns_fixed_message_when_documents_none():
    """Falsy documents (None) are treated the same as an empty document list."""

    result = generate_answer(
        "What is the internal SOP for expense approval?",
        None,
    )

    assert result == INSUFFICIENT_CONTEXT_ANSWER
