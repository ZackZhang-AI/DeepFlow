"""Versioned model pricing used for transparent cost estimates."""

from __future__ import annotations

import os
from dataclasses import dataclass

PRICING_VERSION = "deepseek-2026-07-24"


@dataclass(frozen=True)
class ModelPrice:
    cache_hit_input_usd_per_million: float
    cache_miss_input_usd_per_million: float
    output_usd_per_million: float


_MODEL_PRICES = {
    "deepseek-v4-flash": ModelPrice(0.0028, 0.14, 0.28),
    "deepseek-v4-pro": ModelPrice(0.003625, 0.435, 0.87),
}


def estimate_cost_rmb(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_prompt_tokens: int = 0,
) -> float:
    price = _MODEL_PRICES.get(model)
    if price is None:
        return 0.0
    cached = max(0, min(prompt_tokens, cached_prompt_tokens))
    uncached = max(0, prompt_tokens - cached)
    usd = (
        cached / 1_000_000 * price.cache_hit_input_usd_per_million
        + uncached / 1_000_000 * price.cache_miss_input_usd_per_million
        + max(0, completion_tokens) / 1_000_000 * price.output_usd_per_million
    )
    usd_to_cny = float(os.getenv("USD_TO_CNY_RATE", "7.2"))
    return round(usd * usd_to_cny, 4)
