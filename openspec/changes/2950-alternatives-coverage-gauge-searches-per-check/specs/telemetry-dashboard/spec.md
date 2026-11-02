## ADDED Requirements

### Requirement: Alternatives coverage panel
The Roadmap dashboard SHALL hold a panel that shows the gauge `devops_cli_roadmap_alternatives_unchecked_items`, the gauge `devops_cli_roadmap_alternatives_oldest_check_age_seconds` and the histogram `devops_cli_roadmap_alternatives_searches`.

#### Scenario: The panel queries the three instruments
- **WHEN** The dashboard check reads `k8s/monitoring/dashboards/devops-cli.json`
- **THEN** the panel holds a query for each of the three instruments and every query names a declared instrument
