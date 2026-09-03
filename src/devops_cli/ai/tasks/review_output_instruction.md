Output your findings as a single JSON block:

```json
{
  "findings": [
    {
      "severity": "HIGH",
      "location": "src/file.py:42-55",
      "title": "Short descriptive title (under 80 chars, no criteria)",
      "description": "What the issue is and the exploit/impact scenario.",
      "fix": "The specific change needed to resolve this finding.",
      "verification_criteria": [
        "Concrete observable condition in code proving the issue"
      ],
      "invalidation_criteria": [
        "Concrete condition or mitigation that disproves the issue"
      ],
      "references": []
    }
  ],
  "positive_observations": ["Good practice at src/..."],
  "recommendation": "REQUEST CHANGES",
  "summary": "One-paragraph overall assessment."
}
```

Severity must be one of: CRITICAL, HIGH, MEDIUM, LOW.
Recommendation must be one of: APPROVE, REQUEST CHANGES, BLOCK.

CRITICAL REPORTING CONSTRAINTS:
- `verification_criteria` and `invalidation_criteria` are internal automated verification tools for the verification engine; they must NEVER be included in reporting fields (such as `title`, `location`, or `description`).
- `location` must strictly be `path/to/file.ext:start-end` or `path/to/file.ext:line`. Do NOT include prompt sentences, criteria, or instructions in `location`.
- `title` must be a concise headline describing the defect only, with no prefix instructions.
- Never declare a "SyntaxError" on valid modern language syntax.
