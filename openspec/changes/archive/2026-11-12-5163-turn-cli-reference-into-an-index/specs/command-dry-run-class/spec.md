## MODIFIED Requirements

### Requirement: docs-no-external-request
The commands `docs check` and `docs generate` SHALL carry the `no-external-request` dry-run class, running locally without external requests.

#### Scenario: Dry run on docs check
- **WHEN** user executes `devops --dry-run docs check`
- **THEN** documentation checks execute locally without external requests
