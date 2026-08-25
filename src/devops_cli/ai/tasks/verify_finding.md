## Chain-of-Thought Finding Verification Protocol

Execute a structured, 4-step chain-of-thought verification procedure for each reported finding:

### Step 1: Observable Code & AST Evidence Tracing
- Locate the exact file and line span (`path/to/file.ext:start-end`).
- Test each item in `verification_criteria` against the actual visible code, AST syntax, and runtime constructs.
- Determine whether the alleged vulnerability or logic error is genuinely present in the execution path.

### Step 2: Guardrail, Lockfile & Invalidation Testing
- Test all `invalidation_criteria` against surrounding context, caller validation, type guards, and architectural constraints.
- Verify path containment checks (`Path.is_relative_to`) and boundary enforcement.
- Verify cryptographic lockfiles (`uv.lock`, `poetry.lock`, `package-lock.json`, `Cargo.lock`, `go.sum`) to disprove false missing-pin alerts.
- Verify secure OS Keyring usage and confirm absence of insecure unencrypted packages (e.g. `keyrings.alt`).
- Check if the flagged code is documentation, tutorials, knowledge base guides, test assertions/fixtures, test mocks, template files, or prompt tasks explaining known vulnerabilities in the context of avoiding, explaining, or mitigating them.

### Step 3: Fix Correctness & Regression Evaluation
- Trace the proposed `fix` against the codebase.
- Confirm the fix directly remediates the root cause without introducing secondary flaws, type errors, or breaking API contracts.

### Step 4: Confidence Calibration & Causal Status Determination
- Any invalidation criterion satisfied, avoidance context detected, or mitigation present → `"status": "INVALIDATED" | "MITIGATED"`, `"verified": false`, `"reportable": false`.
- Verification criteria satisfied without invalidation or mitigation → `"status": "VERIFIED"`, `"verified": true`, `"reportable": true`.
- Inconclusive, theoretical, or unprovable finding → `"status": "UNVERIFIED"`, `"verified": false`, `"reportable": false`.

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
