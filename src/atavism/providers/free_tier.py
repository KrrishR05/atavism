"""Strict Free-Tier Cost Guard for Model Providers.

Enforces zero-cost ($0.00) budget constraints:
- Rejects non-free model selections before any network call.
- Validates that models carry explicit zero-cost tags (e.g. OpenRouter ':free' suffix).
- Prohibits automatic fallback to paid models or undisclosed pricing tiers.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from .base import NonFreeModelError, PricingVerificationError
from .secrets import redact_secrets

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
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "liquid/lfm-3-1.7b:free",
    "liquid/lfm-2.5-2.6b:free",
    "cohere/north-mini-code:free",
    "recursive/flint-v1.0:free",
    "xingchen-agi/xing4.0-29b-a4b:free",
    "nvidia/nemotron-3.5-super-vl:free",
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "dots-studio/dots-3-note-preview:free",
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
    def validate_pricing_dict(cls, model_id: str, model_data: dict[str, Any]) -> dict[str, Any]:
        """Validate model metadata and pricing dictionary extracted from /models.

        Strictly enforces:
        - Exact model ID matching
        - Non-null, non-empty, numeric pricing fields
        - Non-negative prices
        - Zero prompt and completion price ($0.00)
        - Zero prices for optional tokens (request, image, cache)
        """
        if not isinstance(model_data, dict):
            raise PricingVerificationError(f"Model metadata for '{model_id}' must be a dictionary, got {type(model_data)}.")

        entry_id = model_data.get("id")
        if not entry_id or entry_id.strip() != model_id.strip():
            raise PricingVerificationError(
                f"Model ID mismatch in metadata: expected '{model_id}', got '{entry_id}'."
            )

        pricing = model_data.get("pricing")
        if pricing is None or not isinstance(pricing, dict):
            raise PricingVerificationError(
                f"Model '{model_id}' is missing required 'pricing' metadata object."
            )

        if "prompt" not in pricing or "completion" not in pricing:
            raise PricingVerificationError(
                f"Model '{model_id}' pricing missing 'prompt' or 'completion' keys: {pricing}"
            )

        prompt_raw = pricing.get("prompt")
        comp_raw = pricing.get("completion")

        if prompt_raw is None or comp_raw is None:
            raise PricingVerificationError(
                f"Model '{model_id}' has null pricing values: prompt={prompt_raw}, completion={comp_raw}."
            )

        if isinstance(prompt_raw, str) and not prompt_raw.strip():
            raise PricingVerificationError(f"Model '{model_id}' has empty prompt price string.")
        if isinstance(comp_raw, str) and not comp_raw.strip():
            raise PricingVerificationError(f"Model '{model_id}' has empty completion price string.")

        try:
            prompt_dec = Decimal(str(prompt_raw))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise PricingVerificationError(
                f"Model '{model_id}' has non-numeric prompt price: {prompt_raw!r}"
            ) from exc

        try:
            comp_dec = Decimal(str(comp_raw))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise PricingVerificationError(
                f"Model '{model_id}' has non-numeric completion price: {comp_raw!r}"
            ) from exc

        if prompt_dec < 0 or comp_dec < 0:
            raise PricingVerificationError(
                f"Model '{model_id}' has negative pricing: prompt={prompt_dec}, completion={comp_dec}."
            )

        if prompt_dec != Decimal("0") or comp_dec != Decimal("0"):
            raise PricingVerificationError(
                f"Model '{model_id}' is not zero-cost: prompt={prompt_dec}, completion={comp_dec}. "
                "Budget authorization is strictly $0.00."
            )

        # Check auxiliary pricing fields if present
        for aux_key in ("request", "image", "input_cache_read", "input_cache_write"):
            if aux_key in pricing and pricing[aux_key] is not None:
                aux_raw = pricing[aux_key]
                try:
                    aux_dec = Decimal(str(aux_raw))
                except (InvalidOperation, TypeError, ValueError) as exc:
                    raise PricingVerificationError(
                        f"Model '{model_id}' has non-numeric '{aux_key}' price: {aux_raw!r}"
                    ) from exc
                if aux_dec != Decimal("0"):
                    raise PricingVerificationError(
                        f"Model '{model_id}' has non-zero '{aux_key}' price: {aux_dec}. "
                        "Budget authorization is strictly $0.00."
                    )

        endpoints = model_data.get("endpoints")
        if endpoints is not None and isinstance(endpoints, list):
            if "/api/v1/chat/completions" not in endpoints and not any("chat" in str(e) for e in endpoints):
                raise PricingVerificationError(
                    f"Model '{model_id}' does not support chat completions endpoint: {endpoints}"
                )

        verified_at = datetime.now(timezone.utc).isoformat()
        return {
            "model_id": model_id,
            "verified_at": verified_at,
            "is_zero_cost": True,
            "pricing_classification": "FREE ($0.00)",
            "prompt_price_token": str(prompt_dec),
            "completion_price_token": str(comp_dec),
            "raw_pricing": pricing,
            "context_length": model_data.get("context_length"),
            "endpoints": endpoints,
        }

    @classmethod
    def verify_dynamic_pricing(
        cls,
        model_id: str,
        base_url: str,
        api_key: str | None = None,
        timeout: int = 15,
    ) -> dict[str, Any]:
        """Fetch live model catalog from /models and verify exact zero-cost pricing preflight.

        Raises PricingVerificationError if:
        - Model is not found in active catalog
        - Metadata or pricing is missing, null, or malformed
        - Pricing is non-numeric, negative, or non-zero
        - Request fails or times out
        """
        cls.assert_free(model_id)

        models_endpoint = f"{base_url.rstrip('/')}/models"
        headers = {
            "User-Agent": "Atavism-Evaluation-Engine/1.0",
            "HTTP-Referer": "https://github.com/atavism-eval/atavism",
            "X-Title": "Atavism Dynamic Pricing Verification",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(models_endpoint, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw_bytes = resp.read()
                data = json.loads(raw_bytes.decode("utf-8"))
        except urllib.error.HTTPError as http_err:
            err_body = ""
            try:
                err_body = http_err.read().decode("utf-8")
            except Exception:
                pass
            msg = redact_secrets(f"HTTP {http_err.code}: {http_err.reason}. {err_body}")
            raise PricingVerificationError(
                f"Failed to fetch model catalog for pricing verification ({msg})"
            ) from http_err
        except urllib.error.URLError as url_err:
            raise PricingVerificationError(
                f"Network error fetching model catalog for pricing verification: {redact_secrets(str(url_err.reason))}"
            ) from url_err
        except TimeoutError as to_err:
            raise PricingVerificationError(
                f"Timeout ({timeout}s) fetching model catalog for dynamic pricing verification."
            ) from to_err
        except Exception as exc:
            raise PricingVerificationError(
                f"Unexpected error during dynamic pricing verification: {redact_secrets(str(exc))}"
            ) from exc

        if not isinstance(data, dict) or "data" not in data or not isinstance(data["data"], list):
            raise PricingVerificationError(
                f"OpenRouter /models returned invalid schema: missing 'data' array in response."
            )

        target_entry: dict[str, Any] | None = None
        for item in data["data"]:
            if isinstance(item, dict) and item.get("id") == model_id:
                target_entry = item
                break

        if target_entry is None:
            raise PricingVerificationError(
                f"Model '{model_id}' was not found in the active OpenRouter model catalog at {models_endpoint}. "
                "Inference blocked under strict cost control."
            )

        evidence = cls.validate_pricing_dict(model_id, target_entry)
        evidence["source_endpoint"] = models_endpoint
        return evidence

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

