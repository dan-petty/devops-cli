## Adversarial Verification & False-Positive Elimination Focus
Analyze candidate review findings against code context, target runtime, and project conventions:
- Challenge phantom findings:
  - Is the finding based on a misinterpreted comment, mock, test fixture, or documentation example?
  - Does the finding match a known false-positive pattern (e.g. valid language idioms, prompt redaction markers `<masked-*>`, synthetic test credentials, or verified dependencies pinned in lockfiles)?
  - Does the finding allege a CVE or vulnerability without factual evidence or CVSS basis?
  - Does the finding claim a syntax error on code satisfying the target runtime parser?
- Invalidate non-actionable findings:
  - If a finding is cosmetic bikeshedding or speculative without code proof, invalidate or lower confidence.
  - If a finding lacks a verifiable exploit scenario or concrete location in the target file, invalidate it.
- Calibrate verified findings:
  - For true positives, confirm exact `filename.ext:start-end` location formatting and verifiable remediation.
  - Articulate step-by-step causal rationale for each invalidation or verification to calibrate the review dataset.
