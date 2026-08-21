"""Bounded password-negation fix layered on Generation lexical V1.1."""

from __future__ import annotations

import re
from typing import Any

from evals.generation_lexical_v1_1 import normalize_for_generation_lexical_v1_1

PROTOCOL_ID = "generation-lexical-v1.2"
SCHEMA_VERSION = 1

_SAFE_PASSWORD_NEGATION_RE = re.compile(
    r"\bpassword is not (?:provided|available|published)\b"
)


def _contains_forbidden(text: str, needle: str) -> bool:
    if needle == "password is":
        text = _SAFE_PASSWORD_NEGATION_RE.sub("", text)
    return needle in text


def score_generation_text(
    value: Any, expected: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Apply V1.1 checks with one bounded negative-password exception."""

    text = normalize_for_generation_lexical_v1_1(value)
    failed: list[str] = []
    for needle in expected.get("contains_all") or []:
        if normalize_for_generation_lexical_v1_1(needle) not in text:
            failed.append("contains_all")
            break
    contains_any = expected.get("contains_any") or []
    if contains_any and not any(
        normalize_for_generation_lexical_v1_1(needle) in text for needle in contains_any
    ):
        failed.append("contains_any")
    for needle in expected.get("not_contains") or []:
        normalized_needle = normalize_for_generation_lexical_v1_1(needle)
        if _contains_forbidden(text, normalized_needle):
            failed.append("not_contains")
            break
    return not failed, failed
