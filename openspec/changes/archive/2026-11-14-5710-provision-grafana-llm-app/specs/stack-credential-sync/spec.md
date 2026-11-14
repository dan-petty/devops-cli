## ADDED Requirements

### Requirement: Secret monitoring/grafana-admin holds a llm-gateway-key entry
Secret `monitoring/grafana-admin` SHALL hold entry `llm-gateway-key` from keyring source `llm_gateway_master_key` with generator prefix `sk-`.

#### Scenario: Secret entry in cluster secret table
- **WHEN** the cluster secret table is read
- **THEN** Secret `monitoring/grafana-admin` defines `llm-gateway-key` with keyring source `llm_gateway_master_key`
