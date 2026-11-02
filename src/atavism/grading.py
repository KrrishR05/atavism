"""Grading harness — runs pytest against a candidate implementation.

Provides utilities to grade a model's submission by replacing the
starter client.py with the candidate and running the hidden test suite.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class GradeResult:
    """Result of grading a candidate implementation."""
    passed: bool
    total_tests: int
    passed_tests: int
    failed_tests: int
    errors: int
    output: str
    return_code: int


def grade_candidate(
    candidate_path: Path,
    types_path: Path,
    test_dirs: list[Path],
    conftest_path: Path,
    *,
    timeout: int = 60,
) -> GradeResult:
    """Grade a candidate implementation against the hidden test suite.

    Args:
        candidate_path: Path to the candidate's client.py.
        types_path: Path to types.py (shared type definitions).
        test_dirs: Directories containing test files to run.
        conftest_path: Path to the shared conftest.py.
        timeout: Maximum seconds for pytest execution.

    Returns:
        GradeResult with pass/fail details.
    """
    with tempfile.TemporaryDirectory(prefix="atavism_grade_") as tmpdir:
        tmp = Path(tmpdir)

        # Set up package structure
        pkg_dir = tmp / "src" / "atavism_retry"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "__init__.py").write_text('"""Atavism retry client."""\n')
        shutil.copy2(types_path, pkg_dir / "types.py")
        shutil.copy2(candidate_path, pkg_dir / "client.py")

        # Copy test files
        test_dir = tmp / "tests"
        test_dir.mkdir()
        shutil.copy2(conftest_path, test_dir / "conftest.py")

        for td in test_dirs:
            if td.is_dir():
                for tf in td.glob("test_*.py"):
                    shutil.copy2(tf, test_dir / tf.name)
            elif td.is_file():
                shutil.copy2(td, test_dir / td.name)

        # Run pytest
        env_path = str(tmp / "src")
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                str(test_dir),
                "-v", "--tb=short", "-q",
                f"--rootdir={tmpdir}",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tmpdir,
            env={
                **dict(__import__("os").environ),
                "PYTHONPATH": f"{env_path}{__import__('os').pathsep}{str(test_dir)}",
            },
        )

        output = result.stdout + result.stderr

        # Parse results
        passed_tests = 0
        failed_tests = 0
        errors = 0
        total_tests = 0

        for line in output.splitlines():
            line_stripped = line.strip()
            # Look for summary line like "3 passed, 1 failed"
            if "passed" in line_stripped or "failed" in line_stripped or "error" in line_stripped:
                import re
                m_passed = re.search(r"(\d+) passed", line_stripped)
                m_failed = re.search(r"(\d+) failed", line_stripped)
                m_errors = re.search(r"(\d+) error", line_stripped)
                if m_passed or m_failed or m_errors:
                    if m_passed:
                        passed_tests = int(m_passed.group(1))
                    if m_failed:
                        failed_tests = int(m_failed.group(1))
                    if m_errors:
                        errors = int(m_errors.group(1))
                    total_tests = passed_tests + failed_tests + errors

        return GradeResult(
            passed=(result.returncode == 0),
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            errors=errors,
            output=output,
            return_code=result.returncode,
        )

