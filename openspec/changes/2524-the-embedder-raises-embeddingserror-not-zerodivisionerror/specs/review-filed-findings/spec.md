## ADDED Requirements

### Requirement: Hardening audit files finding without a model credential
The hardening audit workflow SHALL file its finding as a GitHub issue using a path that requires no model or embedding credential.

#### Scenario: Workflow step runs on a runner with only GH_TOKEN
- **WHEN** the hardening report step fails and the runner has no model credential
- **THEN** a GitHub issue is created with the finding title and body and the workflow step exits with code 0
