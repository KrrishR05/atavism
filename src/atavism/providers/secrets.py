"""Credential management, masking, and secret redaction utilities."""

from __future__ import annotations

import os
import re

# Known sensitive environment variable names
SENSITIVE_ENV_VARS: tuple[str, ...] = (
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "FRONTIER_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "GITHUB_TOKEN",
)


def mask_secret(secret: str | None, visible_prefix: int = 4, visible_suffix: int = 4) -> str:
    """Mask an API key or token for display.
    
    Example:
        'sk-or-v1-abcdef1234567890' -> 'sk-o...7890'
        '' or None -> '[NOT CONFIGURED]'
    """
    if not secret:
        return "[NOT CONFIGURED]"
    s = secret.strip()
    if len(s) <= visible_prefix + visible_suffix:
        return "********"
    return f"{s[:visible_prefix]}...{s[-visible_suffix:]}"


def redact_secrets(text: str, secrets: list[str] | None = None) -> str:
    """Redact known API keys from text, transcripts, logs, and exception strings."""
    if not text:
        return text

    target_secrets: list[str] = []
    if secrets:
        target_secrets.extend(s for s in secrets if s and len(s) > 5)

    # Automatically discover active API keys from environment
    for var in SENSITIVE_ENV_VARS:
        val = os.environ.get(var, "")
        if val and len(val) > 5 and val not in target_secrets:
            target_secrets.append(val)

    redacted = text
    for sec in target_secrets:
        redacted = redacted.replace(sec, "[REDACTED_API_KEY]")

    # Generic bearer token regex redaction
    redacted = re.sub(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{8,}", r"\1[REDACTED_API_KEY]", redacted)
    # Generic OpenRouter key pattern (sk-or-v1-...)
    redacted = re.sub(r"sk-or-v1-[a-zA-Z0-9]{16,}", "[REDACTED_API_KEY]", redacted)

    return redacted


def load_dotenv(dotenv_path: str | os.PathLike[str] | None = None) -> dict[str, str]:
    """Load key-value pairs from a .env file into os.environ if not already present.

    Uses pure Python standard library only (no external dependencies).
    """
    from pathlib import Path

    target_path: Path
    if dotenv_path is None:
        target_path = Path.cwd() / ".env"
    else:
        target_path = Path(dotenv_path)

    if not target_path.is_file():
        return {}

    loaded: dict[str, str] = {}
    try:
        content = target_path.read_text(encoding="utf-8")
    except Exception:
        return {}

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val
                loaded[key] = val

    return loaded

