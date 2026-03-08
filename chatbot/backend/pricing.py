"""Model pricing and cost calculation from model_pricing.json."""

import json
from pathlib import Path

PRICING_PATH = Path(__file__).parent / "model_pricing.json"
_pricing_data: dict | None = None


def _load_pricing() -> dict:
    global _pricing_data
    if _pricing_data is None:
        with open(PRICING_PATH, encoding="utf-8") as f:
            _pricing_data = json.load(f)
    return _pricing_data


def get_pricing_for_model(model_id: str) -> dict | None:
    """Return pricing dict for the given model id (e.g. claude-sonnet-4-20250514), or None if unknown."""
    data = _load_pricing()
    model_key = data.get("model_id_to_key", {}).get(model_id)
    if not model_key:
        return None
    return data.get("models", {}).get(model_key)


def get_premium_per_token() -> float:
    """Premium in USD per token for other costs."""
    return float(_load_pricing().get("premium_per_token", 0))


def compute_cost(
    input_tokens: int,
    output_tokens: int,
    cache_tokens: int,
    model_id: str,
    use_reasoning: bool = False,
) -> float:
    """
    Compute cost in USD from token counts and model pricing.
    Uses cache_read price for cache_tokens. Adds premium_per_token to every token.
    When use_reasoning is True, output tokens are charged at extended_thinking_usd_per_mtok
    (Claude extended thinking rate); otherwise at output_usd_per_mtok.
    """
    pricing = get_pricing_for_model(model_id)
    premium = get_premium_per_token()
    total_tokens = input_tokens + output_tokens + cache_tokens
    premium_cost = total_tokens * premium

    if not pricing:
        return round(premium_cost, 6)

    input_cost = input_tokens * (pricing["input_usd_per_mtok"] / 1_000_000)
    output_rate = (
        pricing.get("extended_thinking_usd_per_mtok") or pricing["output_usd_per_mtok"]
    ) if use_reasoning else pricing["output_usd_per_mtok"]
    output_cost = output_tokens * (output_rate / 1_000_000)
    cache_cost = cache_tokens * (pricing["cache_read_usd_per_mtok"] / 1_000_000)
    return round(input_cost + output_cost + cache_cost + premium_cost, 6)
