"""Grading harness — metadata-driven candidate evaluation.

Provides utilities to grade a candidate implementation against task-specific
hidden test suites in an isolated temporary environment. Supports multiple
tasks and packages (e.g. atavism_retry, atavism_pagination) driven by task.json
metadata and provides diagnostic scoring across requirement categories.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

# Allowlist of environment variables permitted in candidate execution subprocesses
SAFE_SYSTEM_ENV_VARS: frozenset[str] = frozenset({
    # Windows core runtime
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "PATH",
    "PATHEXT",
    "TEMP",
    "TMP",
    "COMSPEC",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
    # POSIX core runtime
    "HOME",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    # Python runtime controls
    "PYTHONIOENCODING",
    "PYTHONUTF8",
    "PYTHONHASHSEED",
})

# Substrings identifying sensitive credentials to unconditionally exclude
SENSITIVE_ENV_PATTERNS: tuple[str, ...] = (
    "KEY",
    "TOKEN",
    "SECRET",
    "AUTH",
    "PASS",
    "CRED",
    "SSH",
    "AWS",
    "GITHUB",
    "OPENAI",
    "ANTHROPIC",
    "AZURE",
    "GEMINI",
)


def build_minimal_env(extra_pythonpath: list[str]) -> dict[str, str]:
    """Construct a minimal, scrubbed environment dictionary for candidate subprocesses.

    Ensures sensitive credentials, cloud tokens, API keys, and host secrets are excluded.
    Only allows explicitly safe operating system variables required for Python runtime execution.
    """
    clean_env: dict[str, str] = {}
    for key, val in os.environ.items():
        key_upper = key.upper()
        if key_upper in SAFE_SYSTEM_ENV_VARS:
            if not any(pattern in key_upper for pattern in SENSITIVE_ENV_PATTERNS):
                clean_env[key] = val

    clean_env["PYTHONPATH"] = os.pathsep.join(extra_pythonpath)
    clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
    clean_env["PYTHONIOENCODING"] = "utf-8"
    return clean_env


@dataclass(frozen=True)
class DiagnosticScore:
    """Diagnostic score for a specific category of test requirements."""
    category: str
    total: int
    passed: int
    failed: int
    score: float
    passed_all: bool


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
    diagnostics: dict[str, DiagnosticScore] = field(default_factory=dict)
    test_outcomes: dict[str, str] = field(default_factory=dict)
    failure_reasons: dict[str, str] = field(default_factory=dict)


def grade_candidate(
    candidate_path: Path,
    types_path: Path,
    test_dirs: list[Path],
    conftest_path: Path,
    *,
    package_name: str = "atavism_retry",
    module_name: str = "client.py",
    timeout: int = 60,
    diagnostic_categories: dict[str, list[str]] | None = None,
) -> GradeResult:
    """Grade a candidate implementation against the hidden test suite.

    Args:
        candidate_path: Path to the candidate's implementation file.
        types_path: Path to types.py (shared type definitions).
        test_dirs: Directories or files containing tests to run.
        conftest_path: Path to conftest.py.
        package_name: Target Python package name (e.g. 'atavism_retry').
        module_name: Module filename within the package (e.g. 'client.py').
        timeout: Maximum seconds for pytest execution.
        diagnostic_categories: Optional mapping of category names to identifier substrings.

    Returns:
        GradeResult with pass/fail details and category diagnostics.
    """
    candidate_path = Path(candidate_path).resolve()
    types_path = Path(types_path).resolve()
    conftest_path = Path(conftest_path).resolve()

    with tempfile.TemporaryDirectory(prefix="atavism_grade_") as tmpdir:
        tmp = Path(tmpdir)

        # Set up target package structure
        pkg_dir = tmp / "src" / package_name
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "__init__.py").write_text(
            f'"""Candidate package for {package_name}."""\n', encoding="utf-8"
        )
        shutil.copy2(types_path, pkg_dir / "types.py")
        shutil.copy2(candidate_path, pkg_dir / module_name)

        # Copy test files into tests/
        test_dir = tmp / "tests"
        test_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(conftest_path, test_dir / "conftest.py")

        for td in test_dirs:
            td = Path(td).resolve()
            if td.is_dir():
                for tf in td.glob("test_*.py"):
                    dest_name = (
                        f"{td.name}_{tf.name}"
                        if (test_dir / tf.name).exists()
                        else tf.name
                    )
                    shutil.copy2(tf, test_dir / dest_name)
            elif td.is_file():
                shutil.copy2(td, test_dir / td.name)

        junit_xml = tmp / "junit.xml"

        # Execute pytest in isolated subprocess with scrubbed minimal environment
        env_path = str(tmp / "src")
        clean_env = build_minimal_env([env_path, str(test_dir)])

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    str(test_dir),
                    "-v",
                    "--tb=short",
                    "-q",
                    f"--junitxml={junit_xml}",
                    f"--rootdir={tmpdir}",
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
                env=clean_env,
            )
        except subprocess.TimeoutExpired as exc:
            return GradeResult(
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                errors=1,
                output=f"Candidate execution timed out after {timeout} seconds.\n{exc.stdout or ''}\n{exc.stderr or ''}",
                return_code=124,
                failure_reasons={"timeout": f"Timed out after {timeout}s"},
            )

        output = result.stdout + result.stderr

        # Parse test outcomes from JUnit XML if generated
        test_outcomes: dict[str, str] = {}
        failure_reasons: dict[str, str] = {}
        passed_tests = 0
        failed_tests = 0
        errors = 0
        total_tests = 0

        if junit_xml.is_file():
            try:
                tree = ET.parse(junit_xml)
                root = tree.getroot()

                # Root might be <testsuites> or <testsuite>
                suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
                for suite in suites:
                    for tc in suite.findall("testcase"):
                        name = tc.attrib.get("name", "unknown")
                        classname = tc.attrib.get("classname", "")
                        test_key = f"{classname}::{name}"

                        failure = tc.find("failure")
                        error = tc.find("error")

                        if failure is not None:
                            outcome = "failed"
                            failed_tests += 1
                            msg = failure.attrib.get("message") or (failure.text or "")
                            failure_reasons[test_key] = msg.strip()
                        elif error is not None:
                            outcome = "error"
                            errors += 1
                            msg = error.attrib.get("message") or (error.text or "")
                            failure_reasons[test_key] = msg.strip()
                        else:
                            outcome = "passed"
                            passed_tests += 1

                        test_outcomes[test_key] = outcome

                total_tests = passed_tests + failed_tests + errors
            except Exception:
                pass

        # Fallback regex parsing of stdout if XML had no testcases
        if total_tests == 0:
            for line in output.splitlines():
                line_stripped = line.strip()
                if (
                    "passed" in line_stripped
                    or "failed" in line_stripped
                    or "error" in line_stripped
                ):
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

        # Compute diagnostic category scores
        diagnostics: dict[str, DiagnosticScore] = {}
        if diagnostic_categories:
            for cat, keywords in diagnostic_categories.items():
                cat_total = 0
                cat_passed = 0
                for test_key, outcome in test_outcomes.items():
                    # Match if any keyword appears in the test key
                    if any(kw.lower() in test_key.lower() for kw in keywords):
                        cat_total += 1
                        if outcome == "passed":
                            cat_passed += 1

                cat_failed = cat_total - cat_passed
                cat_score = (cat_passed / cat_total) if cat_total > 0 else 1.0
                cat_passed_all = (cat_total > 0) and (cat_passed == cat_total)
                diagnostics[cat] = DiagnosticScore(
                    category=cat,
                    total=cat_total,
                    passed=cat_passed,
                    failed=cat_failed,
                    score=cat_score,
                    passed_all=cat_passed_all,
                )

        # Overall pass requires 0 return code AND 0 failures/errors AND at least 1 test passed
        overall_passed = (result.returncode == 0) and (failed_tests == 0) and (errors == 0) and (passed_tests > 0)

        return GradeResult(
            passed=overall_passed,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            errors=errors,
            output=output,
            return_code=result.returncode,
            diagnostics=diagnostics,
            test_outcomes=test_outcomes,
            failure_reasons=failure_reasons,
        )


def grade_task_candidate(
    task_dir: Path,
    variant: str,
    candidate_path: Path,
    *,
    timeout: int = 60,
) -> GradeResult:
    """Grade a candidate implementation using task.json execution metadata.

    Args:
        task_dir: Directory containing task.json and variants.
        variant: Variant identifier ('A' or 'B').
        candidate_path: Path to the candidate solution file.
        timeout: Maximum seconds for test execution.

    Returns:
        GradeResult with comprehensive diagnostics.

    Raises:
        FileNotFoundError: If task directory, task.json, candidate file, types file,
                          conftest.py, or test paths do not exist.
        ValueError: If metadata structure, package name, variant, or test configuration
                    is missing, malformed, or attempts directory traversal.
    """
    task_dir = Path(task_dir).resolve()
    if not task_dir.is_dir():
        raise FileNotFoundError(f"Task directory not found: {task_dir}")

    task_json = task_dir / "task.json"
    if not task_json.is_file():
        raise FileNotFoundError(f"task.json not found in {task_dir}")

    try:
        with open(task_json, encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as exc:
        raise ValueError(f"Failed to parse {task_json}: {exc}") from exc

    if not isinstance(meta, dict):
        raise ValueError(f"Root of {task_json} must be a JSON object")

    exec_cfg = meta.get("execution")
    if not exec_cfg or not isinstance(exec_cfg, dict):
        raise ValueError(f"Task configuration in {task_json} is missing required 'execution' section")

    package_name = exec_cfg.get("package_name")
    if not package_name or not isinstance(package_name, str) or not package_name.isidentifier():
        raise ValueError(
            f"Invalid or missing 'package_name' in {task_json} execution config: {package_name!r}"
        )

    module_name = exec_cfg.get("module_name", "client.py")
    if not module_name or not isinstance(module_name, str) or not module_name.endswith(".py"):
        raise ValueError(
            f"Invalid or missing 'module_name' in {task_json} execution config: {module_name!r}"
        )

    types_rel = exec_cfg.get("types_file")
    if not types_rel or not isinstance(types_rel, str) or not types_rel.strip():
        raise ValueError(
            f"Invalid or missing 'types_file' in {task_json} execution config: {types_rel!r}"
        )

    variants_cfg = exec_cfg.get("variants")
    if not isinstance(variants_cfg, dict) or not variants_cfg:
        raise ValueError(f"Missing or empty 'variants' section under 'execution' in {task_json}")

    if variant not in variants_cfg:
        raise ValueError(f"Unknown variant '{variant}'. Expected one of: {list(variants_cfg.keys())}")

    var_cfg = variants_cfg[variant]
    if not isinstance(var_cfg, dict):
        raise ValueError(f"Configuration for variant '{variant}' must be a dictionary in {task_json}")

    test_rel = var_cfg.get("test_paths")
    if not isinstance(test_rel, list) or len(test_rel) == 0:
        raise ValueError(f"Variant '{variant}' has no test_paths configured in {task_json}")

    diag = var_cfg.get("diagnostic_categories")
    if diag is not None and not isinstance(diag, dict):
        raise ValueError(
            f"diagnostic_categories for variant '{variant}' must be a dictionary in {task_json}"
        )

    # Validate candidate path
    candidate_path = Path(candidate_path).resolve()
    if not candidate_path.is_file():
        raise FileNotFoundError(f"Candidate file not found: {candidate_path}")

    # Resolve and validate types path (prevent directory traversal outside task_dir)
    types_path = (task_dir / "variants" / variant / "workspace" / types_rel).resolve()
    if not types_path.is_file():
        types_path = (task_dir / "variants" / "A" / "workspace" / types_rel).resolve()
    try:
        types_path.relative_to(task_dir)
    except ValueError:
        raise ValueError(f"types_file '{types_rel}' resolves outside task directory: {types_path}")
    if not types_path.is_file():
        raise FileNotFoundError(f"Types file not found: {types_path}")

    # Resolve and validate test paths (prevent directory traversal outside task_dir)
    test_paths: list[Path] = []
    for p in test_rel:
        if not isinstance(p, str) or not p.strip():
            raise ValueError(f"Invalid test path entry {p!r} in variant '{variant}'")
        p_resolved = (task_dir / p).resolve()
        try:
            p_resolved.relative_to(task_dir)
        except ValueError:
            raise ValueError(f"Test path '{p}' resolves outside task directory: {p_resolved}")
        if not p_resolved.exists():
            raise FileNotFoundError(f"Configured test path does not exist: {p_resolved}")
        test_paths.append(p_resolved)

    conftest_path = (task_dir / "private" / "tests" / "conftest.py").resolve()
    if not conftest_path.is_file():
        raise FileNotFoundError(f"conftest.py not found in {task_dir / 'private' / 'tests'}")

    return grade_candidate(
        candidate_path=candidate_path,
        types_path=types_path,
        test_dirs=test_paths,
        conftest_path=conftest_path,
        package_name=package_name,
        module_name=module_name,
        timeout=timeout,
        diagnostic_categories=diag,
    )
