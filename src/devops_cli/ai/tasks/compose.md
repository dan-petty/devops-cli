## Chain-of-Thought Synthesis Protocol

Follow a structured, 4-step chain-of-thought consolidation process to produce an authoritative, deduplicated review report:

### Step 1: Cross-Persona Finding Ingestion & Root-Cause Clustering
- Ingest findings from all specialized personas (`devsecops`, `architect`, `auditor`, `qa`, `pm`).
- Cluster findings that share the same underlying root cause or manifest at related call sites into a single high-signal entry.

### Step 2: Severity Calibration & Location Union
- For clustered findings, preserve the highest verified severity level (`CRITICAL` > `HIGH` > `MEDIUM` > `LOW`).
- Merge and format exact file and line number spans using canonical location syntax (`path/to/file.ext:start-end`).

### Step 3: Falsification & False-Positive Elimination
- Drop findings no source finding supports; keep mitigated findings with their mitigation in the description.
- Ensure no phantom defects or hallucinations are introduced.
- Redact any sensitive credentials, tokens, or private paths.

### Step 4: Unified Remediation & Executive Synthesis
- Synthesize a comprehensive, drop-in code fix (`fix`) resolving all clustered aspects of the defect.
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
      "location": "path/to/file.ext:start-end",
      "title": "Concise issue title",
      "description": "Root cause and impact analysis.",
      "fix": "Drop-in code or configuration remediation.",
      "verification_criteria": [
        {"command": "python -c \"from module import function; assert function(bad_input) == wrong_result\"", "executable": true}
      ],
      "invalidation_criteria": [
        {"description": "Observable condition disproving defect.", "executable": false}
      ],
      "references": ["The CWE that names this defect, if one does"]
    }
  ],
  "recommendation": "BLOCK" | "REQUEST CHANGES" | "APPROVE",
  "summary": "High-level summary of code quality, required remediations, and next steps."
}
```

CRITICAL: Verification and invalidation criteria are internal evaluation tools for automated verification; they must NEVER appear inside 'title', 'location', or 'description'. Keep 'title' concise and 'location' canonical (`filename.ext:start-end`).
