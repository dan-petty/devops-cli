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
      "verification_criteria": [
        "Token decoding call lacks algorithm or verification parameter"
      ],
      "invalidation_criteria": [
        "Signature verification is performed upstream or configured in parser options"
      ],
      "references": ["CWE-347"]
    }
  ],
  "positive_observations": ["Explicit key rotation implemented in auth/rotation.py"],
  "recommendation": "REQUEST CHANGES",
  "summary": "One-paragraph overall assessment summarizing code quality and risks."
}
```

Severity must be one of: CRITICAL, HIGH, MEDIUM, LOW.
Recommendation must be one of: APPROVE, REQUEST CHANGES, BLOCK.

### Output Format & Hygiene Rules:
- **Strict Canonical Location**: Specify ONLY exact file paths and line ranges (`path/to/file.ext:start-end` or `path/to/file.ext:line`). Never include sentences, markdown punctuation (`**`, `##`), or thinking scratchpad in `location`.
- **Zero Scratchpad Leakage**: Never leak conversational phrases ("We need to...", "Let's check...") or section headers into `location`, `title`, `description`, or `fix`.
- **Zero Conversational Praise in Findings**: Positive observations belong strictly in the `positive_observations` array, never in finding `title` or `description`.
- **Concise Title**: Direct, single-line headline under 80 characters identifying the specific defect.
- **Criteria Isolation**: `verification_criteria` and `invalidation_criteria` are internal automated verification arrays; keep them focused and strictly contained within their respective schema fields.
- **Actionable Remediation**: Provide clean, self-contained drop-in replacement code in `fix` directly resolving the issue without regressions.
- **Non-Empty Fix Required**: `fix` must never be empty or whitespace. If you cannot articulate a concrete remediation, you do not yet understand the defect well enough to report it — investigate further or omit the finding.
- **One Entry Per Root Cause**: Emit a single finding per underlying defect. Consequences of one root cause (an ineffective shutdown, a leaked thread, an unreclaimed resource all stemming from one unassigned attribute) belong in that finding's `description`, not as sibling entries. Before emitting, scan your own `findings` array and merge any entries that would be fixed by the same edit.
- **Narrowest Location**: Point `location` at the lines that must change. Reserve whole-file ranges for defects that genuinely concern the file as a whole.
- **Do Not Assert Absence Beyond Your Segment**: You see a bounded slice of each file. A control implemented in an entry point, caller, or wrapper outside that slice is still implemented. Report "missing authentication / validation / error handling" only when the provided linked-file and symbol context confirms its absence; otherwise omit the finding or record the unchecked assumption in `invalidation_criteria` and reduce `confidence_score`.
