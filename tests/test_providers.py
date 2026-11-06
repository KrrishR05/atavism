"""Unit tests for model provider adapters, free-tier guard, and secret redaction."""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from atavism.providers import (
    AuthenticationError,
    CompletionRequest,
    FreeTierGuard,
    MalformedResponseError,
    NonFreeModelError,
    OpenRouterProvider,
    ProviderError,
    ProviderTimeoutError,
    RateLimitError,
    get_provider,
    mask_secret,
    redact_secrets,
)


class TestSecretMaskingAndRedaction:
    """Verify that credentials are appropriately masked and redacted."""

    def test_mask_secret_unconfigured(self) -> None:
        assert mask_secret("") == "[NOT CONFIGURED]"
        assert mask_secret(None) == "[NOT CONFIGURED]"

    def test_mask_secret_masks_middle(self) -> None:
        masked = mask_secret("sk-or-v1-abcdef0123456789")
        assert "abcdef" not in masked
        assert masked.startswith("sk-o")
        assert masked.endswith("6789")

    def test_redact_secrets_explicit(self) -> None:
        secret = "sk-or-v1-my-secret-token-12345678"
        text = f"An error occurred with key {secret} in request"
        redacted = redact_secrets(text, secrets=[secret])
        assert secret not in redacted
        assert "[REDACTED_API_KEY]" in redacted

    def test_redact_secrets_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dummy_key = "sk-or-v1-supersecretkey99999999"
        monkeypatch.setenv("OPENROUTER_API_KEY", dummy_key)
        raw_msg = f"Failed to connect using Bearer {dummy_key}"
        clean_msg = redact_secrets(raw_msg)
        assert dummy_key not in clean_msg
        assert "[REDACTED_API_KEY]" in clean_msg


class TestFreeTierGuard:
    """Verify strict $0.00 zero-cost budget enforcement."""

    def test_free_tier_suffix_allowed(self) -> None:
        assert FreeTierGuard.is_free_tier("meta-llama/llama-3.3-70b-instruct:free") is True
        assert FreeTierGuard.is_free_tier("deepseek/deepseek-r1:free") is True
        assert FreeTierGuard.is_free_tier("google/gemini-2.0-flash-exp:free") is True

    def test_paid_model_rejected(self) -> None:
        assert FreeTierGuard.is_free_tier("openai/gpt-4o") is False
        assert FreeTierGuard.is_free_tier("anthropic/claude-3-5-sonnet") is False
        assert FreeTierGuard.is_free_tier("meta-llama/llama-3.3-70b-instruct") is False

    def test_assert_free_raises_on_paid_model(self) -> None:
        with pytest.raises(NonFreeModelError) as exc_info:
            FreeTierGuard.assert_free("openai/gpt-4o")
        assert "Budget authorization is $0.00" in str(exc_info.value)
        assert "Only verified free-tier models ending in ':free'" in str(exc_info.value)

    def test_assert_free_succeeds_on_free_model(self) -> None:
        FreeTierGuard.assert_free("meta-llama/llama-3.3-70b-instruct:free")


class TestOpenRouterProvider:
    """Verify OpenRouter provider behavior under mocked HTTP calls."""

    def test_missing_api_key_raises_auth_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        provider = OpenRouterProvider(api_key="")
        req = CompletionRequest.from_prompt("Hello", model="meta-llama/llama-3.3-70b-instruct:free")
        with pytest.raises(AuthenticationError) as exc:
            provider.complete(req)
        assert "OPENROUTER_API_KEY is missing" in str(exc.value)

    def test_enforce_free_tier_blocks_paid_model(self) -> None:
        provider = OpenRouterProvider(api_key="test-key", enforce_free_tier=True)
        req = CompletionRequest.from_prompt("Hello", model="openai/gpt-4o")
        with pytest.raises(NonFreeModelError):
            provider.complete(req)

    def test_complete_successful_response(self) -> None:
        provider = OpenRouterProvider(api_key="test-key")
        req = CompletionRequest.from_prompt(
            user_prompt="Write a function",
            system_prompt="Be concise",
            model="meta-llama/llama-3.3-70b-instruct:free",
        )

        mock_response_body = {
            "id": "gen-12345",
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "def hello(): pass"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 8,
                "total_tokens": 20,
            },
        }

        mock_cm = MagicMock()
        mock_cm.read.return_value = json.dumps(mock_response_body).encode("utf-8")
        mock_cm.__enter__.return_value = mock_cm

        with patch("urllib.request.urlopen", return_value=mock_cm):
            resp = provider.complete(req)

        assert resp.content == "def hello(): pass"
        assert resp.prompt_tokens == 12
        assert resp.completion_tokens == 8
        assert resp.cost_usd == 0.0
        assert resp.finish_reason == "stop"

    def test_complete_handles_http_401_auth_error(self) -> None:
        provider = OpenRouterProvider(api_key="invalid-key")
        req = CompletionRequest.from_prompt("Hi", model="meta-llama/llama-3.3-70b-instruct:free")

        http_err = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs=MagicMock(),
            fp=io.BytesIO(b'{"error": "Invalid API key"}'),
        )

        with patch("urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(AuthenticationError) as exc_info:
                provider.complete(req)
            assert "authentication failed" in str(exc_info.value).lower()

    def test_complete_handles_http_429_rate_limit(self) -> None:
        provider = OpenRouterProvider(api_key="test-key")
        req = CompletionRequest.from_prompt("Hi", model="meta-llama/llama-3.3-70b-instruct:free")

        http_err = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs=MagicMock(),
            fp=io.BytesIO(b'{"error": "Free tier rate limit reached"}'),
        )

        with patch("urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(RateLimitError) as exc_info:
                provider.complete(req)
            assert "rate limit exceeded" in str(exc_info.value).lower()

    def test_complete_handles_timeout(self) -> None:
        provider = OpenRouterProvider(api_key="test-key")
        req = CompletionRequest.from_prompt("Hi", model="meta-llama/llama-3.3-70b-instruct:free", timeout=5)

        with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
            with pytest.raises(ProviderTimeoutError) as exc_info:
                provider.complete(req)
            assert "timed out after 5s" in str(exc_info.value)

    def test_complete_handles_malformed_json(self) -> None:
        provider = OpenRouterProvider(api_key="test-key")
        req = CompletionRequest.from_prompt("Hi", model="meta-llama/llama-3.3-70b-instruct:free")

        mock_cm = MagicMock()
        mock_cm.read.return_value = b"<html>502 Bad Gateway</html>"
        mock_cm.__enter__.return_value = mock_cm

        with patch("urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(MalformedResponseError):
                provider.complete(req)

    def test_check_connection_unconfigured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        provider = OpenRouterProvider(api_key="")
        ok, msg = provider.check_connection()
        assert ok is False
        assert "not configured" in msg


class TestProviderFactory:
    """Verify get_provider behavior."""

    def test_get_openrouter_provider(self) -> None:
        p = get_provider("openrouter", api_key="sk-test")
        assert p.provider_name == "openrouter"

    def test_unsupported_provider_raises(self) -> None:
        with pytest.raises(ValueError) as exc:
            get_provider("unsupported_provider")
        assert "Unsupported provider" in str(exc.value)

