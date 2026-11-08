"""Provider integration layer for model evaluation."""

from __future__ import annotations

from .base import (
    AuthenticationError,
    ChatMessage,
    CompletionRequest,
    CompletionResponse,
    MalformedResponseError,
    ModelMismatchError,
    ModelProvider,
    NonFreeModelError,
    PricingVerificationError,
    ProviderError,
    ProviderTimeoutError,
    RateLimitError,
)
from .free_tier import VERIFIED_FREE_MODELS, FreeTierGuard
from .openrouter import DEFAULT_FREE_MODEL, DEFAULT_OPENROUTER_BASE_URL, OpenRouterProvider
from .secrets import SENSITIVE_ENV_VARS, load_dotenv, mask_secret, redact_secrets


def get_provider(
    name: str = "openrouter",
    api_key: str | None = None,
    base_url: str | None = None,
    default_model: str = DEFAULT_FREE_MODEL,
    enforce_free_tier: bool = True,
    dynamic_pricing_check: bool = True,
) -> ModelProvider:
    """Factory for model providers."""
    prov_name = (name or "").strip().lower()
    if prov_name == "openrouter":
        return OpenRouterProvider(
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            enforce_free_tier=enforce_free_tier,
            dynamic_pricing_check=dynamic_pricing_check,
        )
    raise ValueError(f"Unsupported provider: '{name}'. Initial free-tier phase supports 'openrouter'.")


__all__ = [
    "AuthenticationError",
    "ChatMessage",
    "CompletionRequest",
    "CompletionResponse",
    "DEFAULT_FREE_MODEL",
    "DEFAULT_OPENROUTER_BASE_URL",
    "FreeTierGuard",
    "MalformedResponseError",
    "ModelMismatchError",
    "ModelProvider",
    "NonFreeModelError",
    "OpenRouterProvider",
    "PricingVerificationError",
    "ProviderError",
    "ProviderTimeoutError",
    "RateLimitError",
    "SENSITIVE_ENV_VARS",
    "VERIFIED_FREE_MODELS",
    "get_provider",
    "load_dotenv",
    "mask_secret",
    "redact_secrets",
]

