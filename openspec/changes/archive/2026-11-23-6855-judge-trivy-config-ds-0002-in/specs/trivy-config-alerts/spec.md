# Spec Delta: trivy-config-alerts

## ADDED Requirements

### Requirement: Dated ignore entry for the harbor template Dockerfile
`.trivyignore.yaml` SHALL hold an entry with `id: DS-0002`, a `paths` value that names `.venv/lib/python3.14/site-packages/harbor/cli/template-adapter/task-template/environment/Dockerfile`, a statement and an `expired_at` date.

#### Scenario: The IaC scan hides DS-0002 in the harbor template
- **WHEN** a maintainer runs `trivy config --ignorefile .trivyignore.yaml .venv/lib/python3.14/site-packages/harbor/cli/template-adapter/task-template/environment` at the merge commit
- **THEN** the scan reports no DS-0002 finding and exits 0

### Requirement: The entry carries an expiry that the scan reads
The entry MUST set `expired_at` to a date after the merge date, so the IaC scan hides the finding only until that date.

#### Scenario: The scan reads a valid expiry
- **WHEN** a maintainer runs `trivy config --ignorefile .trivyignore.yaml .venv/lib/python3.14/site-packages/harbor/cli/template-adapter/task-template/environment` at the merge commit
- **THEN** the scan reports no expired-entry error and exits 0
