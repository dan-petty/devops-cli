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
