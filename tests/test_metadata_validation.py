"""Unit tests for task metadata validation and security checks in grading harness."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from atavism.grading import grade_task_candidate

ROOT = Path(__file__).resolve().parent.parent
T01_DIR = ROOT / "benchmark" / "tasks" / "T01_retry_semantics"
CAND_FILE = T01_DIR / "private" / "reference" / "control.py"


class TestMetadataValidation:
    """Verify that grade_task_candidate raises descriptive exceptions on invalid task metadata."""

    def test_missing_task_directory_raises(self) -> None:
        non_existent = ROOT / "benchmark" / "tasks" / "T99_missing"
        with pytest.raises(FileNotFoundError, match="Task directory not found"):
            grade_task_candidate(non_existent, "A", CAND_FILE)

    def test_missing_task_json_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError, match="task.json not found"):
                grade_task_candidate(Path(tmpdir), "A", CAND_FILE)

    def test_malformed_json_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "task.json").write_text("{invalid json", encoding="utf-8")
            with pytest.raises(ValueError, match="Failed to parse"):
                grade_task_candidate(p, "A", CAND_FILE)

    def test_non_dict_root_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "task.json").write_text("[]", encoding="utf-8")
            with pytest.raises(ValueError, match="must be a JSON object"):
                grade_task_candidate(p, "A", CAND_FILE)

    def test_missing_execution_section_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "task.json").write_text('{"id": "T99"}', encoding="utf-8")
            with pytest.raises(ValueError, match="missing required 'execution' section"):
                grade_task_candidate(p, "A", CAND_FILE)

    def test_invalid_package_name_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            meta = {
                "id": "T99",
                "execution": {
                    "package_name": "invalid-package-hyphen",
                    "types_file": "types.py",
                    "variants": {"A": {"test_paths": ["test.py"]}},
                },
            }
            (p / "task.json").write_text(json.dumps(meta), encoding="utf-8")
            with pytest.raises(ValueError, match="Invalid or missing 'package_name'"):
                grade_task_candidate(p, "A", CAND_FILE)

    def test_invalid_module_name_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            meta = {
                "id": "T99",
                "execution": {
                    "package_name": "valid_pkg",
                    "module_name": "not_python.txt",
                    "types_file": "types.py",
                    "variants": {"A": {"test_paths": ["test.py"]}},
                },
            }
            (p / "task.json").write_text(json.dumps(meta), encoding="utf-8")
            with pytest.raises(ValueError, match="Invalid or missing 'module_name'"):
                grade_task_candidate(p, "A", CAND_FILE)

    def test_unknown_variant_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown variant 'C'. Expected one of:"):
            grade_task_candidate(T01_DIR, "C", CAND_FILE)

    def test_missing_test_paths_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            meta = {
                "id": "T99",
                "execution": {
                    "package_name": "valid_pkg",
                    "types_file": "types.py",
                    "variants": {"A": {"test_paths": []}},
                },
            }
            (p / "task.json").write_text(json.dumps(meta), encoding="utf-8")
            with pytest.raises(ValueError, match="has no test_paths configured"):
                grade_task_candidate(p, "A", CAND_FILE)

    def test_missing_candidate_file_raises(self) -> None:
        non_existent_cand = Path("/fake/non_existent_client.py")
        with pytest.raises(FileNotFoundError, match="Candidate file not found"):
            grade_task_candidate(T01_DIR, "A", non_existent_cand)

    def test_nonexistent_test_path_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            # Create dummy workspace types
            types_file = p / "variants" / "A" / "workspace" / "types.py"
            types_file.parent.mkdir(parents=True, exist_ok=True)
            types_file.write_text("# types", encoding="utf-8")

            meta = {
                "id": "T99",
                "execution": {
                    "package_name": "valid_pkg",
                    "types_file": "types.py",
                    "variants": {"A": {"test_paths": ["nonexistent_tests"]}},
                },
            }
            (p / "task.json").write_text(json.dumps(meta), encoding="utf-8")
            with pytest.raises(FileNotFoundError, match="Configured test path does not exist"):
                grade_task_candidate(p, "A", CAND_FILE)

    def test_test_path_traversal_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            types_file = p / "variants" / "A" / "workspace" / "types.py"
            types_file.parent.mkdir(parents=True, exist_ok=True)
            types_file.write_text("# types", encoding="utf-8")

            meta = {
                "id": "T99",
                "execution": {
                    "package_name": "valid_pkg",
                    "types_file": "types.py",
                    "variants": {"A": {"test_paths": ["../../etc/passwd"]}},
                },
            }
            (p / "task.json").write_text(json.dumps(meta), encoding="utf-8")
            with pytest.raises(ValueError, match="resolves outside task directory"):
                grade_task_candidate(p, "A", CAND_FILE)

    def test_types_file_traversal_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            meta = {
                "id": "T99",
                "execution": {
                    "package_name": "valid_pkg",
                    "types_file": "../../../../outside_types.py",
                    "variants": {"A": {"test_paths": ["private/tests"]}},
                },
            }
            (p / "task.json").write_text(json.dumps(meta), encoding="utf-8")
            with pytest.raises(ValueError, match="resolves outside task directory"):
                grade_task_candidate(p, "A", CAND_FILE)
