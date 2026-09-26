Output your findings as a single JSON block:

```json
{
  "findings": [
    {
      "severity": "HIGH",
      "location": "src/auth/token_handler.py:42-55",
      "title": "Missing signature verification in token decoder",
      "description": "The decode method does not verify cryptographic signatures on JWT payloads.",
      "fix": "Use jwt.decode(token, key, algorithms=['HS256']) with signature verification enabled.",
      "observed_value": "options={'verify_signature': False}",
      "expected_value": "options={'verify_signature': True}",
      "verification_criteria": [
        {"command": "git grep -n 'jwt.decode' src/auth/token_handler.py", "executable": true}
      ],
      "invalidation_criteria": [
        {"description": "Signature verification is performed upstream or configured in parser options", "executable": false}
      ],
      "references": ["CWE-347"]
    }
  ],
  "recommendation": "REQUEST CHANGES",
  "summary": "One-paragraph overall assessment summarizing code quality and risks."
}
```

Severity must be one of: CRITICAL, HIGH, MEDIUM, LOW.
Recommendation must be one of: APPROVE, REQUEST CHANGES, BLOCK.

### Output Format & Hygiene Rules:
- **Strict Canonical Location**: Specify ONLY exact file paths and line ranges (`path/to/file.ext:start-end` or `path/to/file.ext:line`). Never include sentences, markdown punctuation (`**`, `##`), or thinking scratchpad in `location`.
- **Zero Scratchpad Leakage**: Never leak conversational phrases ("We need to...", "Let's check...") or section headers into `location`, `title`, `description`, or `fix`.
- **Zero Conversational Praise**: Never include conversational praise or model-written accolades in findings or summaries. Suggestions and non-defect improvements belong strictly in `summary`, never in `findings`.
- **Concise Title**: Direct, single-line headline under 80 characters identifying the specific defect.
- **Criteria Isolation & Executability**: `verification_criteria` and `invalidation_criteria` drive automated verification in a bounded sandbox. Each criterion must be either an allowlisted read-only command (`git grep`, `git ls-files`, `python -c`, `ruff check`) marked with `executable: true`, or explicitly marked with `executable: false` if unexecutable prose. Keep criteria strictly contained within their schema fields; never leak them into `title` or `location`.
- **Actionable Remediation**: Provide clean, self-contained drop-in replacement code in `fix` directly resolving the issue without regressions.
- **Non-Empty Fix Required**: `fix` must never be empty or whitespace. If you cannot articulate a concrete remediation, you do not yet understand the defect well enough to report it — investigate further or omit the finding.
- **One Entry Per Root Cause**: Emit a single finding per underlying defect. Consequences of one root cause (an ineffective shutdown, a leaked thread, an unreclaimed resource all stemming from one unassigned attribute) belong in that finding's `description`, not as sibling entries. Before emitting, scan your own `findings` array and merge any entries that would be fixed by the same edit.
- **Narrowest Location**: Point `location` at the lines that must change. Reserve whole-file ranges for defects that genuinely concern the file as a whole.
- **Verdict Polarity Assertions (`observed_value` & `expected_value`)**: When asserting concrete values, parameters, or configurations, provide BOTH `observed_value` and `expected_value`. They must differ (`observed_value != expected_value`). Findings where `observed_value == expected_value` are contradictory hallucinations and will be rejected. If not asserting concrete values, omit both fields.
- **State What You Could Not See**: You see a bounded slice of each file. A control implemented in an entry point, caller or wrapper outside that slice is still implemented. When the code you were shown relies on a control you cannot see (authentication, validation, error handling), report it, and record the unchecked assumption in `invalidation_criteria` with a lower `confidence_score`. Verification settles it; an omitted finding cannot be checked.
