## MODIFIED Requirements

### Requirement: The AI spend dashboard charts the p95 gateway slot wait by outcome
`k8s/devops/dashboards/ai-spend.json` SHALL have a panel that charts the 0.95 quantile of `devops_cli_ai_gateway_slot_wait_seconds` summed by `outcome`, and the count of its observations by `outcome`.

#### Scenario: The dashboard queries the slot wait
- **WHEN** a test reads the queries of `ai-spend.json`
- **THEN** one query is the 0.95 `histogram_quantile` of `devops_cli_ai_gateway_slot_wait_seconds` summed by `outcome`
- **AND** every query names only series in `INSTRUMENTS`
