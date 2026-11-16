# Spec Delta: trivy-config-alerts

## ADDED Requirements

### Requirement: The harbor template Dockerfile holds a dated ignore entry
The repository SHALL hold one `misconfigurations` entry of `.trivyignore.yaml` for the rule `DS-0029` on the path `.venv/lib/python3.14/site-packages/harbor/cli/template-adapter/task-template/environment/Dockerfile`, with a `statement` that names the harbor task-template Dockerfile and issue #5947, and an `expired_at` date no more than 3 days after the entry.

#### Scenario: The entry of the harbor template Dockerfile
- **WHEN** a test reads the ignore file of the repository
- **THEN** it finds one misconfiguration entry of the rule DS-0029 and the path `.venv/lib/python3.14/site-packages/harbor/cli/template-adapter/task-template/environment/Dockerfile`, and the entry holds a statement with the issue #5947 and an expiry date
