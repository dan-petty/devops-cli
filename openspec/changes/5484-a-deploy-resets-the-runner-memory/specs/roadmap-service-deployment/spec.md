## ADDED Requirements

### Requirement: The example ConfigMap holds the runner memory limit
The example ConfigMap SHALL set `roadmap.implement.max_memory_limit` to 16Gi, with a comment that names the two out-of-memory kills of 2026-11-12 and 2026-11-13, and the render of the ConfigMap SHALL keep that value for every repository.

#### Scenario: The rendered example holds the limit
- **WHEN** a test renders the example ConfigMap for one repository with the GitHub App settings
- **THEN** the rendered config holds 16Gi as the runner memory limit and the service.repos of that repository

#### Scenario: The comment names the two kills
- **WHEN** a test reads the comment above the setting in the example ConfigMap
- **THEN** the comment names 2026-11-12, 2026-11-13 and the two killed Jobs
