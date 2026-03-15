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


def get_allowed_models() -> list[dict]:
    """Return the allowed model list for the UI (id, label, provider)."""
    data = _load_pricing()
    return list(data.get("allowed_models", []))


def is_allowed_model(model_id: str) -> bool:
    """Return True if model_id is in the allowed list."""
    if not model_id or not model_id.strip():
        return False
    allowed = get_allowed_models()
    ids = {m.get("id") for m in allowed if m.get("id")}
    return model_id.strip() in ids


def get_pricing_for_model(model_id: str) -> dict | None:
    """Return pricing dict for the given model id (e.g. claude-sonnet-4-20250514), or None if unknown."""
    data = _load_pricing()
    model_key = data.get("model_id_to_key", {}).get(model_id)
    if not model_key:
        return None
    return data.get("models", {}).get(model_key)


def get_premium_per_million_tokens() -> float:
    """
    Premium in USD per million tokens (optional markup).
    Prefer premium_per_mtok in JSON; fall back to premium_per_token converted from per-token
    (premium_per_token * 1e6) so that legacy per-token values are not applied as per-million.
    """
    data = _load_pricing()
    if "premium_per_mtok" in data:
        return float(data["premium_per_mtok"])
    # Legacy: premium_per_token was in USD per token; do not use for per-million calc
    return 0.0


def compute_cost(
    input_tokens: int,
    output_tokens: int,
    cache_tokens: int,
    model_id: str,
    use_reasoning: bool = False,
) -> float:
    """
    Compute cost in USD from token counts and model pricing.
    All rates are per million tokens (USD per mtok): cost = tokens * (rate / 1_000_000).
    - input_tokens × input_usd_per_mtok
    - output_tokens × output_usd_per_mtok (or extended_thinking_usd_per_mtok if use_reasoning)
    - cache_tokens × cache_read_usd_per_mtok
    - Optional: premium_per_mtok (USD per million tokens) applied to total tokens.
    """
    pricing = get_pricing_for_model(model_id)
    premium_per_mtok = get_premium_per_million_tokens()
    total_tokens = input_tokens + output_tokens + cache_tokens
    premium_cost = total_tokens * (premium_per_mtok / 1_000_000)

    if not pricing:
        return round(premium_cost, 6)

    input_cost = input_tokens * (pricing["input_usd_per_mtok"] / 1_000_000)
    output_rate = (
        pricing.get("extended_thinking_usd_per_mtok") or pricing["output_usd_per_mtok"]
    ) if use_reasoning else pricing["output_usd_per_mtok"]
    output_cost = output_tokens * (output_rate / 1_000_000)
    cache_cost = cache_tokens * (pricing["cache_read_usd_per_mtok"] / 1_000_000)
    return round(input_cost + output_cost + cache_cost + premium_cost, 6)
