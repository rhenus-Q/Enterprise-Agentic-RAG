"""Evidence-backed revision of the frozen Generation V1 lexical scorer.

The historical ``generation-lexical-v1`` implementation remains in
``run_model_optimization_eval.py``. This module only adds normalization for
equivalent forms that produced demonstrated false negatives in the
four-model diagnostic run.
"""

from __future__ import annotations

import re
from typing import Any

from evals.run_eval import normalize_for_contains

PROTOCOL_ID = "generation-lexical-v1.1"
SCHEMA_VERSION = 1

_DURATION_UNIT = r"second|minute|hour|day|week|month|year"
_HYPHENATED_DURATION_RE = re.compile(
    rf"\b(\d+(?:\.\d+)?)\s*-\s*({_DURATION_UNIT})s?\b"
)
_PLAIN_DURATION_RE = re.compile(rf"\b(\d+(?:\.\d+)?)\s+({_DURATION_UNIT})s?\b")


def normalize_for_generation_lexical_v1_1(text: Any) -> str:
    """Normalize only the equivalent forms observed in diagnostic evidence."""

    normalized = normalize_for_contains(str(text))
    normalized = normalized.translate(str.maketrans({"’": "'", "‘": "'"}))
    normalized = re.sub(r"\bdon't\b", "do not", normalized)
    normalized = _HYPHENATED_DURATION_RE.sub(r"\1 \2", normalized)
    return _PLAIN_DURATION_RE.sub(r"\1 \2", normalized)


def score_generation_text(
    value: Any, expected: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Apply the frozen V1 checks after the bounded V1.1 normalization."""

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
        if normalize_for_generation_lexical_v1_1(needle) in text:
            failed.append("not_contains")
            break
    return not failed, failed
