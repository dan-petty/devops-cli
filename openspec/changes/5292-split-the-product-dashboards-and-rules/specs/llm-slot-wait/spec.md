## MODIFIED Requirements

### Requirement: The AI spend dashboard charts the p95 Ollama slot wait by priority
`k8s/devops/dashboards/ai-spend.json` SHALL have a panel that charts the 0.95 quantile of `devops_cli_ai_ollama_slot_wait_seconds` summed by `priority`, and the count of its observations by `priority`.

#### Scenario: The dashboard queries the slot wait
- **WHEN** a test reads the queries of `ai-spend.json`
- **THEN** one query is the 0.95 `histogram_quantile` of `devops_cli_ai_ollama_slot_wait_seconds` summed by `priority`
- **AND** every query names only series in `INSTRUMENTS`
