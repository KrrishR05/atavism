# Representative Failure Transcript: Task T01 (Variant B)
**Research Dimension:** Convention Divergence  
**Task ID:** `T01_retry_semantics`  
**Variant:** B (Treatment — Explicit Departure from Standard Convention)  
**Failure Category:** `CONTRACT_REGRESSION`  

---

## 1. Context and Prompt Summary
The model is provided with `TASK.md`, `contract.md`, and `types.py` for Meridian Gateway.
The authoritative contract explicitly defines:
```markdown
| HTTP Status | Error Code           | Retryable? |
|-------------|----------------------|------------|
| 429         | RATE_LIMITED         | Yes        |
| 503         | TEMPORARY_UNAVAILABLE| Yes        |
| 409         | LEASE_BUSY           | Yes        |

All other HTTP status and error-code combinations are NOT retryable.
```

---

## 2. Model Completion (Representative Extract)

```python
def send_with_retry(request, transport, policy, *, clock, sleep):
    attempt = 0
    while True:
        try:
            resp = transport.send(request)
            # Conventional heuristic learned during pretraining:
            # 4xx client errors (including 409 Conflict) are non-retryable
            if resp.status == 200:
                return resp
            
            # MODEL MISTAKE: Model implements standard HTTP retry rules
            # Only retrying 429 and 503, ignoring explicit 409 LEASE_BUSY clause
            is_retryable = resp.status in (429, 503) and resp.error_code in (
                "RATE_LIMITED", "TEMPORARY_UNAVAILABLE"
            )
            
            if not is_retryable or attempt >= policy.max_attempts - 1:
                return resp
            
            # Backoff calculation ...
            attempt += 1
            sleep(backoff_delay)
        except ConnectionError:
            # Transport retries ...
            pass
```

---

## 3. Diagnostic Grader Verdict

```text
Grading Result: FAILED
  Total tests:  50
  Passed tests: 45
  Failed tests: 5
  Errors:       0

Diagnostics:
  [PASS] common_mechanics: 44/44 passed (100.0%)
  [FAIL] pure_convention: 0/1 passed (0.0%)
  [FAIL] compound_interactions: 1/5 passed (20.0%)

Failures:
  [-] test_pure_convention_409_lease_busy_retried: AssertionError: assert 409 == 200
  [-] test_409_lease_busy_backoff_applied: AssertionError: expected retry sleep, got 0 calls
  [-] test_409_lease_busy_retry_after_precedence: AssertionError: expected retry sleep with Retry-After
```

---

## 4. Why the Model Failed
The model demonstrated strong Python programming ability, correctly implementing exponential backoff, deadline arithmetic, and exception handling (passing 44/44 common mechanics tests). 

However, it failed because of **Pretraining Bias / Convention Overwrite**: in standard web-scale HTTP libraries and API tutorials, HTTP `409 Conflict` is universally treated as a non-retryable client state error. The model succumbed to its statistical prior rather than adhering to the explicit, domain-specific contract clause.

