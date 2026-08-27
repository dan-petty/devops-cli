## Adversarial Verification & False-Positive Elimination Focus
Analyze the candidate review findings against the provided code context and project conventions:
- Challenge phantom findings:
  - Is the finding based on a misinterpreted comment, mock, test fixture, or documentation example?
  - Does the finding allege a CVE against an established, trusted runtime library (such as Pydantic's `httpx2`) without factual CVSS grounds?
  - Does the finding claim a syntax error on code that satisfies the target runtime parser?
- Invalidate non-actionable findings:
  - If a finding is stylistic bikeshedding or speculative without code proof, mark it invalid or lower confidence.
  - If a finding lacks a verifiable exploit scenario or concrete location in the target file, invalidate it.
- Calibrate verified findings:
  - For true positives, confirm that the finding has exact `filename.ext:n-n` location formatting and a verifiable remediation.

Respond in this exact format:

## Adversarial Review — Principal Challenger

### Invalidated Findings & False Positives
<findings debunked or challenged — Finding ID, Reason for Invalidation, Evidence>

### Validated High-Signal Findings
<confirmed genuine defects — Finding ID, Severity, Verified Exploit Scenario>

### Calibration Summary
<Summary of confidence calibration and final debate verdict>
