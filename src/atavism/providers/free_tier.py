"""Strict Free-Tier Cost Guard for Model Providers.

Enforces zero-cost ($0.00) budget constraints:
- Rejects non-free model selections before any network call.
- Validates that models carry explicit zero-cost tags (e.g. OpenRouter ':free' suffix).
- Prohibits automatic fallback to paid models or undisclosed pricing tiers.
"""

from __future__ import annotations

from .base import NonFreeModelError

# Curated list of verified zero-cost free-tier models on OpenRouter.
# All verified OpenRouter free models carry the explicit ':free' suffix.
VERIFIED_FREE_MODELS: tuple[str, ...] = (
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-r1:free",
    "deepseek/deepseek-chat:free",
    "google/gemini-2.0-flash-exp:free",
    "google/gemini-2.0-flash-thinking-exp:free",
    "mistralai/mistral-small-24b-instruct-2501:free",
    "qwen/qwen-2.5-coder-32b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "microsoft/phi-3-medium-128k-instruct:free",
    "microsoft/phi-3-mini-128k-instruct:free",
)


class FreeTierGuard:
    """Safeguard enforcing zero-cost ($0.00) model evaluation."""

    FREE_SUFFIX = ":free"

    @classmethod
    def is_free_tier(cls, model_id: str) -> bool:
        """Check if a model ID represents a verified zero-cost free-tier model."""
        clean_id = (model_id or "").strip().lower()
        if not clean_id:
            return False
        # OpenRouter free models explicitly end with ':free'
        if clean_id.endswith(cls.FREE_SUFFIX):
            return True
        return clean_id in {m.lower() for m in VERIFIED_FREE_MODELS}

    @classmethod
    def assert_free(cls, model_id: str) -> None:
        """Assert that the requested model is verified free, raising NonFreeModelError if not."""
        if not cls.is_free_tier(model_id):
            raise NonFreeModelError(
                f"Model '{model_id}' is rejected under strict cost control. "
                "Budget authorization is $0.00. "
                f"Only verified free-tier models ending in '{cls.FREE_SUFFIX}' are permitted "
                "(e.g., 'meta-llama/llama-3.3-70b-instruct:free', 'deepseek/deepseek-r1:free')."
            )

    @classmethod
    def get_pricing_info(cls, model_id: str) -> dict[str, object]:
        """Return pricing specification for a model."""
        is_free = cls.is_free_tier(model_id)
        return {
            "model_id": model_id,
            "is_free": is_free,
            "pricing_classification": "FREE ($0.00)" if is_free else "PAID / DISALLOWED",
            "expected_cost_usd": 0.0 if is_free else None,
            "prompt_cost_per_million": 0.0 if is_free else None,
            "completion_cost_per_million": 0.0 if is_free else None,
        }

