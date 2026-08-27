## Chain-of-Thought Finding Verification Protocol

Execute a structured 4-step reasoning process to rigorously verify each reported finding:

### Step 1: Observable Code & AST Evidence Tracing
- Locate the exact file and line span (`path/to/file.ext:start-end`).
- Test each item in `verification_criteria` against actual visible code, AST syntax, and runtime constructs.
- Determine whether the alleged vulnerability or logic error is genuinely reachable and executable.

### Step 2: Guardrail, Lockfile & Invalidation Testing
- Test all `invalidation_criteria` against surrounding context, caller validation, type guards, and architectural constraints.
- Verify module import & attribute existence: Validate alleged missing imports, missing functions, or nonexistent attributes (e.g. `ImportError`, `AttributeError`) by checking the actual referenced target module source, AST symbol definitions, `__all__`, or `__getattr__`. If the symbol/attribute is defined or re-exported in the target module, immediately invalidate the finding as a false positive.
- Verify path containment checks (`is_relative_to` or path bounds), file extension filters, and bounded loader guards.
- Verify file permissions: Ensure sensitive cryptographic keys and private credentials enforce restricted permissions (0600) via atomic creation and explicit post-write `chmod`.
- Verify command exit code conventions: Tools intentionally returning non-zero status for informational outcomes (e.g. `diff` returning 1 when differences exist) are expected behavior.
- Verify target language features & formatter rules: Validate against standard language grammar and formatter conventions before flagging syntax issues.
- Verify syntax errors & AST integrity: Validate alleged syntax errors (missing/unmatched parentheses, quotes, malformed comprehensions) against AST parsing (`ast.parse`) or compiler validity. If the code parses cleanly without syntax errors, immediately invalidate the finding.
- Verify internal module introspection: Internal command registries and documentation generators that inspect trusted internal package modules (e.g. `devops_cli.commands.*`) are standard designs and not untrusted code injection.
- Verify AST definitions: Confirm that alleged duplicate symbols or commands are actually defined multiple times.
- Verify cryptographic lockfiles (`uv.lock`, `Cargo.lock`, `go.sum`, `package-lock.json`, `poetry.lock`) to disprove false unpinned package alerts.
- Verify secure secret managers, vaults, or OS Keyrings to confirm rejection of unencrypted plaintext secrets.
- Check context: Do NOT flag documentation, tutorials, architectural guides, test fixtures/mocks, or prompt tasks that explain known vulnerabilities in the context of avoiding or mitigating them.
- Check identifier context: Confirm the flagged item is an actual external endpoint rather than an internal telemetry attribute, metric name, or identifier.

### Step 3: Fix Correctness & Regression Evaluation
- Trace the proposed `fix` against the codebase.
- Confirm the fix remediates the root cause without introducing regressions, type errors, or breaking API contracts.

### Step 4: Confidence Calibration, Causal Status & Feedback Synthesis
- Invalidation criterion satisfied, avoidance context detected, or mitigation present → `"status": "INVALIDATED" | "MITIGATED"`, `"verified": false`, `"reportable": false`.
- Verification criteria satisfied without invalidation or mitigation → `"status": "VERIFIED"`, `"verified": true`, `"reportable": true`.
- Inconclusive, theoretical, or unprovable finding → `"status": "UNVERIFIED"`, `"verified": false`, `"reportable": false`.
- Synthesize an explicit causal explanation in `reason` detailing matched criteria for the feedback fine-tuning dataset (`feedback_dataset.jsonl`), ensuring the review system continuously learns from invalidations and suppresses recurring false positives.

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
