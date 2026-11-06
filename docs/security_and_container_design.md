# Atavism — Security Architecture & Container Execution Design

## 1. Security Boundary of the Subprocess Execution Mode

### 1.1 Current Implementation

In the local development and benchmark authoring environment, candidate solutions are evaluated via Python subprocess invocation (`subprocess.run([sys.executable, "-m", "pytest", ...])`) managed by `src/atavism/grading.py`.

The grading harness applies the following security hardening measures:

1. **Environment Scrubbing (Allowlist Filtering):**
   - The candidate subprocess does **not** inherit the host environment.
   - Only explicitly allowlisted, non-sensitive runtime variables (`SAFE_SYSTEM_ENV_VARS`) are forwarded (e.g. `SYSTEMROOT`, `WINDIR`, `PATH`, `PATHEXT`, `TEMP`, `TMP`, `COMSPEC`, `USERPROFILE`, `HOME`, `LANG`, `LC_ALL`, `PYTHONIOENCODING`).
   - Any environment variable matching sensitive patterns (`KEY`, `TOKEN`, `SECRET`, `AUTH`, `PASS`, `CRED`, `SSH`, `AWS`, `GITHUB`, `OPENAI`, `ANTHROPIC`, `AZURE`, `GEMINI`) is unconditionally stripped.
   - `PYTHONDONTWRITEBYTECODE=1` is enforced to prevent persistent `.pyc` caching and workspace pollution.

2. **Temporary Directory Sandboxing:**
   - The candidate source file and test harness are assembled in an ephemeral directory (`tempfile.TemporaryDirectory(prefix="atavism_grade_")`).
   - The working directory (`cwd`) is set to this temporary directory.

3. **Subprocess Timeout Enforcement:**
   - A hard timeout (default 60 seconds) is enforced via `subprocess.run(..., timeout=timeout)`.
   - If a candidate hangs, enters an infinite loop, or attempts a slow resource attack, it is terminated, returning `return_code=124`, `errors=1`, and `passed=False`.

4. **Strict Task Metadata Validation:**
   - Task paths, types files, and test files are validated against path traversal attacks (`..`). Any attempt to reference files outside the task directory raises a descriptive `ValueError`.

### 1.2 Explicit Security Limitations

> [!WARNING]
> **Environment scrubbing does NOT constitute kernel-level isolation, filesystem confinement, or network isolation.**

Subprocess execution alone is **not safe for untrusted candidate code**. Because the Python subprocess runs as a child process of the benchmark harness, it executes under the OS permissions of the host user:

- **Filesystem Access:** An untrusted candidate script could potentially read or modify any files readable or writable by the host user outside the temporary directory.
- **Network Sockets:** An untrusted candidate script could open socket connections to the local network or internet unless blocked by the host OS or firewall.
- **Resource Exhaustion:** Without cgroup limits, a candidate could attempt CPU or memory exhaustion before the subprocess timeout terminates it.

Therefore, the subprocess execution mode is intended **strictly for local verification, unit tests, and development on trusted reference implementations and mutation fixtures**.

---

## 2. Containerized Execution Design for Untrusted Candidate Trials

When evaluating untrusted or autonomous AI coding agents, grading must occur inside an ephemeral, hardened OCI container (Docker, Podman, or gVisor `runsc`).

### 2.1 Container Security Model

The container execution environment must implement defense-in-depth across six distinct isolation layers:

| Layer | Implementation | Security Objective |
| :--- | :--- | :--- |
| **Network** | `--network none` | Completely prevents exfiltration, telemetry, reverse shells, and external calls. |
| **Root Filesystem** | `--read-only` | Prevents persistence, binary replacement, or container modification. |
| **Scratch Space** | `--tmpfs /tmp:rw,noexec,nosuid,size=64m` | Memory-backed temporary directory; execution (`noexec`) disabled in `/tmp`. |
| **Workspace Volume** | Dedicated ephemeral scratch volume | Candidate cannot modify evaluator files or benchmark inputs. |
| **User Privileges** | `--user 65534:65534` (`nobody:nogroup`), `--cap-drop=ALL` | Drops all Linux capabilities; prevents privilege escalation (`--security-opt=no-new-privileges`). |
| **Resource Limits** | `--memory 512m --cpus 1.0 --pids-limit 64` | Restricts CPU, RAM, and process counts to prevent fork-bombs and DoS. |

### 2.2 Volume Mount Hierarchy

