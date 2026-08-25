## Chain-of-Thought Synthesis Protocol

Follow a structured, 4-step chain-of-thought consolidation process to produce an authoritative, deduplicated review report:

### Step 1: Cross-Persona Finding Ingestion & Root-Cause Clustering
- Ingest findings from all specialized personas (`devsecops`, `architect`, `auditor`, `qa`, `pm`).
- Cluster findings that share the same underlying root cause or manifest at related call sites into a single high-signal entry.

### Step 2: Severity Calibration & Location Union
- For clustered findings, preserve the highest verified severity level (`CRITICAL` > `HIGH` > `MEDIUM` > `LOW`).
- Merge and format exact file and line number spans using canonical location syntax (`path/to/file.ext:start-end`).

### Step 3: Falsification & False-Positive Elimination
- Eliminate uncorroborated, speculative, or mitigated findings.
- Ensure no phantom defects or hallucinations are introduced.
- Redact any sensitive credentials, tokens, or private paths.

### Step 4: Unified Remediation & Executive Synthesis
- Synthesize a comprehensive, drop-in code fix (`fix`) resolving all clustered aspects of the defect.
- Formulate holistic `positive_observations` highlighting codebase architectural strengths.
- Determine the overall merge recommendation:
  - **BLOCK**: Any unmitigated `CRITICAL` findings.
  - **REQUEST CHANGES**: Unresolved `HIGH`, `MEDIUM`, or `LOW` findings.
  - **APPROVE**: Zero actionable defects.

---

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
