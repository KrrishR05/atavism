"""Candidate execution backends and container security enforcement.

Provides execution backends for Atavism benchmark grading:
- TrustLevel: UNTRUSTED ("untrusted") vs TRUSTED_LOCAL ("trusted-local")
- ExecutionBackend: Base interface for executing tests in candidate workspaces
- TrustedLocalBackend: Subprocess-based execution with minimal environment allowlisting
- ContainerExecutionBackend: Hardened OCI/Docker container sandbox
- UntrustedExecutionUnavailableError: Raised when untrusted candidate execution fails closed
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Sequence


class TrustLevel(str, Enum):
    """Trust level required for candidate evaluation."""
    UNTRUSTED = "untrusted"
    TRUSTED_LOCAL = "trusted-local"


class UntrustedExecutionUnavailableError(RuntimeError):
    """Raised when untrusted execution fails closed because no secure sandbox is available."""
    pass


@dataclass(frozen=True)
class ExecutionResult:
    """Raw result of command execution in a backend."""
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class ExecutionBackend:
    """Abstract interface for benchmark execution backends."""

    def execute(
        self,
        command: Sequence[str],
        cwd: Path,
        env: dict[str, str],
        timeout: int,
    ) -> ExecutionResult:
        raise NotImplementedError


class TrustedLocalBackend(ExecutionBackend):
    """Host subprocess execution with environment scrubbing.

    CRITICAL SECURITY NOTICE:
    This backend executes candidate code directly on the host operating system with
    the permissions of the invoking user. It cleans environment variables but does NOT
    provide filesystem, network, or PID isolation. It is strictly intended for trusted
    internal development, reference solution verification, and mutation testing.
    It MUST NOT be used for untrusted, model-generated code.
    """

    def execute(
        self,
        command: Sequence[str],
        cwd: Path,
        env: dict[str, str],
        timeout: int,
    ) -> ExecutionResult:
        try:
            proc = subprocess.run(
                list(command),
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return ExecutionResult(
                return_code=proc.returncode,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecutionResult(
                return_code=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or f"Execution timed out after {timeout} seconds.",
                timed_out=True,
            )


@dataclass(frozen=True)
class ContainerSecurityConfig:
    """Hardened security configuration for OCI/Docker candidate execution."""
    image: str = "python:3.11-slim"
    network: str = "none"
    read_only_root: bool = True
    drop_capabilities: tuple[str, ...] = ("ALL",)
    no_new_privileges: bool = True
    user: str = "65534:65534"  # nobody:nogroup
    memory: str = "512m"
    cpus: str = "1.0"
    pids_limit: int = 64
    tmpfs_mounts: tuple[str, ...] = ("/tmp:rw,noexec,nosuid,size=64m",)


class ContainerExecutionBackend(ExecutionBackend):
    """Hardened OCI/Docker container sandbox for untrusted candidate execution.

    Enforces:
    - Network disabled (--network=none)
    - Read-only root filesystem (--read-only)
    - All capabilities dropped (--cap-drop=ALL)
    - No new privileges (--security-opt=no-new-privileges)
    - Non-root user (--user=65534:65534)
    - Memory limit (--memory=512m)
    - CPU limit (--cpus=1.0)
    - PID limit (--pids-limit=64)
    - Isolated writable workspace mounted explicitly
    - Read-only test definitions mounted explicitly
    """

    def __init__(
        self,
        config: ContainerSecurityConfig | None = None,
        docker_path: str | None = None,
    ) -> None:
        self.config = config or ContainerSecurityConfig()
        self._docker_path = docker_path or shutil.which("docker")

    def is_available(self) -> tuple[bool, str]:
        """Check if Docker is installed, running, and supports Linux containers."""
        if not self._docker_path:
            return False, "Docker CLI binary not found in system PATH"

        try:
            res = subprocess.run(
                [self._docker_path, "info", "--format", "{{.OSType}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode != 0:
                return False, f"Docker daemon unresponsive (exit code {res.returncode}): {res.stderr.strip()}"

            os_type = res.stdout.strip().lower()
            if os_type and os_type != "linux":
                return False, f"Docker daemon is running in '{os_type}' mode; Linux containers required for security flags"

            return True, "Docker container sandbox available with Linux isolation"
        except subprocess.TimeoutExpired:
            return False, "Docker info check timed out after 5 seconds"
        except Exception as exc:
            return False, f"Docker availability check failed: {exc}"

    def build_docker_command(
        self,
        command: Sequence[str],
        host_workspace: Path,
        container_workspace: str = "/workspace",
        test_dir: Path | None = None,
        container_tests: str = "/tests",
        env_vars: dict[str, str] | None = None,
    ) -> list[str]:
        """Build the hardened docker run command with all security flags."""
        cmd = [
            self._docker_path or "docker",
            "run",
            "--rm",
            f"--network={self.config.network}",
            f"--user={self.config.user}",
            f"--memory={self.config.memory}",
            f"--cpus={self.config.cpus}",
            f"--pids-limit={self.config.pids_limit}",
        ]

        if self.config.read_only_root:
            cmd.append("--read-only")

        if self.config.no_new_privileges:
            cmd.append("--security-opt=no-new-privileges")

        for cap in self.config.drop_capabilities:
            cmd.append(f"--cap-drop={cap}")

        for tmpfs in self.config.tmpfs_mounts:
            cmd.append(f"--tmpfs={tmpfs}")

        # Mount workspace: candidate work dir is writable
        cmd.extend(["--volume", f"{host_workspace.resolve()}:{container_workspace}:rw"])

        # Mount tests read-only if separate
        if test_dir:
            cmd.extend(["--volume", f"{test_dir.resolve()}:{container_tests}:ro"])

        cmd.extend(["--workdir", container_workspace])

        # Pass safe environment variables
        if env_vars:
            for k, v in env_vars.items():
                cmd.extend(["-e", f"{k}={v}"])

        cmd.append(self.config.image)
        cmd.extend(command)
        return cmd

    def execute(
        self,
        command: Sequence[str],
        cwd: Path,
        env: dict[str, str],
        timeout: int,
    ) -> ExecutionResult:
        avail, reason = self.is_available()
        if not avail:
            raise UntrustedExecutionUnavailableError(
                f"Untrusted candidate execution failed closed: {reason}. "
                "Host execution is not an OS sandbox and will not be used for untrusted code. "
                "To execute in trusted development mode, explicitly select trust_level='trusted-local'."
            )

        docker_cmd = self.build_docker_command(
            command=command,
            host_workspace=cwd,
            container_workspace="/workspace",
            env_vars=env,
        )

        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return ExecutionResult(
                return_code=proc.returncode,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecutionResult(
                return_code=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or f"Container execution timed out after {timeout} seconds.",
                timed_out=True,
            )

