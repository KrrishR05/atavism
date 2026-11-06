# Atavism — Model Evaluation Guide

**Target Audience:** Benchmark researchers, evaluation engineers, and micro1 Eval Hackathon auditors.  
**Scope:** Controlled model evaluation on Atavism benchmark tasks (T01–T05) using OpenRouter free-tier models, with extensible architecture for future frontier model phases.

---

## 1. Quick Start & Prerequisites

### 1.1 Strict Cost Control Policy ($0.00 Budget)
To ensure cost safety and reproducible experimentation:
- **Only verified free-tier models** carrying the explicit `:free` suffix on OpenRouter are authorized.
- The `FreeTierGuard` configuration safeguard unconditionally rejects paid model identifiers (e.g. `openai/gpt-4o`, `anthropic/claude-3-5-sonnet`) before any API request can be made.
- Automatic fallback to paid tiers is strictly prohibited.

### 1.2 Host Security Boundary (Windows vs Linux)
- Candidate model submissions must be graded under **`trust_level="untrusted"`**, which requires an OCI-compliant container runtime (Docker or Podman with Linux container isolation).
- On the Windows development host without an active Docker daemon, the evaluation runner **fails closed**:
  - The model prompt is formulated and sent.
  - The model response is captured and preserved in `results/trials/.../candidate.py` and `transcript.txt`.
  - Candidate code execution and grading is **blocked** to prevent untrusted code execution on the host OS.
  - The trial record records `trial_status: "SECURITY_BLOCKED"` and `failure_category: "CONTAINER_SANDBOX_UNAVAILABLE"`.
- To execute live untrusted candidate grading, run Atavism on an isolated Linux host (e.g. Ubuntu 22.04 LTS) with Docker.

---

## 2. API Key and Credential Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Populate your OpenRouter API key in `.env`:
   ```env
   OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
   OPENROUTER_DEFAULT_MODEL=meta-llama/llama-3.3-70b-instruct:free
   ```
3. Verify credential setup without making paid calls:
   ```bash
   python -m atavism.cli models
   ```
   Expected output:
   ```text
   ================================================================================
   ATAVISM — SUPPORTED ZERO-COST FREE-TIER MODELS
   ================================================================================
   Provider:          openrouter
   Connection Status: CONNECTED
   ...
   ```

---

## 3. Supported Zero-Cost Free-Tier Models

OpenRouter provides several free-tier models with explicit zero-cost pricing tags:

| Model Identifier | Provider / Architecture | Context Window | Use Case |
| :--- | :--- | :--- | :--- |
| `meta-llama/llama-3.3-70b-instruct:free` | Meta Llama 3.3 (70B) | 128k | Primary baseline model for code synthesis |
| `deepseek/deepseek-r1:free` | DeepSeek R1 (Reasoning) | 64k | Chain-of-thought specification reasoning |
| `deepseek/deepseek-chat:free` | DeepSeek V3 (MoE) | 64k | Fast general instruction adherence |
| `google/gemini-2.0-flash-exp:free` | Google Gemini 2.0 Flash | 1M | Large-context multimodal & code |
| `mistralai/mistral-small-24b-instruct-2501:free` | Mistral Small (24B) | 32k | Efficient instruction following |
| `qwen/qwen-2.5-coder-32b-instruct:free` | Alibaba Qwen 2.5 Coder (32B) | 32k | Code-specialized baseline |

---

## 4. Running Model Evaluations

### 4.1 Running a Dry-Run (Zero Calls, Zero Cost)
Before running API requests, always execute a dry-run to verify prompt construction, token estimation, and trial manifests:
```bash
python -m atavism.cli eval --task all --dry-run
```
For a specific task (e.g. T01):
```bash
python -m atavism.cli eval --task T01 --variant both --dry-run
```

### 4.2 Running Controlled Evaluations (Free Models)
Run 3 independent counterbalanced trials across all 5 benchmark tasks on Llama 3.3 70B:
```bash
python -m atavism.cli eval \
  --task all \
  --variant both \
  --model meta-llama/llama-3.3-70b-instruct:free \
  --trials 3 \
  --temperature 0.0 \
  --output-dir results/trials
```

To evaluate a single task (e.g. T04 Incomplete Specifications):
```bash
python -m atavism.cli eval \
  --task T04 \
  --variant both \
  --model deepseek/deepseek-r1:free \
  --trials 3 \
  --temperature 0.0
```

---

## 5. Result Structure & Artifact Preservation

Each trial writes artifacts to an isolated directory:
```
results/trials/{task_dir}/{variant}/{sanitized_model_id}/{trial_id}/
├── metadata.json       # Complete machine-readable provenance & score record
├── candidate.py        # Exact Python source code extracted from completion
└── transcript.txt      # Neutral system & user prompt + raw model response
```

### 5.1 Metadata Schema (`metadata.json`)
```json
{
  "trial_id": "T01-A-meta-llama_llama-3.3-70b-instruct_free-trial01-20261106_120000",
  "timestamp": "2026-11-06T12:00:00Z",
  "task_id": "T01_retry_semantics",
  "variant": "A",
  "benchmark_commit": "f6add26...",
  "grader_version": "1.0.0",
  "execution_backend": "container_docker",
  "trust_level": "untrusted",
  "trial_status": "COMPLETED",
  "model": {
    "provider": "openrouter",
    "name": "meta-llama/llama-3.3-70b-instruct:free",
    "temperature": 0.0,
    "max_tokens": 4096,
    "pricing": {
      "is_free": true,
      "pricing_classification": "FREE ($0.00)",
      "expected_cost_usd": 0.0
    }
  },
  "candidate_code_hash": "sha256:...",
  "manifest_hashes": {
    "TASK.md": "sha256:...",
    "contract.md": "sha256:...",
    "src/atavism_retry/types.py": "sha256:..."
  },
  "grader_result": {
    "passed": true,
    "total_tests": 47,
    "passed_tests": 47,
    "failed_tests": 0,
    "diagnostics": {
      "common_mechanics": 1.0,
      "pure_convention": 1.0,
      "compound_interactions": 1.0
    }
  },
  "execution_metrics": {
    "duration_seconds": 2.45,
    "tokens_prompt": 1420,
    "tokens_completion": 380,
    "cost_usd": 0.0
  }
}
```

---

## 6. Generating Aggregate Analysis Reports

To aggregate trial results and generate Markdown and JSON comparison summaries:

```bash
python -m atavism.cli report \
  --results-dir results/trials \
  --output results/reports/model_comparison.md \
  --json-output results/reports/model_comparison.json
```

The report aggregates:
1. **Pass Rate by Model:** Overall and per-task adherence rates.
2. **Control vs Treatment Delta ($\Delta = \text{PassRate}(B) - \text{PassRate}(A)$):** Quantifying vulnerability to convention divergence, inline misinformation, or specification incompleteness.
3. **Failure Taxonomy Distribution:** Classifying failures into syntax, timeout, container unavailable, or contract regression.

---

## 7. Future Frontier Model Evaluation Protocol

When frontier model evaluations are authorized in a future phase:
1. **Frontier Provider Configuration:**
   Configure credentials in `.env`:
   ```env
   FRONTIER_API_KEY=your_key_here
   FRONTIER_BASE_URL=https://api.openai.com/v1
   FRONTIER_MODEL=gpt-4o-2024-08-06
   ```
2. **Preserve Identical Protocol:**
   Frontier models must be evaluated against the exact same task versions, prompts, and grading suites.
3. **Run on Linux Container Host:**
   Frontier evaluations must run on an OCI container host with `--trust-level untrusted`.

