# Atavism — Research Protocol

## Overview

This document describes the experimental protocol for running Atavism benchmark evaluations.

## Trial Procedure

### 1. Task Selection

Select a benchmark task (e.g., T01) and specify which variant(s) to evaluate (A, B, or both).

### 2. Workspace Preparation

For each trial:

1. Export a clean model workspace using the workspace isolation utility.
2. Verify that the exported workspace contains only permitted files (task instructions, contract, starter code).
3. Confirm that no reference solutions, grader code, or test files are included.

### 3. Model Invocation

Present the model with:

- The task description (`TASK.md`).
- The provider contract (`contract.md`).
- The starter code files.

Record:

- Model name and exact version/checkpoint.
- Temperature setting, system prompt, and any other configuration.
- Timestamp and trial number.
- The complete model transcript.

### 4. Grading

1. Extract the model's implementation from its output.
2. Place the implementation in the grading harness.
3. Run the grader (pytest with the hidden test suite).
4. Record pass/fail results per test, overall outcome, and any error details.

### 5. Data Recording

For each trial, record all fields specified in the evaluation methodology:

- Task identifier and variant.
- Model name and version.
- Model settings.
- Trial number.
- Environment and dependency versions.
- Execution duration.
- Approximate cost (when available).
- Candidate output file location.
- Grader outcome (pass/fail per test, overall).
- Failure details and diagnostic category.
- Transcript file location.

## Analysis

### Per-Task Metrics

- Raw pass count per variant.
- Pass rate per variant.
- pass@k (probability that at least one of k samples passes).
- pass^k (probability that all k samples pass).

### Diagnostic Metrics

- `common_mechanics`: Score isolating generic requirement adherence (e.g. backoff calculation, header parsing, pagination ordering, limits).
- `pure_convention`: Pure classification of the central experimental variable in isolation from composite mechanics (e.g. whether 409 LEASE_BUSY is classified as retryable or non-retryable on GET).
- `compound_interactions`: Evaluation of the experimental variable combined with complex interactions (e.g. 409 LEASE_BUSY combined with exponential backoff progression, Retry-After delay headers, and HTTP idempotency rules).
- `contract_compliance`: Strict overall qualification requiring 100% adherence to all clauses (0 failures, 0 errors, returncode 0).

### Known Methodological Limitations

#### The Stub-Overwrite Confounder in T02
In code-completion and edit tasks involving conflicting implementation guidance (T02), models frequently overwrite function bodies or omit existing comments wholesale.
- Passing Variant B indicates that the model's output satisfies the authoritative API contract despite the conflicting legacy comment.
- **Researchers must not claim that passing Variant B proves conscious or deliberate cognitive conflict arbitration.** The model may simply have ignored the comment or rewritten the file from prompt context alone.
- The meaningful evaluation metric is the **cross-variant delta** ($\text{PassRate}_A - \text{PassRate}_B$). A performance penalty on Variant B provides empirical evidence that conflicting comments induce contract regression.

## Security Limitations & Candidate Isolation

### Subprocess Execution Boundaries

The default test runner executes candidate code using local `subprocess.run([sys.executable, "-m", "pytest", ...])` within an isolated temporary directory with environment scrubbing. While this prevents host environment credential inheritance and isolates file imports, **subprocess execution alone does not provide OS-level kernel isolation, network isolation, or filesystem confinement**.

For full container execution architecture, security boundaries, and Docker/Podman deployment specifications, refer to [Security Architecture & Container Execution Design](security_and_container_design.md).

### Required Isolation for Untrusted Candidates

When evaluating external or untrusted AI models whose candidate implementations may contain arbitrary Python code:

1. **Container Isolation:** Execute candidate grading inside an ephemeral container (e.g., Docker/Podman or gVisor) with root filesystems mounted read-only and no network access (`--network=none`).
2. **Resource Constraints:** Apply strict cgroup resource limits on memory (e.g., 512MB), CPU shares, and execution timeout (default 60s).
3. **Restricted Privileges:** Run the test process under an unprivileged user (`nobody:nogroup`, `cap-drop=ALL`) without write access outside the scratch temporary directory.

## Reproducibility

- Pin all dependency versions.
- Record the exact Python version used.
- Provide complete setup and execution instructions in the README.
- Archive model transcripts alongside results.
