"""Pure, provider/model-specific model-usage cost calculation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

_MILLION = Decimal("1000000")


def _decimal(value: Any) -> Decimal:
    result = Decimal(str(value))
    if result < 0:
        raise ValueError("Price rates must be non-negative.")
    return result


@dataclass(frozen=True)
class ModelPrice:
    provider: str
    model: str
    uncached_input_per_million: Decimal
    output_per_million: Decimal
    cached_input_per_million: Decimal | None = None
    cache_write_per_million: Decimal | None = None


@dataclass(frozen=True)
class PriceSnapshot:
    snapshot_id: str
    effective_date: date
    currency: str
    source_url: str
    prices: tuple[ModelPrice, ...]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PriceSnapshot:
        snapshot_id = str(payload.get("snapshot_id") or "").strip()
        source_url = str(payload.get("source_url") or "").strip()
        currency = str(payload.get("currency") or "USD").strip().upper()
        if not snapshot_id or not source_url:
            raise ValueError("Price snapshots require snapshot_id and source_url.")
        effective_date = date.fromisoformat(str(payload.get("effective_date") or ""))

        prices = []
        for item in payload.get("prices") or []:
            item = dict(item)
            provider = str(item.get("provider") or "").strip()
            model = str(item.get("model") or "").strip()
            if not provider or not model:
                raise ValueError("Every price requires provider and model.")
            prices.append(
                ModelPrice(
                    provider=provider,
                    model=model,
                    uncached_input_per_million=_decimal(item["uncached_input_per_million"]),
                    output_per_million=_decimal(item["output_per_million"]),
                    cached_input_per_million=(
                        _decimal(item["cached_input_per_million"])
                        if item.get("cached_input_per_million") is not None
                        else None
                    ),
                    cache_write_per_million=(
                        _decimal(item["cache_write_per_million"])
                        if item.get("cache_write_per_million") is not None
                        else None
                    ),
                )
            )
        if not prices:
            raise ValueError("Price snapshots require at least one provider/model price.")
        if len({(price.provider, price.model) for price in prices}) != len(prices):
            raise ValueError("Price snapshot provider/model keys must be unique.")
        return cls(snapshot_id, effective_date, currency, source_url, tuple(prices))


def load_price_snapshot(path: str | Path) -> PriceSnapshot:
    """Load and validate one explicit snapshot; no prices are fetched implicitly."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Price snapshot JSON must be an object.")
    return PriceSnapshot.from_dict(payload)


def estimate_model_usage_cost(
    model_usage: Mapping[str, Any], snapshot: PriceSnapshot | None
) -> dict[str, Any]:
    """Estimate all-attempt cost; incomplete provider usage remains incomplete."""

    if snapshot is None:
        return {
            "status": "unavailable",
            "price_snapshot_id": None,
            "currency": None,
            "estimated_cost": None,
            "complete_attempts": 0,
            "incomplete_attempts": len(model_usage.get("attempts") or []),
        }

    price_by_target = {(price.provider, price.model): price for price in snapshot.prices}
    attempts = list(model_usage.get("attempts") or [])
    total = Decimal("0")
    complete_attempts = 0
    incomplete_attempts = 0

    for attempt in attempts:
        price = price_by_target.get(
            (str(attempt.get("provider")), str(attempt.get("requested_model")))
        )
        input_tokens = attempt.get("input_tokens")
        output_tokens = attempt.get("output_tokens")
        cached_tokens = attempt.get("cached_input_tokens")
        cache_write_tokens = attempt.get("cache_write_tokens")

        if price is None or input_tokens is None or output_tokens is None:
            incomplete_attempts += 1
            continue
        if price.cached_input_per_million is not None and cached_tokens is None:
            incomplete_attempts += 1
            continue
        if price.cache_write_per_million is not None and cache_write_tokens is None:
            incomplete_attempts += 1
            continue

        cached = int(cached_tokens or 0)
        cache_write = int(cache_write_tokens or 0)
        uncached = max(int(input_tokens) - cached, 0)
        attempt_cost = (
            Decimal(uncached) * price.uncached_input_per_million / _MILLION
            + Decimal(int(output_tokens)) * price.output_per_million / _MILLION
        )
        if cached:
            if price.cached_input_per_million is None:
                incomplete_attempts += 1
                continue
            attempt_cost += Decimal(cached) * price.cached_input_per_million / _MILLION
        if cache_write:
            if price.cache_write_per_million is None:
                incomplete_attempts += 1
                continue
            attempt_cost += Decimal(cache_write) * price.cache_write_per_million / _MILLION

        total += attempt_cost
        complete_attempts += 1

    return {
        "status": "complete" if incomplete_attempts == 0 else "incomplete",
        "price_snapshot_id": snapshot.snapshot_id,
        "effective_date": snapshot.effective_date.isoformat(),
        "currency": snapshot.currency,
        "source_url": snapshot.source_url,
        "estimated_cost": (format(total, "f") if complete_attempts or not attempts else None),
        "complete_attempts": complete_attempts,
        "incomplete_attempts": incomplete_attempts,
    }
