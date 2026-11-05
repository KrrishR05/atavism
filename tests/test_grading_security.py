"""Tests for candidate execution security and environment scrubbing."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from atavism.grading import (
    SAFE_SYSTEM_ENV_VARS,
    SENSITIVE_ENV_PATTERNS,
    GradeResult,
    build_minimal_env,
    grade_candidate,
)

ROOT = Path(__file__).resolve().parent.parent
T01_DIR = ROOT / "benchmark" / "tasks" / "T01_retry_semantics"


class TestEnvironmentScrubbing:
    """Verify that candidate subprocess environment excludes host credentials and secrets."""

    def test_build_minimal_env_filters_sensitive_variables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-live-123456789")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-secret-key")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_fakeToken123456789")
        monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/ssh-agent.sock")
        monkeypatch.setenv("DATABASE_PASSWORD", "supersecret123")
        monkeypatch.setenv("CUSTOM_SECRET_AUTH", "bearer-token")

        clean_env = build_minimal_env(["/fake/src", "/fake/tests"])

        for key in clean_env:
            key_upper = key.upper()
            assert not any(pat in key_upper for pat in SENSITIVE_ENV_PATTERNS), (
                f"Sensitive pattern leaked into clean environment: {key}"
            )
            assert key_upper in SAFE_SYSTEM_ENV_VARS or key in (
                "PYTHONPATH",
                "PYTHONDONTWRITEBYTECODE",
                "PYTHONIOENCODING",
            )

        assert "OPENAI_API_KEY" not in clean_env
        assert "ANTHROPIC_API_KEY" not in clean_env
        assert "AWS_SECRET_ACCESS_KEY" not in clean_env
        assert "GITHUB_TOKEN" not in clean_env
        assert "SSH_AUTH_SOCK" not in clean_env
        assert "DATABASE_PASSWORD" not in clean_env
        assert "CUSTOM_SECRET_AUTH" not in clean_env

    def test_build_minimal_env_preserves_runtime_variables(self) -> None:
        clean_env = build_minimal_env(["/fake/src", "/fake/tests"])
        assert "PYTHONPATH" in clean_env
        assert "/fake/src" in clean_env["PYTHONPATH"]
        assert clean_env.get("PYTHONDONTWRITEBYTECODE") == "1"
        assert clean_env.get("PYTHONIOENCODING") == "utf-8"

        # On Windows or POSIX, PATH must be preserved for Python runtime DLL resolution
        assert "PATH" in clean_env

    def test_candidate_subprocess_cannot_read_host_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Execute a candidate via grade_candidate and prove host environment secrets are unreadable."""
        monkeypatch.setenv("ATAVISM_TEST_SECRET_KEY", "unauthorized_host_token_999")

        # Candidate checks that ATAVISM_TEST_SECRET_KEY is absent
        with tempfile.TemporaryDirectory(prefix="test_sec_cand_") as tmpdir:
            cand_file = Path(tmpdir) / "client.py"
            cand_file.write_text(
                "import os\n"
                "from atavism_retry.types import Response\n"
                "def send_with_retry(request, transport, policy, clock=None, sleep=None):\n"
                "    secret = os.environ.get('ATAVISM_TEST_SECRET_KEY')\n"
                "    if secret is not None:\n"
                "        raise RuntimeError(f'SECRET_LEAKED: {secret}')\n"
                "    return transport(request)\n",
                encoding="utf-8",
            )

            types_path = T01_DIR / "variants" / "A" / "workspace" / "src" / "atavism_retry" / "types.py"
            conftest_path = T01_DIR / "private" / "tests" / "conftest.py"
            test_path = T01_DIR / "private" / "tests" / "common"

            res = grade_candidate(
                candidate_path=cand_file,
                types_path=types_path,
                test_dirs=[test_path],
                conftest_path=conftest_path,
                package_name="atavism_retry",
                module_name="client.py",
                timeout=10,
            )

            # Check that the secret was not leaked
            assert "SECRET_LEAKED" not in res.output
            assert res.output != ""


class TestCandidateTimeout:
    """Verify that long-running or hanging candidates are terminated safely."""

    def test_candidate_timeout_handled_gracefully(self) -> None:
        with tempfile.TemporaryDirectory(prefix="test_timeout_") as tmpdir:
            cand_file = Path(tmpdir) / "client.py"
            cand_file.write_text(
                "import time\n"
                "time.sleep(10)\n"
                "def send_with_retry(request, transport, policy, clock=None, sleep=None):\n"
                "    return transport(request)\n",
                encoding="utf-8",
            )

            types_path = T01_DIR / "variants" / "A" / "workspace" / "src" / "atavism_retry" / "types.py"
            conftest_path = T01_DIR / "private" / "tests" / "conftest.py"
            test_path = T01_DIR / "private" / "tests" / "common"

            res = grade_candidate(
                candidate_path=cand_file,
                types_path=types_path,
                test_dirs=[test_path],
                conftest_path=conftest_path,
                package_name="atavism_retry",
                module_name="client.py",
                timeout=1,
            )

            assert res.passed is False
            assert res.return_code == 124
            assert res.errors == 1
            assert "timed out after 1 seconds" in res.output
            assert "timeout" in res.failure_reasons
