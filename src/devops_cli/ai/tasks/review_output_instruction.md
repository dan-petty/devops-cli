Output your findings as a single JSON block:

```json
{
  "findings": [
    {
      "severity": "HIGH",
      "location": "src/file.py:42-55",
      "title": "Short descriptive title",
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
