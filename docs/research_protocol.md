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

### Cross-Variant Comparison

- Control vs. treatment pass-rate delta.
- Diagnostic failure categories (e.g., "used conventional 409 behavior," "ignored error code").

### Reporting Standards

- Report actual trial counts and results.
- Do not fabricate data or extrapolate from insufficient evidence.
- Document all limitations.
- Include representative failure transcripts with analysis.

## Reproducibility

- Pin all dependency versions.
- Record the exact Python version used.
- Provide complete setup and execution instructions in the README.
- Archive model transcripts alongside results.
