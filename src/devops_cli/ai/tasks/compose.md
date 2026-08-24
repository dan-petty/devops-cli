## Synthesis Task
Consolidate segmented review findings and analyses into a single authoritative, deduplicated review report.

## Consolidation Rules
- **Semantic Deduplication**: Group findings that share an identical underlying root cause into a single high-signal entry with unified file locations and drop-in fix.
- **Preserve Verified Severity**: Preserve the highest verified severity level with exact file and line number spans (`path/to/file.ext:start-end`).
- **Eliminate False Positives**: Drop uncorroborated, speculative, or mitigated findings; never invent new unobserved defects.
- **Security & Privacy Guardrail**: Redact any sensitive credentials, tokens, or private paths. Adhere strictly to the required JSON schema.

## Output Format (JSON)
Return ONLY a valid JSON object matching:
```json
{
  "findings": [
    {
      "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
      "location": "path/to/file.py:start-end",
      "title": "Concise issue title",
      "description": "Root cause and impact analysis.",
      "fix": "Drop-in code or configuration remediation.",
      "verification_criteria": ["Observable condition proving defect."],
      "invalidation_criteria": ["Observable condition disproving defect."],
      "references": ["CWE-XXX", "OWASP-XXX"]
    }
  ],
  "positive_observations": ["Notable architectural or security strengths."],
  "recommendation": "BLOCK" | "REQUEST CHANGES" | "APPROVE",
  "summary": "High-level summary of code quality, required remediations, and next steps."
}
```
