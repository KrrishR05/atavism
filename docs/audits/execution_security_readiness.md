# Atavism — Execution Security Readiness Audit

**Audit Date:** 2026-11-06  
**Auditor:** Senior Security Reviewer, Infrastructure Engineer & Benchmark Architect  
**Host Environment:** Windows 11 (Host development machine without Docker daemon)  
**Target Module:** `src/atavism/execution.py`, `src/atavism/grading.py`, `src/atavism/cli.py`  

---

## 1. Security Architecture Summary

Atavism enforces a **strict dual-backend execution model**:
1. **`ContainerExecutionBackend` (Default / Untrusted):**
   - Intended for model-generated, untrusted candidate submissions.
   - Requires an OCI-compliant container runtime with Linux container support.
   - Configures `--network=none`, `--read-only`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, `--user=65534:65534` (nobody), `--memory=512m`, `--cpus=1.0`, `--pids-limit=64`.
   - **Fail-Closed Guarantee:** If Docker is missing, stopped, or fails to launch, execution immediately halts with `UntrustedExecutionUnavailableError` (exit code 126). Untrusted code **never** falls back to host execution.
2. **`TrustedLocalBackend` (Opt-in / Trusted Only):**
   - Subprocess execution directly on the host OS.
   - Scrubbed environment allowlist (`SAFE_SYSTEM_ENV_VARS`) unconditionally removing sensitive API keys, cloud credentials, tokens, and SSH keys.
   - **Boundary Statement:** Environment scrubbing is *not* an operating system sandbox. It provides zero filesystem, network, or PID isolation. It is strictly restricted to trusted internal development and reference test validation.

---

## 2. Control Verification Matrix

| Security Control | Implementation Mechanism | Verification Status | Evidence / Notes |
| :--- | :--- | :--- | :--- |
| **Default Trust Level** | CLI `--trust-level` defaults to `untrusted` | **Verified by execution** | `test_cli_grade_defaults_to_untrusted_and_fails_closed` passed. |
| **Fail-Closed on Missing Runtime** | Raises `UntrustedExecutionUnavailableError` when Docker info fails | **Verified by execution** | `test_untrusted_execute_fails_closed_when_docker_unavailable` passed. |
| **Fail-Closed on OCI Launch Error** | Catches exit codes 125/126/127 and raises security error | **Verified by execution** | `test_untrusted_execute_fails_closed_on_container_runtime_launch_error` passed. |
| **No Silent Fallback** | `ContainerExecutionBackend` has no call path to `TrustedLocalBackend` | **Verified by code inspection** | Inspection of `execution.py` L220-L252. |
| **Explicit Local Opt-in** | Requires `--trust-level trusted-local` flag | **Verified by execution** | `test_cli_grade_passes_with_explicit_trusted_local` passed. |
| **Environment Variable Scrubbing** | Filters environment against `SAFE_SYSTEM_ENV_VARS` & `SENSITIVE_ENV_PATTERNS` | **Verified by execution** | `test_build_minimal_env_filters_sensitive_variables` and `test_candidate_subprocess_cannot_read_host_secret` passed. |
| **Identifier & Path Traversal Guards** | Validates package names, module names, and restricts paths to workspace | **Verified by execution** | `test_metadata_validation.py` (8 traversal & malformed metadata tests passed). |
| **Subprocess Execution Timeout** | `subprocess.TimeoutExpired` terminates process with exit code 124 | **Verified by execution** | `test_candidate_timeout_handled_gracefully` passed. |
| **Docker Isolation Flags Construction** | Passes `--network=none`, `--read-only`, `--cap-drop=ALL`, `--user=nobody`, cgroups | **Verified by execution (Unit test)** | `test_build_docker_command_includes_all_isolation_flags` passed. |
| **Live Kernel Sandbox Isolation** | Linux kernel namespace, seccomp, and cgroup enforcement | **NOT VERIFIED ON HOST** | Host environment runs Windows without Docker; live container execution cannot be validated locally. |
| **Private Grader Isolation** | Grader files stored outside candidate workspace; only allowed files exported | **Verified by execution** | 43 workspace isolation tests across T01–T04 passed. |
| **Safe Temp Directory Cleanup** | `tempfile.TemporaryDirectory` context manager | **Verified by code inspection** | Inspected in `grading.py` L174. |

---

## 3. Host Limitation Statement & Linux Readiness Checklist

> **CRITICAL TRANSPARENCY NOTICE:**  
> The current development host runs **Windows 11 without a running Docker engine**.  
> The fail-closed behavior has been rigorously verified: running untrusted grading fails closed with code 126 and raises `UntrustedExecutionUnavailableError`.  
> However, **live container execution on a Linux kernel has NOT been verified on this host.**  
> Under no circumstances may the benchmark claim that container sandboxing is operational on the current host.

### Pre-Trial Linux Host Validation Checklist
Before running untrusted LLM candidate trials, a Linux evaluation host must complete the following checklist:
1. [ ] Linux OS kernel (Ubuntu 22.04 LTS or Debian 12 recommended).
2. [ ] Docker / OCI runtime installed and active: `docker info --format '{{.OSType}}'` returns `linux`.
3. [ ] Pull evaluation base image: `docker pull python:3.11-slim`.
4. [ ] Run isolated probe: `docker run --rm --network=none --read-only --user=65534:65534 python:3.11-slim python3 -c "print('sandbox_ok')"`
5. [ ] Execute live untrusted grade: `atavism grade benchmark/tasks/T01_retry_semantics A <candidate.py> --trust-level untrusted`
6. [ ] Confirm untrusted execution produces clean JUnit XML and exit code 0 or 2 (never 126).

