"""Unit tests for model provider adapters, free-tier guard, dynamic pricing, and secret redaction."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

from atavism.providers import (
    AuthenticationError,
    CompletionRequest,
    FreeTierGuard,
    MalformedResponseError,
    ModelMismatchError,
    NonFreeModelError,
    OpenRouterProvider,
    PricingVerificationError,
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

    def test_bearer_token_pattern_redacted(self) -> None:
        raw_msg = "Authorization: Bearer secret_token_1234567890abcdef"
        clean_msg = redact_secrets(raw_msg)
        assert "secret_token" not in clean_msg
        assert "[REDACTED_API_KEY]" in clean_msg


class TestFreeTierGuard:
    """Verify strict $0.00 zero-cost budget enforcement."""

    def test_free_tier_suffix_allowed(self) -> None:
        assert FreeTierGuard.is_free_tier("meta-llama/llama-3.3-70b-instruct:free") is True
        assert FreeTierGuard.is_free_tier("deepseek/deepseek-r1:free") is True
        assert FreeTierGuard.is_free_tier("google/gemini-2.0-flash-exp:free") is True
        assert FreeTierGuard.is_free_tier("google/gemma-4-26b-a4b-it:free") is True

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


class TestDynamicPricingVerification:
    """Verify live pricing verification logic against /models metadata (F-02)."""

    def test_valid_zero_cost_pricing_succeeds(self) -> None:
        valid_meta = {
            "id": "meta-llama/llama-3.3-70b-instruct:free",
            "context_length": 131072,
            "pricing": {"prompt": "0", "completion": "0"},
            "endpoints": ["/api/v1/chat/completions"],
        }
        evidence = FreeTierGuard.validate_pricing_dict("meta-llama/llama-3.3-70b-instruct:free", valid_meta)
        assert evidence["is_zero_cost"] is True
        assert evidence["prompt_price_token"] == "0"
        assert evidence["completion_price_token"] == "0"

    def test_model_id_mismatch_rejected(self) -> None:
        meta = {
            "id": "meta-llama/llama-3.3-70b-instruct",  # Lacks :free
            "pricing": {"prompt": "0", "completion": "0"},
        }
        with pytest.raises(PricingVerificationError) as exc:
            FreeTierGuard.validate_pricing_dict("meta-llama/llama-3.3-70b-instruct:free", meta)
        assert "Model ID mismatch" in str(exc.value)

    def test_missing_pricing_metadata_rejected(self) -> None:
        meta = {"id": "meta-llama/llama-3.3-70b-instruct:free"}
        with pytest.raises(PricingVerificationError) as exc:
            FreeTierGuard.validate_pricing_dict("meta-llama/llama-3.3-70b-instruct:free", meta)
        assert "missing required 'pricing'" in str(exc.value)

    def test_missing_prompt_or_completion_key_rejected(self) -> None:
        meta = {
            "id": "meta-llama/llama-3.3-70b-instruct:free",
            "pricing": {"prompt": "0"},  # Missing completion
        }
        with pytest.raises(PricingVerificationError) as exc:
            FreeTierGuard.validate_pricing_dict("meta-llama/llama-3.3-70b-instruct:free", meta)
        assert "missing 'prompt' or 'completion'" in str(exc.value)

    def test_null_pricing_rejected(self) -> None:
        meta = {
            "id": "meta-llama/llama-3.3-70b-instruct:free",
            "pricing": {"prompt": None, "completion": "0"},
        }
        with pytest.raises(PricingVerificationError) as exc:
            FreeTierGuard.validate_pricing_dict("meta-llama/llama-3.3-70b-instruct:free", meta)
        assert "null pricing values" in str(exc.value)

    def test_empty_pricing_string_rejected(self) -> None:
        meta = {
            "id": "meta-llama/llama-3.3-70b-instruct:free",
            "pricing": {"prompt": " ", "completion": "0"},
        }
        with pytest.raises(PricingVerificationError) as exc:
            FreeTierGuard.validate_pricing_dict("meta-llama/llama-3.3-70b-instruct:free", meta)
        assert "empty prompt price" in str(exc.value)

    def test_non_numeric_pricing_rejected(self) -> None:
        meta = {
            "id": "meta-llama/llama-3.3-70b-instruct:free",
            "pricing": {"prompt": "free", "completion": "0"},
        }
        with pytest.raises(PricingVerificationError) as exc:
            FreeTierGuard.validate_pricing_dict("meta-llama/llama-3.3-70b-instruct:free", meta)
        assert "non-numeric prompt price" in str(exc.value)

    def test_negative_pricing_rejected(self) -> None:
        meta = {
            "id": "meta-llama/llama-3.3-70b-instruct:free",
            "pricing": {"prompt": "-0.01", "completion": "0"},
        }
        with pytest.raises(PricingVerificationError) as exc:
            FreeTierGuard.validate_pricing_dict("meta-llama/llama-3.3-70b-instruct:free", meta)
        assert "negative pricing" in str(exc.value)

    def test_nonzero_prompt_pricing_rejected(self) -> None:
        meta = {
            "id": "meta-llama/llama-3.3-70b-instruct:free",
            "pricing": {"prompt": "0.00000015", "completion": "0"},
        }
        with pytest.raises(PricingVerificationError) as exc:
            FreeTierGuard.validate_pricing_dict("meta-llama/llama-3.3-70b-instruct:free", meta)
        assert "not zero-cost" in str(exc.value)
        assert "Budget authorization is strictly $0.00" in str(exc.value)

    def test_nonzero_completion_pricing_rejected(self) -> None:
        meta = {
            "id": "meta-llama/llama-3.3-70b-instruct:free",
            "pricing": {"prompt": "0", "completion": "0.0000006"},
        }
        with pytest.raises(PricingVerificationError) as exc:
            FreeTierGuard.validate_pricing_dict("meta-llama/llama-3.3-70b-instruct:free", meta)
        assert "not zero-cost" in str(exc.value)

    def test_nonzero_auxiliary_pricing_rejected(self) -> None:
        meta = {
            "id": "meta-llama/llama-3.3-70b-instruct:free",
            "pricing": {"prompt": "0", "completion": "0", "request": "0.001"},
        }
        with pytest.raises(PricingVerificationError) as exc:
            FreeTierGuard.validate_pricing_dict("meta-llama/llama-3.3-70b-instruct:free", meta)
        assert "non-zero 'request' price" in str(exc.value)

    def test_unsupported_chat_endpoint_rejected(self) -> None:
        meta = {
            "id": "meta-llama/llama-3.3-70b-instruct:free",
            "pricing": {"prompt": "0", "completion": "0"},
            "endpoints": ["/api/v1/embeddings"],
        }
        with pytest.raises(PricingVerificationError) as exc:
            FreeTierGuard.validate_pricing_dict("meta-llama/llama-3.3-70b-instruct:free", meta)
        assert "does not support chat completions endpoint" in str(exc.value)

    def test_fetch_dynamic_pricing_unknown_model_raises(self) -> None:
        mock_resp = {
            "data": [
                {
                    "id": "other-model:free",
                    "pricing": {"prompt": "0", "completion": "0"},
                }
            ]
        }
        mock_cm = MagicMock()
        mock_cm.read.return_value = json.dumps(mock_resp).encode("utf-8")
        mock_cm.__enter__.return_value = mock_cm

        with patch("urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(PricingVerificationError) as exc:
                FreeTierGuard.verify_dynamic_pricing(
                    model_id="meta-llama/llama-3.3-70b-instruct:free",
                    base_url="https://openrouter.ai/api/v1",
                )
            assert "was not found in the active OpenRouter model catalog" in str(exc.value)


class TestFallbackEnforcementAndRouting:
    """Verify fallback disabling (F-01) and model preservation."""

    def test_request_payload_disables_fallbacks(self) -> None:
        provider = OpenRouterProvider(api_key="test-key", dynamic_pricing_check=False)
        req = CompletionRequest.from_prompt("Hello", model="meta-llama/llama-3.3-70b-instruct:free")

        captured_request_bytes: list[bytes] = []

        def fake_urlopen(url_req, **kwargs):
            captured_request_bytes.append(url_req.data)
            mock_cm = MagicMock()
            mock_cm.read.return_value = json.dumps({
                "id": "gen-1",
                "model": "meta-llama/llama-3.3-70b-instruct:free",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            }).encode("utf-8")
            mock_cm.__enter__.return_value = mock_cm
            return mock_cm

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            provider.complete(req)

        assert len(captured_request_bytes) == 1
        payload = json.loads(captured_request_bytes[0].decode("utf-8"))
        assert payload["model"] == "meta-llama/llama-3.3-70b-instruct:free"
        assert "provider" in payload
        assert payload["provider"]["allow_fallbacks"] is False
        assert payload["provider"]["require_parameters"] is True

    def test_returned_model_mismatch_raises_model_mismatch_error(self) -> None:
        provider = OpenRouterProvider(api_key="test-key", dynamic_pricing_check=False)
        req = CompletionRequest.from_prompt("Hello", model="meta-llama/llama-3.3-70b-instruct:free")

        mock_cm = MagicMock()
        # Returns deepseek instead of requested llama
        mock_cm.read.return_value = json.dumps({
            "id": "gen-1",
            "model": "deepseek/deepseek-chat:free",
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        }).encode("utf-8")
        mock_cm.__enter__.return_value = mock_cm

        with patch("urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(ModelMismatchError) as exc:
                provider.complete(req)
            assert "Model substitution detected" in str(exc.value)
            assert "requested 'meta-llama/llama-3.3-70b-instruct:free'" in str(exc.value)

    def test_paid_model_substitution_without_free_suffix_rejected(self) -> None:
        provider = OpenRouterProvider(api_key="test-key", dynamic_pricing_check=False)
        req = CompletionRequest.from_prompt("Hello", model="meta-llama/llama-3.3-70b-instruct:free")

        mock_cm = MagicMock()
        # Returns paid version without :free suffix
        mock_cm.read.return_value = json.dumps({
            "id": "gen-1",
            "model": "meta-llama/llama-3.3-70b-instruct",
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        }).encode("utf-8")
        mock_cm.__enter__.return_value = mock_cm

        with patch("urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(ModelMismatchError) as exc:
                provider.complete(req)
            assert "Model substitution detected" in str(exc.value)

    def test_routing_metadata_captured_in_response(self) -> None:
        provider = OpenRouterProvider(api_key="test-key", dynamic_pricing_check=False)
        req = CompletionRequest.from_prompt("Hello", model="meta-llama/llama-3.3-70b-instruct:free")

        mock_cm = MagicMock()
        mock_cm.read.return_value = json.dumps({
            "id": "gen-abc-123",
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "provider": "Together",
            "choices": [{"message": {"content": "result"}, "finish_reason": "stop"}],
        }).encode("utf-8")
        mock_cm.__enter__.return_value = mock_cm

        with patch("urllib.request.urlopen", return_value=mock_cm):
            resp = provider.complete(req)

        assert resp.routing_metadata["requested_model"] == "meta-llama/llama-3.3-70b-instruct:free"
        assert resp.routing_metadata["returned_model"] == "meta-llama/llama-3.3-70b-instruct:free"
        assert resp.routing_metadata["allow_fallbacks"] is False
        assert resp.routing_metadata["provider"] == "Together"
        assert resp.routing_metadata["generation_id"] == "gen-abc-123"

    def test_post_request_cost_nonzero_rejected(self) -> None:
        provider = OpenRouterProvider(api_key="test-key", dynamic_pricing_check=False)
        req = CompletionRequest.from_prompt("Hello", model="meta-llama/llama-3.3-70b-instruct:free")

        mock_cm = MagicMock()
        mock_cm.read.return_value = json.dumps({
            "id": "gen-1",
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.005},
        }).encode("utf-8")
        mock_cm.__enter__.return_value = mock_cm

        with patch("urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(ProviderError) as exc:
                provider.complete(req)
            assert "non-zero post-request billing" in str(exc.value)


class TestOpenRouterProviderMechanics:
    """Verify standard completion error handling and recovery."""

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
        provider = OpenRouterProvider(api_key="test-key", dynamic_pricing_check=False)
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
        provider = OpenRouterProvider(api_key="invalid-key", dynamic_pricing_check=False)
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
        provider = OpenRouterProvider(api_key="test-key", dynamic_pricing_check=False)
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
        provider = OpenRouterProvider(api_key="test-key", dynamic_pricing_check=False)
        req = CompletionRequest.from_prompt("Hi", model="meta-llama/llama-3.3-70b-instruct:free", timeout=5)

        with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
            with pytest.raises(ProviderTimeoutError) as exc_info:
                provider.complete(req)
            assert "timed out after 5s" in str(exc_info.value)

    def test_complete_handles_malformed_json(self) -> None:
        provider = OpenRouterProvider(api_key="test-key", dynamic_pricing_check=False)
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
