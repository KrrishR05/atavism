"""Tests for candidate execution backends, container security flags, and fail-closed isolation."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from atavism.cli import main as cli_main
from atavism.execution import (
    ContainerExecutionBackend,
    ContainerSecurityConfig,
    ExecutionResult,
    TrustLevel,
    TrustedLocalBackend,
    UntrustedExecutionUnavailableError,
)
from atavism.grading import (
    SAFE_SYSTEM_ENV_VARS,
    SENSITIVE_ENV_PATTERNS,
    build_minimal_env,
    grade_candidate,
    grade_task_candidate,
)

ROOT = Path(__file__).resolve().parent.parent
T01_DIR = ROOT / "benchmark" / "tasks" / "T01_retry_semantics"
T01_TYPES = T01_DIR / "variants" / "A" / "workspace" / "src" / "atavism_retry" / "types.py"
T01_CONFTEST = T01_DIR / "private" / "tests" / "conftest.py"
T01_COMMON = T01_DIR / "private" / "tests" / "common"
T01_REF_CONTROL = T01_DIR / "private" / "reference" / "control.py"


class TestContainerSecurityFlags:
    """Verify that ContainerExecutionBackend strictly configures all OCI/Docker security flags."""

    def test_default_container_security_config(self) -> None:
        cfg = ContainerSecurityConfig()
        assert cfg.image == "python:3.11-slim"
        assert cfg.network == "none"
        assert cfg.read_only_root is True
        assert cfg.drop_capabilities == ("ALL",)
        assert cfg.no_new_privileges is True
        assert cfg.user == "65534:65534"
        assert cfg.memory == "512m"
        assert cfg.cpus == "1.0"
        assert cfg.pids_limit == 64
        assert "/tmp:rw,noexec,nosuid,size=64m" in cfg.tmpfs_mounts

    def test_build_docker_command_includes_all_isolation_flags(self) -> None:
        backend = ContainerExecutionBackend(docker_path="docker")
        workspace = Path("/mock/host/workspace")
        tests = Path("/mock/host/tests")
        cmd = backend.build_docker_command(
            command=["python", "-m", "pytest"],
            host_workspace=workspace,
            container_workspace="/workspace",
            test_dir=tests,
            container_tests="/tests",
            env_vars={"PYTHONPATH": "/workspace/src"},
        )

        cmd_str = " ".join(cmd)
        # Network disabled
        assert "--network=none" in cmd
        # Non-root execution
        assert "--user=65534:65534" in cmd
        # Read-only container root
        assert "--read-only" in cmd
        # Drop all capabilities
        assert "--cap-drop=ALL" in cmd
        # Prevent privilege escalation
        assert "--security-opt=no-new-privileges" in cmd
        # Resource limits
        assert "--memory=512m" in cmd
        assert "--cpus=1.0" in cmd
        assert "--pids-limit=64" in cmd
        # Ephemeral tempfs
        assert "--tmpfs=/tmp:rw,noexec,nosuid,size=64m" in cmd
        # Cleanup on exit
        assert "--rm" in cmd
        # Volume containment
        assert f"--volume {workspace.resolve()}:/workspace:rw" in cmd_str
        assert f"--volume {tests.resolve()}:/tests:ro" in cmd_str
        # Safe environment
        assert "-e PYTHONPATH=/workspace/src" in cmd_str
        # Image and entrypoint
        assert "python:3.11-slim" in cmd
        assert cmd[-3:] == ["python", "-m", "pytest"]


class TestBackendAvailabilityAndFailClosed:
    """Verify backend availability detection and fail-closed behavior for untrusted execution."""

    def test_is_available_returns_false_when_docker_missing(self) -> None:
        backend = ContainerExecutionBackend(docker_path=None)
        # Clear path detection
        backend._docker_path = None
        avail, reason = backend.is_available()
        assert avail is False
        assert "not found in system PATH" in reason

    def test_is_available_rejects_non_linux_containers(self) -> None:
        backend = ContainerExecutionBackend(docker_path="docker")
        mock_proc = MagicMock(returncode=0, stdout="windows\n", stderr="")
        with patch("subprocess.run", return_value=mock_proc):
            avail, reason = backend.is_available()
            assert avail is False
            assert "Linux containers required" in reason

    def test_untrusted_execute_fails_closed_when_docker_unavailable(self) -> None:
        backend = ContainerExecutionBackend(docker_path=None)
        backend._docker_path = None
        with pytest.raises(UntrustedExecutionUnavailableError) as exc_info:
            backend.execute(["echo", "hi"], cwd=Path("."), env={}, timeout=5)
        assert "Untrusted candidate execution failed closed" in str(exc_info.value)
        assert "Host execution is not an OS sandbox" in str(exc_info.value)

    def test_untrusted_execute_fails_closed_on_container_runtime_launch_error(self) -> None:
        backend = ContainerExecutionBackend(docker_path="docker")
        mock_proc = MagicMock(
            returncode=127,
            stdout="",
            stderr="docker: Error response from daemon: OCI runtime create failed",
        )
        with patch.object(backend, "is_available", return_value=(True, "ok")):
            with patch("subprocess.run", return_value=mock_proc):
                with pytest.raises(UntrustedExecutionUnavailableError) as exc_info:
                    backend.execute(["python", "-m", "pytest"], cwd=Path("."), env={}, timeout=5)
        assert "Container sandbox execution unavailable" in str(exc_info.value)

    def test_grade_candidate_untrusted_returns_security_error_when_container_unavailable(self) -> None:
        res = grade_candidate(
            candidate_path=T01_REF_CONTROL,
            types_path=T01_TYPES,
            test_dirs=[T01_COMMON],
            conftest_path=T01_CONFTEST,
            package_name="atavism_retry",
            module_name="client.py",
            trust_level="untrusted",
        )
        assert res.passed is False
        assert res.return_code == 126
        assert res.errors == 1
        assert "security" in res.failure_reasons
        assert "SECURITY ERROR: Untrusted candidate execution failed closed" in res.output

    def test_grade_task_candidate_untrusted_returns_security_error(self) -> None:
        res = grade_task_candidate(
            task_dir=T01_DIR,
            variant="A",
            candidate_path=T01_REF_CONTROL,
            trust_level="untrusted",
        )
        assert res.passed is False
        assert res.return_code == 126
        assert "security" in res.failure_reasons


class TestTrustedLocalBackendValidation:
    """Verify TrustedLocalBackend requires explicit opt-in and operates safely in trusted mode."""

    def test_trusted_local_grades_reference_successfully(self) -> None:
        res = grade_task_candidate(
            task_dir=T01_DIR,
            variant="A",
            candidate_path=T01_REF_CONTROL,
            trust_level="trusted-local",
        )
        assert res.passed is True
        assert res.return_code == 0
        assert res.passed_tests > 0

    def test_invalid_trust_level_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid trust_level"):
            grade_task_candidate(
                task_dir=T01_DIR,
                variant="A",
                candidate_path=T01_REF_CONTROL,
                trust_level="arbitrary_mode",
            )

    def test_missing_or_invalid_package_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid package_name"):
            grade_candidate(
                candidate_path=T01_REF_CONTROL,
                types_path=T01_TYPES,
                test_dirs=[T01_COMMON],
                conftest_path=T01_CONFTEST,
                package_name="",
                module_name="client.py",
                trust_level="trusted-local",
            )

    def test_missing_or_invalid_module_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid module_name"):
            grade_candidate(
                candidate_path=T01_REF_CONTROL,
                types_path=T01_TYPES,
                test_dirs=[T01_COMMON],
                conftest_path=T01_CONFTEST,
                package_name="atavism_retry",
                module_name="client.txt",
                trust_level="trusted-local",
            )

    def test_grade_candidate_uses_portable_python_command(self) -> None:
        backend = MagicMock()
        backend.execute.return_value = ExecutionResult(return_code=0, stdout="", stderr="", timed_out=False)

        grade_candidate(
            candidate_path=T01_REF_CONTROL,
            types_path=T01_TYPES,
            test_dirs=[T01_COMMON],
            conftest_path=T01_CONFTEST,
            package_name="atavism_retry",
            module_name="client.py",
            trust_level="trusted-local",
            backend=backend,
        )

        command = backend.execute.call_args.args[0]
        assert command[:3] == ["python", "-m", "pytest"]


class TestCliTrustLevelIntegration:
    """Verify that CLI defaults to fail-closed untrusted execution."""

    def test_cli_grade_defaults_to_untrusted_and_fails_closed(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = cli_main([
            "grade",
            str(T01_DIR),
            "A",
            str(T01_REF_CONTROL),
        ])
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "FAILED" in captured.out
        assert "security" in captured.out or "SECURITY ERROR" in captured.out

    def test_cli_grade_passes_with_explicit_trusted_local(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = cli_main([
            "grade",
            str(T01_DIR),
            "A",
            str(T01_REF_CONTROL),
            "--trust-level",
            "trusted-local",
        ])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "PASSED" in captured.out
