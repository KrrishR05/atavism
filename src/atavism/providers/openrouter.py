"""OpenRouter API provider adapter with strict zero-cost free-tier enforcement."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from .base import (
    AuthenticationError,
    CompletionRequest,
    CompletionResponse,
    MalformedResponseError,
    ModelProvider,
    ProviderError,
    ProviderTimeoutError,
    RateLimitError,
)
from .free_tier import FreeTierGuard
from .secrets import mask_secret, redact_secrets

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_FREE_MODEL = "meta-llama/llama-3.3-70b-instruct:free"


class OpenRouterProvider(ModelProvider):
    """OpenRouter provider supporting free-tier models under strict $0 budget control."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str = DEFAULT_FREE_MODEL,
        enforce_free_tier: bool = True,
        timeout: int = 60,
    ) -> None:
        self.api_key = (api_key or os.environ.get("OPENROUTER_API_KEY", "")).strip()
        self.base_url = (base_url or os.environ.get("OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL)).rstrip("/")
        self.default_model = default_model
        self.enforce_free_tier = enforce_free_tier
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return "openrouter"

    def check_connection(self) -> tuple[bool, str]:
        """Verify OpenRouter credentials and connectivity."""
        if not self.api_key:
            return False, "OPENROUTER_API_KEY is not configured in environment or .env."

        # Probe key via auth key endpoint
        url = f"{self.base_url}/auth/key"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/atavism-eval/atavism",
            "X-Title": "Atavism Benchmark Evaluation",
        }
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                label = data.get("data", {}).get("label") or "Authenticated"
                return True, f"OpenRouter connected ({label}, Key: {mask_secret(self.api_key)})"
        except urllib.error.HTTPError as err:
            if err.code in (401, 403):
                return False, f"OpenRouter authentication failed (HTTP {err.code}): Invalid API key."
            return False, f"OpenRouter connection returned HTTP {err.code}: {err.reason}"
        except Exception as exc:
            return False, f"OpenRouter connectivity check failed: {redact_secrets(str(exc))}"

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send completion request to OpenRouter with zero-cost verification."""
        model = request.model or self.default_model

        # 1. Strict Free-Tier Guard Assertion
        if self.enforce_free_tier:
            FreeTierGuard.assert_free(model)

        # 2. Credential Verification
        if not self.api_key:
            raise AuthenticationError(
                "OPENROUTER_API_KEY is missing. "
                "Set the OPENROUTER_API_KEY environment variable or populate .env."
            )

        # 3. Mandatory Pre-Request Verification Display
        pricing = FreeTierGuard.get_pricing_info(model)
        print(
            f"[API Request] Provider: OpenRouter | "
            f"Model: {model} | "
            f"Pricing: {pricing['pricing_classification']} | "
            f"Expected Cost: $0.00 | "
            f"Max Tokens: {request.max_tokens}"
        )

        # 4. Construct Request Payload
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.stop:
            payload["stop"] = list(request.stop)

        body_bytes = json.dumps(payload).encode("utf-8")
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/atavism-eval/atavism",
            "X-Title": "Atavism Benchmark Evaluation",
            "User-Agent": "Atavism-Evaluation-Engine/1.0",
        }

        req = urllib.request.Request(endpoint, data=body_bytes, headers=headers, method="POST")

        start_time = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=request.timeout or self.timeout) as resp:
                raw_data = resp.read().decode("utf-8")
                latency = time.monotonic() - start_time
        except urllib.error.HTTPError as http_err:
            latency = time.monotonic() - start_time
            err_body = ""
            try:
                err_body = http_err.read().decode("utf-8")
            except Exception:
                pass
            err_msg = redact_secrets(f"HTTP {http_err.code}: {http_err.reason}. {err_body}")

            if http_err.code in (401, 403):
                raise AuthenticationError(f"OpenRouter authentication failed: {err_msg}") from http_err
            elif http_err.code == 429:
                raise RateLimitError(f"OpenRouter free-tier rate limit exceeded: {err_msg}") from http_err
            elif http_err.code >= 500:
                raise ProviderError(f"OpenRouter provider error: {err_msg}") from http_err
            else:
                raise ProviderError(f"OpenRouter request error: {err_msg}") from http_err
        except urllib.error.URLError as url_err:
            latency = time.monotonic() - start_time
            if "timed out" in str(url_err.reason).lower():
                raise ProviderTimeoutError(f"OpenRouter request timed out after {request.timeout}s") from url_err
            raise ProviderError(f"OpenRouter connection failed: {redact_secrets(str(url_err.reason))}") from url_err
        except TimeoutError as timeout_err:
            raise ProviderTimeoutError(f"OpenRouter request timed out after {request.timeout}s") from timeout_err
        except Exception as exc:
            raise ProviderError(f"Unexpected error communicating with OpenRouter: {redact_secrets(str(exc))}") from exc

        # 5. Parse and Validate Response JSON
        try:
            resp_json = json.loads(raw_data)
        except Exception as exc:
            raise MalformedResponseError(f"OpenRouter returned invalid JSON: {exc}") from exc

        choices = resp_json.get("choices")
        if not choices or not isinstance(choices, list):
            raise MalformedResponseError(f"OpenRouter response missing 'choices' array: {resp_json}")

        first_choice = choices[0]
        message = first_choice.get("message", {})
        content = message.get("content", "")
        finish_reason = first_choice.get("finish_reason", "stop")
        actual_model = resp_json.get("model", model)

        usage = resp_json.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")

        return CompletionResponse(
            content=content,
            model_name=actual_model,
            provider="openrouter",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=0.0,  # Strictly zero cost for free tier
            latency_seconds=latency,
            finish_reason=finish_reason,
            raw_response=resp_json,
        )

