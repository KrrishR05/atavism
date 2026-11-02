"""Tests for grader reliability — mutation testing.

Verifies that deliberately incorrect implementations (mutants)
are rejected by the grader's test suite.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

TASK_DIR = Path(__file__).resolve().parent.parent / "benchmark" / "tasks" / "T01_retry_semantics"
PRIVATE = TASK_DIR / "private"
TYPES_PATH = TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_retry" / "types.py"


def _create_mutant_client(mutant_func_name: str, tmp_dir: Path) -> Path:
    """Create a client.py that delegates send_with_retry to a mutant function."""
    mutants_path = PRIVATE / "mutants" / "__init__.py"
    mutant_code = mutants_path.read_text(encoding="utf-8")

    # Create a client.py that appends the target send_with_retry wrapper
    client_code = f"""{mutant_code}

def send_with_retry(
    request: Request,
    transport: Transport,
    policy: RetryPolicy,
    *,
    clock: Clock,
    sleep: Sleeper,
) -> Response:
    return {mutant_func_name}(request, transport, policy, clock=clock, sleep=sleep)
"""
    client_path = tmp_dir / "client.py"
    client_path.write_text(client_code, encoding="utf-8")
    return client_path


def _run_mutant_against_tests(
    mutant_func_name: str,
    test_dirs: list[Path],
) -> tuple[int, str]:
    """Run a mutant against specified test directories."""
    with tempfile.TemporaryDirectory(prefix="atavism_mutant_") as tmpdir:
        tmp = Path(tmpdir)

        # Create mutant client
        client_path = _create_mutant_client(mutant_func_name, tmp)

        # Set up package
        pkg_dir = tmp / "src" / "atavism_retry"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "__init__.py").write_text('"""Atavism retry client."""\n')
        shutil.copy2(TYPES_PATH, pkg_dir / "types.py")
        shutil.copy2(client_path, pkg_dir / "client.py")

        # Copy test files
        test_dir = tmp / "tests"
        test_dir.mkdir()
        shutil.copy2(PRIVATE / "tests" / "conftest.py", test_dir / "conftest.py")

        for td in test_dirs:
            if td.is_dir():
                for tf in td.glob("test_*.py"):
                    shutil.copy2(tf, test_dir / tf.name)

        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_dir), "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=tmpdir,
            env={
                **dict(__import__("os").environ),
                "PYTHONPATH": f"{tmp / 'src'}{__import__('os').pathsep}{test_dir}",
            },
        )
        return result.returncode, result.stdout + result.stderr


class TestMutantsRejected:
    """Every mutant must be caught by at least one test."""

    def test_mutant_retry_all_errors_fails_common(self) -> None:
        """Retrying all 4xx/5xx should fail non-retryable tests."""
        rc, output = _run_mutant_against_tests(
            "mutant_retry_all_errors",
            [PRIVATE / "tests" / "common"],
        )
        assert rc != 0, f"mutant_retry_all_errors should fail:\n{output}"

    def test_mutant_ignore_error_code_fails_common(self) -> None:
        """Ignoring error codes should fail when wrong code used with retryable status."""
        rc, output = _run_mutant_against_tests(
            "mutant_ignore_error_code",
            [PRIVATE / "tests" / "common"],
        )
        assert rc != 0, f"mutant_ignore_error_code should fail:\n{output}"

    def test_mutant_off_by_one_attempts_fails_common(self) -> None:
        """Wrong attempt counting should fail attempt-counting tests."""
        rc, output = _run_mutant_against_tests(
            "mutant_off_by_one_attempts",
            [PRIVATE / "tests" / "common"],
        )
        assert rc != 0, f"mutant_off_by_one_attempts should fail:\n{output}"

    def test_mutant_ignore_retry_after_fails_common(self) -> None:
        """Ignoring Retry-After should fail Retry-After tests."""
        rc, output = _run_mutant_against_tests(
            "mutant_ignore_retry_after",
            [PRIVATE / "tests" / "common"],
        )
        assert rc != 0, f"mutant_ignore_retry_after should fail:\n{output}"

    def test_mutant_wrong_backoff_fails_common(self) -> None:
        """Wrong backoff formula should fail backoff tests."""
        rc, output = _run_mutant_against_tests(
            "mutant_wrong_backoff",
            [PRIVATE / "tests" / "common"],
        )
        assert rc != 0, f"mutant_wrong_backoff should fail:\n{output}"

    def test_mutant_no_idempotency_check_fails_common(self) -> None:
        """Missing idempotency check should fail idempotency tests."""
        rc, output = _run_mutant_against_tests(
            "mutant_no_idempotency_check",
            [PRIVATE / "tests" / "common"],
        )
        assert rc != 0, f"mutant_no_idempotency_check should fail:\n{output}"

    def test_mutant_ignore_deadline_fails_common(self) -> None:
        """Ignoring deadline should fail deadline tests."""
        rc, output = _run_mutant_against_tests(
            "mutant_ignore_deadline",
            [PRIVATE / "tests" / "common"],
        )
        assert rc != 0, f"mutant_ignore_deadline should fail:\n{output}"

    def test_mutant_swallow_exceptions_fails_common(self) -> None:
        """Swallowing exceptions should fail exception-propagation tests."""
        rc, output = _run_mutant_against_tests(
            "mutant_swallow_exceptions",
            [PRIVATE / "tests" / "common"],
        )
        assert rc != 0, f"mutant_swallow_exceptions should fail:\n{output}"

    def test_mutant_treatment_as_control_fails_treatment(self) -> None:
        """Using control behavior in treatment context should fail treatment tests."""
        rc, output = _run_mutant_against_tests(
            "mutant_treatment_as_control",
            [PRIVATE / "tests" / "treatment"],
        )
        assert rc != 0, f"mutant_treatment_as_control should fail treatment tests:\n{output}"

    def test_mutant_treatment_as_control_passes_control(self) -> None:
        """Using control behavior should pass control-specific tests (it IS the control)."""
        rc, output = _run_mutant_against_tests(
            "mutant_treatment_as_control",
            [PRIVATE / "tests" / "control"],
        )
        assert rc == 0, f"mutant_treatment_as_control should pass control tests:\n{output}"
