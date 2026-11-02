"""Tests for reference solution correctness.

Runs the hidden test suite against both reference implementations
to verify they pass their respective graders.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TASK_DIR = Path(__file__).resolve().parent.parent / "benchmark" / "tasks" / "T01_retry_semantics"
PRIVATE = TASK_DIR / "private"
TYPES_PATH = TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_retry" / "types.py"


def _load_reference(name: str):
    """Load a reference implementation module."""
    ref_path = PRIVATE / "reference" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"ref_{name}", ref_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_tests_with_candidate(candidate_path: Path, test_dirs: list[Path]) -> tuple[int, str]:
    """Run pytest against a candidate using subprocess to ensure isolation."""
    import subprocess
    import tempfile
    import shutil

    with tempfile.TemporaryDirectory(prefix="atavism_ref_test_") as tmpdir:
        tmp = Path(tmpdir)

        # Set up package
        pkg_dir = tmp / "src" / "atavism_retry"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "__init__.py").write_text('"""Atavism retry client."""\n')
        shutil.copy2(TYPES_PATH, pkg_dir / "types.py")
        shutil.copy2(candidate_path, pkg_dir / "client.py")

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


class TestReferenceSolutions:
    """Reference implementations must pass their graders."""

    def test_control_reference_passes_common_tests(self) -> None:
        rc, output = _run_tests_with_candidate(
            PRIVATE / "reference" / "control.py",
            [PRIVATE / "tests" / "common"],
        )
        assert rc == 0, f"Control reference failed common tests:\n{output}"

    def test_control_reference_passes_control_tests(self) -> None:
        rc, output = _run_tests_with_candidate(
            PRIVATE / "reference" / "control.py",
            [PRIVATE / "tests" / "control"],
        )
        assert rc == 0, f"Control reference failed control tests:\n{output}"

    def test_treatment_reference_passes_common_tests(self) -> None:
        rc, output = _run_tests_with_candidate(
            PRIVATE / "reference" / "treatment.py",
            [PRIVATE / "tests" / "common"],
        )
        assert rc == 0, f"Treatment reference failed common tests:\n{output}"

    def test_treatment_reference_passes_treatment_tests(self) -> None:
        rc, output = _run_tests_with_candidate(
            PRIVATE / "reference" / "treatment.py",
            [PRIVATE / "tests" / "treatment"],
        )
        assert rc == 0, f"Treatment reference failed treatment tests:\n{output}"

    def test_control_reference_fails_treatment_tests(self) -> None:
        """Control reference should FAIL treatment-specific tests
        (because it doesn't retry 409 LEASE_BUSY)."""
        rc, output = _run_tests_with_candidate(
            PRIVATE / "reference" / "control.py",
            [PRIVATE / "tests" / "treatment"],
        )
        assert rc != 0, f"Control reference should fail treatment tests but passed:\n{output}"

    def test_treatment_reference_fails_control_tests(self) -> None:
        """Treatment reference should FAIL control-specific tests
        (because it retries 409 LEASE_BUSY, which control says not to)."""
        rc, output = _run_tests_with_candidate(
            PRIVATE / "reference" / "treatment.py",
            [PRIVATE / "tests" / "control"],
        )
        assert rc != 0, f"Treatment reference should fail control tests but passed:\n{output}"

