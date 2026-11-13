## MODIFIED Requirements

### Requirement: The devops-cli dashboard charts the series of the Service
The dashboard `k8s/devops/dashboards/devops-cli.json` SHALL have the row "Roadmap Service". The panels of the row SHALL read each `devops_cli_service_*` series that `src/devops_cli/config/constants.py` names.

#### Scenario: Each series has a panel
- **WHEN** the queries of the row "Roadmap Service" are read
- **THEN** each `CONST_SERVICE_METRIC_*` series is in a query of the row

#### Scenario: The budget panel shows the spend beside the limit
- **WHEN** the panel "Service GitHub Budget" is read
- **THEN** it has one query for `devops_cli_service_budget_spent_requests` and one for `devops_cli_service_budget_limit_requests`
