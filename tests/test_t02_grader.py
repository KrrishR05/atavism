"""Tests for T02 grader reliability — mutation testing using shared grading infrastructure.

Verifies that deliberately incorrect implementations (mutants)
are reliably rejected by the hidden test suite.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from atavism.grading import grade_candidate

TASK_DIR = Path(__file__).resolve().parent.parent / "benchmark" / "tasks" / "T02_pagination_authority"
PRIVATE = TASK_DIR / "private"
TYPES_PATH = TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_pagination" / "types.py"
CONFTEST_PATH = PRIVATE / "tests" / "conftest.py"
TEST_PAGINATION_PATH = PRIVATE / "tests" / "test_pagination.py"


def _create_mutant_client(mutant_func_name: str, tmp_dir: Path) -> Path:
    """Create a client.py that delegates collect_all_items to a mutant function."""
    mutants_path = PRIVATE / "mutants" / "__init__.py"
    mutant_code = mutants_path.read_text(encoding="utf-8")

    client_code = f"""{mutant_code}

def collect_all_items(
    fetch_page: PageFetcher,
    *,
    initial_cursor: str | None = None,
    max_pages: int = 100,
) -> list[str]:
    return {mutant_func_name}(fetch_page, initial_cursor=initial_cursor, max_pages=max_pages)
"""
    client_path = tmp_dir / "client.py"
    client_path.write_text(client_code, encoding="utf-8")
    return client_path


def _run_mutant_against_tests(mutant_func_name: str) -> tuple[int, str]:
    """Run a mutant through the grader test suite using shared grading interface."""
    with tempfile.TemporaryDirectory(prefix="atavism_t02_mutant_") as tmpdir:
        tmp = Path(tmpdir)
        client_path = _create_mutant_client(mutant_func_name, tmp)
        res = grade_candidate(
            candidate_path=client_path,
            types_path=TYPES_PATH,
            test_dirs=[TEST_PAGINATION_PATH],
            conftest_path=CONFTEST_PATH,
            package_name="atavism_pagination",
            module_name="client.py",
        )
        return res.return_code, res.output


class TestT02MutantsRejected:
    """Every mutant must be rejected by at least one test in the suite."""

    def test_mutant_cursor_driven_continuation_rejected(self) -> None:
        """Mutant following the legacy treatment comment must fail."""
        rc, output = _run_mutant_against_tests("mutant_cursor_driven_continuation")
        assert rc != 0, f"mutant_cursor_driven_continuation should have failed:\n{output}"

    def test_mutant_has_more_as_advisory_rejected(self) -> None:
        rc, output = _run_mutant_against_tests("mutant_has_more_as_advisory")
        assert rc != 0, f"mutant_has_more_as_advisory should have failed:\n{output}"

    def test_mutant_stop_when_missing_cursor_rejected(self) -> None:
        rc, output = _run_mutant_against_tests("mutant_stop_when_missing_cursor")
        assert rc != 0, f"mutant_stop_when_missing_cursor should have failed:\n{output}"

    def test_mutant_deduplicate_items_rejected(self) -> None:
        rc, output = _run_mutant_against_tests("mutant_deduplicate_items")
        assert rc != 0, f"mutant_deduplicate_items should have failed:\n{output}"

    def test_mutant_sort_items_rejected(self) -> None:
        rc, output = _run_mutant_against_tests("mutant_sort_items")
        assert rc != 0, f"mutant_sort_items should have failed:\n{output}"

    def test_mutant_strip_cursor_rejected(self) -> None:
        rc, output = _run_mutant_against_tests("mutant_strip_cursor")
        assert rc != 0, f"mutant_strip_cursor should have failed:\n{output}"

    def test_mutant_no_cycle_detection_rejected(self) -> None:
        rc, output = _run_mutant_against_tests("mutant_no_cycle_detection")
        assert rc != 0, f"mutant_no_cycle_detection should have failed:\n{output}"

    def test_mutant_silent_partial_on_limit_rejected(self) -> None:
        rc, output = _run_mutant_against_tests("mutant_silent_partial_on_limit")
        assert rc != 0, f"mutant_silent_partial_on_limit should have failed:\n{output}"

    def test_mutant_swallow_exceptions_rejected(self) -> None:
        rc, output = _run_mutant_against_tests("mutant_swallow_exceptions")
        assert rc != 0, f"mutant_swallow_exceptions should have failed:\n{output}"
