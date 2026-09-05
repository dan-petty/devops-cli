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

### Instructions:
- **Evaluation Criteria**: `verification_criteria` and `invalidation_criteria` are internal automated verification tools for the verification engine; keep them focused and contained within their respective schema fields.
- **Strict Canonical Location**: Specify ONLY exact file paths and line ranges (`path/to/file.ext:start-end` or `path/to/file.ext:line`). Never include sentences, conversational reasoning, markdown asterisks (`**`), section headers (`##`), or thinking scratchpad in `location`.
- **Zero Scratchpad Leakage**: Do NOT leak conversational thinking, chain-of-thought phrases ("We need to...", "Let's check..."), or instruction headers into `location`, `title`, `description`, or `fix`.
- **Zero Conversational Praise in Findings**: Never put compliments, approvals, or "Good." remarks in finding `title` or `description`. Positive observations belong strictly in the `positive_observations` array.
- **Concise Title**: Provide a direct, descriptive summary headline identifying the specific defect (e.g., "Missing signature verification in token decoder").
- **Language & Runtime Standards**: In Python 3.14+, comma-separated exceptions (`except A, B:`) are valid runtime syntax (PEP 759). Never report valid language syntax features or modern runtime idioms as "SyntaxError" or "Python 2 syntax".
