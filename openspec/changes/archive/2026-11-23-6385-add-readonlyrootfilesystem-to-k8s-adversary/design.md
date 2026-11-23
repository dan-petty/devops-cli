# Design

## Decisions

### Fix the fixture at its source
SECURITY.md states that fixing the file in a pull request is the first choice for judging a Trivy-config alert.
Setting `readOnlyRootFilesystem: true` on the container and `runAsNonRoot: true` on the pod template removes KSV-0118 and KSV-0014 without suppressing checks.

### Preserve prompt injection payloads
The comment headers and `security.override/instructions` annotations test prompt injection defenses in the AI review pipeline.
All comment headers and annotations stay unchanged.

### Verify in test suite
Add an explicit test assertion in `tests/review/test_review_prompt_adversaries.py` to prevent regression of the security context settings.

## Rejected alternatives

- **Add an entry to `.trivyignore.yaml`**: SECURITY.md specifies ignore entries for findings that cannot be fixed. The fixture can be compliant while keeping its injection payload.
- **Dismiss the alert in code scanning**: An agent cannot dismiss alerts, and GitHub dismissals leave no repository record.
- **Set container readOnlyRootFilesystem only**: Trivy reports KSV-0118 for the DaemonSet template when pod-level security context is omitted. Setting `runAsNonRoot: true` clears the remaining HIGH alert.
