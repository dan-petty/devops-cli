## Chain-of-Thought Finding Verification Protocol

Execute a structured, 4-step chain-of-thought verification procedure for each reported finding:

### Step 1: Observable Code & AST Evidence Tracing
- Locate the exact file and line span (`path/to/file.ext:start-end`).
- Test each item in `verification_criteria` against the actual visible code, AST syntax, and runtime constructs.
- Determine whether the alleged vulnerability or logic error is genuinely present in the execution path.

### Step 2: Guardrail, Lockfile & Invalidation Testing
- Test all `invalidation_criteria` against surrounding context, caller validation, type guards, and architectural constraints.
- Verify path containment checks (`Path.is_relative_to`), file extension filters, and bounded loader guards.
- Verify file permissions: atomic file creation with restricted mode via `os.open(..., O_CREAT, 0o600)` completely fulfills private key/credential security without requiring a redundant post-creation `chmod` call.
- Verify command exit code conventions: tools like `diff` and `kubectl diff` intentionally return exit code 1 when differences are found, so omitting `check=True` for diff operations is expected behavior and not a defect.
- Verify Python 3.14+ runtime features & formatter rules: modern Python 3.14 grammar and Ruff formatting allow and normalize comma-separated exception types in `except A, B:` clauses when omitting an alias variable. Never flag standard Ruff-formatted Python 3.14 exception lists as syntax errors.
- Verify AST definitions: confirm that alleged duplicate functions or commands are actually defined multiple times before flagging duplication.
- Verify cryptographic lockfiles (`uv.lock`, `poetry.lock`, `package-lock.json`, `Cargo.lock`, `go.sum`) to disprove false missing-pin alerts.
- Verify secure OS Keyring usage and confirm rejection of insecure, zero-priority, or unencrypted backends (e.g. `keyrings.alt`, `FailKeyring`).
- Check if the flagged code is documentation, tutorials, knowledge base guides, test assertions/fixtures, test mocks, template files, or prompt tasks explaining known vulnerabilities in the context of avoiding, explaining, or mitigating them.
- Check if the flagged item is a source code identifier, OpenTelemetry attribute, or file name rather than an actual unauthenticated external network endpoint.

### Step 3: Fix Correctness & Regression Evaluation
- Trace the proposed `fix` against the codebase.
- Confirm the fix directly remediates the root cause without introducing secondary flaws, type errors, or breaking API contracts.

### Step 4: Confidence Calibration, Causal Status & Feedback Synthesis
- Any invalidation criterion satisfied, avoidance context detected, or mitigation present → `"status": "INVALIDATED" | "MITIGATED"`, `"verified": false`, `"reportable": false`.
- Verification criteria satisfied without invalidation or mitigation → `"status": "VERIFIED"`, `"verified": true`, `"reportable": true`.
- Inconclusive, theoretical, or unprovable finding → `"status": "UNVERIFIED"`, `"verified": false`, `"reportable": false`.
- Synthesize an explicit, audit-grade causal explanation in `reason` detailing matched criteria and root cause for the feedback dataset.

---

## Output Format
Return ONLY a JSON array with one object per input finding:
```json
[
  {
    "verified": true,
    "mitigated": false,
    "invalidated": false,
    "status": "VERIFIED",
    "reportable": true,
    "severity": "HIGH",
    "location": "path/to/file.ext:12-18",
    "confidence_score": 0.95,
    "verified_criteria_matched": ["Observable defect condition confirmed in source."],
    "invalidated_criteria_matched": [],
    "reason": "Step-by-step verification confirmed defect present in lines 12-18 with zero mitigating guards."
  }
]
```
