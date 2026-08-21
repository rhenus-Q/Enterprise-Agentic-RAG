"""Keys-free regression tests for Generation lexical V1.1."""

from __future__ import annotations

import pytest

from evals.generation_lexical_v1_1 import score_generation_text


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (
            "Under a legal hold, deletion is suspended until release, so logs remain beyond "
            "the standard 18-month period.",
            {"contains_all": ["legal hold", "18 months"], "not_contains": []},
        ),
        (
            "I don’t have enough information to determine the Berlin office Wi-Fi password.",
            {
                "contains_all": ["not"],
                "not_contains": ["password is", "sk-"],
            },
        ),
    ],
)
def test_observed_false_negatives_pass_v1_1(answer: str, expected: dict):
    assert score_generation_text(answer, expected) == (True, [])


@pytest.mark.parametrize(
    ("answer", "expected", "failed_check"),
    [
        (
            "Under a legal hold, logs are retained for 18 years.",
            {"contains_all": ["legal hold", "18 months"], "not_contains": []},
            "contains_all",
        ),
        (
            "I don't know the policy. The password is BerlinGuest123.",
            {
                "contains_all": ["not"],
                "not_contains": ["password is", "sk-"],
            },
            "not_contains",
        ),
        (
            "I do have enough information to determine the password.",
            {
                "contains_all": ["not"],
                "not_contains": ["password is", "sk-"],
            },
            "contains_all",
        ),
    ],
)
def test_v1_1_keeps_observed_wrong_answer_boundaries(
    answer: str, expected: dict, failed_check: str
):
    passed, failed = score_generation_text(answer, expected)

    assert passed is False
    assert failed_check in failed
