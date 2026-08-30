from __future__ import annotations

from typing import Any

GPT_5_6_SOL_PRICING = {
    "currency": "USD",
    "unit_tokens": 1_000_000,
    "input_per_unit": 4.00,
    "cached_input_per_unit": 0.40,
    "cache_write_per_unit": 5.00,
    "output_per_unit": 20.00,
    "source": "https://developers.openai.com/api/docs/models/gpt-5.6-sol",
    "recorded_on": "2026-08-30",
}


def estimate_gpt_5_6_sol_cost(usage: dict[str, Any]) -> float | None:
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if not isinstance(input_tokens, (int, float)) or not isinstance(output_tokens, (int, float)):
        return None
    details = usage.get("input_tokens_details", {})
    details = details if isinstance(details, dict) else {}
    cached_tokens = details.get("cached_tokens", 0)
    cache_write_tokens = details.get("cache_write_tokens", 0)
    cached_tokens = cached_tokens if isinstance(cached_tokens, (int, float)) else 0
    cache_write_tokens = cache_write_tokens if isinstance(cache_write_tokens, (int, float)) else 0
    regular_input_tokens = max(input_tokens - cached_tokens - cache_write_tokens, 0)
    unit = GPT_5_6_SOL_PRICING["unit_tokens"]
    cost = (
        regular_input_tokens * GPT_5_6_SOL_PRICING["input_per_unit"]
        + cached_tokens * GPT_5_6_SOL_PRICING["cached_input_per_unit"]
        + cache_write_tokens * GPT_5_6_SOL_PRICING["cache_write_per_unit"]
        + output_tokens * GPT_5_6_SOL_PRICING["output_per_unit"]
    ) / unit
    return round(cost, 8)
