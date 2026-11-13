## MODIFIED Requirements

### Requirement: eval grades reads the result lines with metric instant queries
`devops roadmap eval grades` SHALL read the result lines with LogQL metric instant queries on `/loki/api/v1/query` of the Loki that `--loki-url` or `loki.url` names. `--repo` SHALL put a match of the repository in each query. `--dry-run` SHALL send no request and print each query.

#### Scenario: The dry run sends no request
- **WHEN** a person runs `devops roadmap eval grades --dry-run`
- **THEN** the command sends 0 requests and prints each LogQL query with the Loki address of `loki.url`

#### Scenario: Loki refuses a query
- **WHEN** Loki answers a query with HTTP 400
- **THEN** the report stops with `ServiceRequestError` and the status 400
