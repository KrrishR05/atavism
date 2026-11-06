# Atavism — Formal Model Evaluation Protocol

**Document Version:** 1.0.0  
**Status:** Pre-Trial Protocol Specification (No model trials have been conducted)  
**Task Scope:** T01 (Retry Semantics), T02 (Pagination Authority), T03 (Tenant Idempotency)

---

## 1. Experimental Objectives

The Atavism evaluation protocol is designed to measure **Contract Intelligence and Specification Adherence** in frontier Large Language Models for software engineering.

The primary experimental variable across all tasks is the **matched-pair delta**:
$$\Delta = \text{PassRate}(\text{Variant B}) - \text{PassRate}(\text{Variant A})$$

- **Variant A (Control):** Establishes baseline code synthesis capability under conventional semantics or consistent inline guidance.
- **Variant B (Treatment):** Tests contract adherence when requirements depart from common convention (T01), conflict with legacy starter code comments (T02), or require multi-clause semantic composition (T03).

---

## 2. Experimental Controls & Configuration

To ensure experimental reproducibility, every evaluation trial must record and enforce the following parameter matrix:

### 2.1 Model Specifications
- **Model Identifier:** Fully qualified provider and model name (e.g., `openai/gpt-4o-2024-08-06`, `anthropic/claude-3-5-sonnet-20241022`, `google/gemini-1.5-pro-002`).
- **Snapshot/Checkpoint:** Exact immutable snapshot timestamp where provided by API; no floating aliases (e.g. avoid unpinned `gpt-4o` or `claude-3-5-sonnet`).
- **Generation Parameters:**
  - `temperature`: Fixed at `0.0` (greedy decoding for maximal determinism) or `0.2` for sampling distributions across pilot trials.
  - `top_p`: `1.0` (when temperature is non-zero).
  - `max_tokens`: Fixed budget (default: 4,096 tokens).
  - `stop_sequences`: Standard EOF / markdown fence delimiters.

### 2.2 Tooling and Permissions
- **Zero-Shot File Replacement:** By default, candidates operate in zero-shot whole-file completion mode.
- **Tool Access:** Disabled by default during baseline evaluation. If agentic tool access (e.g. file reading or terminal execution) is evaluated in exploratory tracks, all tool calls, outputs, and intermediate states must be captured in the execution transcript.

### 2.3 Prompt Format & Environment
- **Context Construction:**
  - Candidate receives *only* the contents of the exported workspace (`TASK.md`, `contract.md`, and starter package files).
  - No hidden tests, no grader code, no reference solutions, and no mutation fixtures may ever be present in the model prompt or accessible environment.
- **System Prompt:** Standardized neutral evaluation system prompt:
  ```text
  You are an expert software engineer. Implement the required module adhering strictly
  to the provided technical specifications and contract document. Output only the complete
  source code for the target implementation file.
  ```

---

## 3. Trial Independence & Workspace Isolation

To prevent experimental contamination across trials and variants:

1. **Fresh Session:** Every single trial must execute in an isolated API context. No conversation history, system prompt cache, or memory from prior trials may carry over.
2. **Fresh Candidate Workspace:** Each trial begins from a cleanly exported workspace generated via `atavism export`.
3. **Balanced Execution Ordering:** To eliminate order effects, A/B variants must be evaluated in alternating or randomized order (e.g., A1, B1, B2, A2, A3, B3).
4. **Environment Invariance:** Variant A and Variant B must execute under identical hardware, Python interpreter versions, and dependency trees.

---

## 4. Trial Counts & Statistical Inference

### 4.1 Exploratory Pilot Track
- **Sample Size:** 3 to 5 independent trials per variant ($N = 3\text{--}5$ per cell).
- **Purpose:** Diagnostic screening of baseline adherence, syntax failure rates, and gross convention divergence.
- **Statistical Notice:**
  > [!WARNING]
  > An exploratory pilot ($N = 3\text{--}5$) is **insufficient for strong statistical significance claims**. Pilot results must be reported as raw sample outcomes and preliminary effect sizes without claiming definitive population generalizations.

### 4.2 Benchmark Scaling Track (Post-Pilot)
- **Sample Size:** $N \ge 30$ independent trials per variant per model for hypothesis testing.
- **Statistical Tests:**
  - McNemar's test for paired binary outcomes.
  - Fisher's Exact test for independent proportion comparisons.
  - 95% Clopper-Pearson confidence intervals for per-variant pass rates.

---

## 5. Metric Definitions

Results must report raw pass counts and explicit denominators before aggregating:

### 5.1 Pass Rate
$$\text{PassRate} = \frac{\text{Number of Passed Trials}}{\text{Total Trials Evaluated } (N)}$$

### 5.2 pass@k
The probability that at least one of $k$ generated candidates passes the hidden grader:
$$\text{pass@k} = 1 - \frac{\binom{N - c}{k}}{\binom{N}{k}}$$
where $N$ is total trials evaluated, $c$ is the number of passing trials, and $k \le N$.

### 5.3 pass^k
The probability that all $k$ candidates pass the hidden grader (measure of strict consistency):
$$\text{pass}^k = \frac{\binom{c}{k}}{\binom{N}{k}}$$

### 5.4 Diagnostic Attribution Scores
In addition to binary pass/fail, trials report category diagnostic scores:
- `common_mechanics`: Baseline specification adherence.
- `pure_convention`: Adherence to the core convention divergence.
- `cross_tenant_key_scope`: Scope adherence under interacting requirements.

---

## 6. Recorded Evidence & Provenance Schema

For every trial, a structured JSON record (`results/<trial_id>.json`) must record:

```json
{
  "trial_id": "T01-B-gpt4o-trial01-20261106-120000",
  "timestamp": "2026-11-06T12:00:00Z",
  "task_id": "T01_retry_semantics",
  "variant": "B",
  "benchmark_commit": "ec856a0241f24a95dfa66737dd281426b86e329e",
  "grader_version": "0.1.0",
  "execution_backend": "container_docker",
  "trust_level": "untrusted",
  "model": {
    "provider": "openai",
    "name": "gpt-4o-2024-08-06",
    "temperature": 0.0,
    "max_tokens": 4096
  },
  "candidate_code_hash": "sha256:...",
  "grader_result": {
    "passed": true,
    "total_tests": 47,
    "passed_tests": 47,
    "failed_tests": 0,
    "errors": 0,
    "diagnostics": {
      "common_mechanics": 1.0,
      "pure_convention": 1.0,
      "compound_interactions": 1.0
    }
  },
  "execution_metrics": {
    "duration_seconds": 1.84,
    "tokens_prompt": 1240,
    "tokens_completion": 412
  }
}
```

---

## 7. Methodological Distinctions & Disclaimers

Researchers evaluating Atavism must strictly preserve the following analytical distinctions:

1. **Engineering Verification vs. Model Capability:** Passing engineering unit tests and reference solution checks proves only that benchmark instrumentation is working as designed. It does not provide evidence about any AI model's capabilities.
2. **Behavioral Compliance vs. Internal Reasoning:** A model producing code that complies with Variant B (e.g. in T02) satisfies the contract, but **does not prove deliberate cognitive conflict arbitration**. The model may have replaced the function stub entirely without processing the inline comment.
3. **Mutation Detection vs. Real-World Defect Elimination:** 100% mutation kill rate confirms that tests detect specific modeled deviations; it does not guarantee that arbitrary human or model errors will always be detected.

