"""Base interfaces and data structures for model providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Sequence


class ProviderError(Exception):
    """Base exception for model provider errors."""
    pass


class AuthenticationError(ProviderError):
    """Raised when authentication with the provider fails."""
    pass


class RateLimitError(ProviderError):
    """Raised when provider rate limits are exceeded."""
    pass


class ProviderTimeoutError(ProviderError):
    """Raised when a provider request times out."""
    pass


class NonFreeModelError(ProviderError):
    """Raised when a non-free model is requested under zero-cost budget constraints."""
    pass


class MalformedResponseError(ProviderError):
    """Raised when the provider response format is unexpected or unparseable."""
    pass


class PricingVerificationError(ProviderError):
    """Raised when dynamic pricing verification fails or cannot prove zero cost."""
    pass


class ModelMismatchError(ProviderError):
    """Raised when the provider returns an unexpected model ID or unauthorized substitution."""
    pass


@dataclass(frozen=True)
class ChatMessage:
    """A single chat message in a completion request."""
    role: str
    content: str


@dataclass(frozen=True)
class CompletionRequest:
    """Standardized request for model code completion."""
    messages: tuple[ChatMessage, ...]
    model: str
    temperature: float = 0.0
    max_tokens: int = 4096
    stop: tuple[str, ...] | None = None
    timeout: int = 60
    metadata: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_prompt(
        cls,
        user_prompt: str,
        system_prompt: str = "",
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        timeout: int = 60,
    ) -> CompletionRequest:
        """Create a completion request from system and user prompt strings."""
        msgs: list[ChatMessage] = []
        if system_prompt:
            msgs.append(ChatMessage(role="system", content=system_prompt))
        msgs.append(ChatMessage(role="user", content=user_prompt))
        return cls(
            messages=tuple(msgs),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )


@dataclass(frozen=True)
class CompletionResponse:
    """Standardized response from a model completion."""
    content: str
    model_name: str
    provider: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = 0.0
    latency_seconds: float = 0.0
    finish_reason: str = "stop"
    pricing_evidence: dict[str, object] = field(default_factory=dict)
    routing_metadata: dict[str, object] = field(default_factory=dict)
    raw_response: dict[str, object] = field(default_factory=dict)


class ModelProvider(ABC):
    """Abstract interface for model providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. 'openrouter')."""
        raise NotImplementedError

    @abstractmethod
    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a completion request."""
        raise NotImplementedError

    @abstractmethod
    def check_connection(self) -> tuple[bool, str]:
        """Check provider connectivity and credential validity."""
        raise NotImplementedError

