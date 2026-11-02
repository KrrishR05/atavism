"""Tests for T02 reference solution correctness.

Runs the hidden test suite against the reference solution to verify
it passes all contract requirements.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parent.parent / "benchmark" / "tasks" / "T02_pagination_authority"
PRIVATE = TASK_DIR / "private"
TYPES_PATH = TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_pagination" / "types.py"


def _run_tests_with_candidate(candidate_path: Path) -> tuple[int, str]:
    """Run pytest against a candidate client using subprocess to ensure isolation."""
    with tempfile.TemporaryDirectory(prefix="atavism_t02_ref_") as tmpdir:
        tmp = Path(tmpdir)

        # Set up package
        pkg_dir = tmp / "src" / "atavism_pagination"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "__init__.py").write_text('"""Atavism pagination client."""\n', encoding="utf-8")
        shutil.copy2(TYPES_PATH, pkg_dir / "types.py")
        shutil.copy2(candidate_path, pkg_dir / "client.py")

        # Copy test files
        test_dir = tmp / "tests"
        test_dir.mkdir()
        shutil.copy2(PRIVATE / "tests" / "conftest.py", test_dir / "conftest.py")
        shutil.copy2(PRIVATE / "tests" / "test_pagination.py", test_dir / "test_pagination.py")

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


class TestT02ReferenceSolution:
    """The reference implementation must pass the entire test suite."""

    def test_reference_solution_passes(self) -> None:
        ref_path = PRIVATE / "reference" / "solution.py"
        rc, output = _run_tests_with_candidate(ref_path)
        assert rc == 0, f"Reference solution failed test suite:\n{output}"

