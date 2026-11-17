## MODIFIED Requirements

### Requirement: Public HTTPS excludes the non-public ranges
Rule 4 of `devops-default-perimeter` SHALL exclude the private ranges, the shared address space `100.64.0.0/10`, the link-local range `169.254.0.0/16`, `169.254.169.254/32`, `192.0.0.0/24` and `198.18.0.0/15`.

#### Scenario: The policy is read
- **WHEN** `uv run devops ci --check --only k8s` renders Application `devops`, and a person reads NetworkPolicy `devops-default-perimeter` of the render
- **THEN** the `except` list of the port 443 rule holds exactly those ranges
