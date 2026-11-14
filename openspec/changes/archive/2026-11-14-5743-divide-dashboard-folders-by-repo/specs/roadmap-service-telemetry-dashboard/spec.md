## MODIFIED Requirements

### Requirement: The roadmap service telemetry dashboard charts service state and job success
The dashboard `k8s/devops/dashboards/roadmap-service-telemetry.json` SHALL exist with uid `devops-roadmap-service-telemetry` and title `Roadmap Service Telemetry`. It SHALL contain rows for "Roadmap Service", "Alternatives Check", and "Roadmap Job Success". It SHALL define a `$repo` template variable to filter telemetry by service repository.

#### Scenario: The dashboard is loaded
- **WHEN** the dashboard `roadmap-service-telemetry.json` is read
- **THEN** its uid is `devops-roadmap-service-telemetry`
- **AND** it contains rows "Roadmap Service", "Alternatives Check", and "Roadmap Job Success"
- **AND** it defines top-level links pointing to `devops-cli-telemetry` and `devops-ai-rag`
- **AND** it defines a template variable `repo`