```text
Host Filesystem                                Container Filesystem
─────────────────────────────────────────────────────────────────────────────
task_dir/variants/<var>/workspace/   ──(ro)──> /benchmark/task:ro
task_dir/private/tests/              ──(ro)──> /benchmark/tests:ro
candidate_output/                    ──(ro)──> /benchmark/candidate:ro
host_tmp/scratch_<trial_id>/         ──(rw)──> /workspace:rw (ephemeral)
```

1. **Benchmark Inputs (`/benchmark/task:ro`):** Read-only mount. Candidate cannot mutate task instructions or contract specifications.
2. **Hidden Test Suite (`/benchmark/tests:ro`):** Read-only mount. Candidate cannot tamper with test assertions or fixtures.
3. **Candidate Submission (`/benchmark/candidate:ro`):** Read-only mount containing model-generated code.
4. **Execution Scratch Workspace (`/workspace:rw`):** Ephemeral directory mounted with bounded size (`size=64m`). All intermediate files generated during pytest execution are written here.

### 2.3 Container Invocation Template

```bash
docker run --rm \
  --name "atavism-grade-${TRIAL_ID}" \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --user 65534:65534 \
  --memory 512m \
  --memory-swap 512m \
  --cpus 1.0 \
  --pids-limit 64 \
  --stop-timeout 5 \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --volume "${TASK_DIR}/variants/${VARIANT}/workspace:/benchmark/task:ro" \
  --volume "${TASK_DIR}/private/tests:/benchmark/tests:ro" \
  --volume "${CANDIDATE_PATH}:/benchmark/candidate/client.py:ro" \
  --volume "${SCRATCH_DIR}:/workspace:rw" \
  --env PYTHONPATH="/workspace/src:/benchmark/tests" \
  --env PYTHONDONTWRITEBYTECODE="1" \
  --env PYTHONIOENCODING="utf-8" \
  atavism-eval-runner:latest \
  pytest /benchmark/tests -v --junitxml=/workspace/junit.xml
```

### 2.4 Lifecycle and Cleanup Protocol

1. **Pre-Execution:**
   - Host generates a fresh, empty scratch directory (`${SCRATCH_DIR}`).
   - Host copies starter package files into `${SCRATCH_DIR}/src/${PACKAGE_NAME}/`.
   - Host copies `${CANDIDATE_PATH}` to `${SCRATCH_DIR}/src/${PACKAGE_NAME}/${MODULE_NAME}`.
2. **Execution:**
   - Container is launched with `--rm` flag and hard timeout.
   - Results are written strictly to `${SCRATCH_DIR}/junit.xml`.
3. **Post-Execution:**
   - Host reads and parses `${SCRATCH_DIR}/junit.xml` via `atavism.grading`.
   - Host purges `${SCRATCH_DIR}` completely.
   - If container exceeds execution timeout, host issues `docker kill` and logs a timeout failure.

---

## 3. Execution Backend Architecture & Fail-Closed Behavior

Atavism implements an explicit dual execution backend in `src/atavism/execution.py`:

### 3.1 Backend Classification

1. **`ContainerExecutionBackend` (Untrusted Candidate Sandbox):**
   - Implements the hardened OCI/Docker container runner.
   - Checks container daemon availability via `is_available()`.
   - On Windows hosts, verifies that Docker is operating with Linux containers (`OSType == "linux"`), since Windows container mode does not support Linux capability dropping (`--cap-drop=ALL`), read-only root filesystems (`--read-only`), or Linux security options (`--security-opt=no-new-privileges`).
   - If Docker or Linux container support is absent, **fails closed** by raising `UntrustedExecutionUnavailableError`. It **never** silently falls back to host execution.

2. **`TrustedLocalBackend` (Trusted Development & Unit Testing):**
   - Implements host subprocess execution with environment scrubbing (`SAFE_SYSTEM_ENV_VARS`).
   - Explicitly marked for trusted internal benchmark development, reference solution testing, and mutation audits.
   - Requires explicit opt-in via `trust_level="trusted-local"` (or CLI `--trust-level trusted-local`).

### 3.2 CLI and API Security Defaults

- **CLI Default:** `atavism grade <task> <variant> <candidate>` defaults to `--trust-level untrusted`. On systems without an active Docker engine, it fails closed with exit code 2 and a security error message.
- **Python API Default:** `grade_task_candidate(..., trust_level="trusted-local")` allows existing offline unit test suites and mutant runners to operate, while `grade_task_candidate(..., trust_level="untrusted")` enforces container sandbox execution or fails closed.


