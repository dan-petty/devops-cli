# Spec Delta

## MODIFIED Requirements

### Requirement: Spend and local savings follow the backend route
All traffic routed to a `*.local` `api_base` SHALL count as local savings, unless `served_by` names the AI gateway proxy endpoint itself. All requests not routed to a `*.local` `api_base` SHALL count as spend. When `served_by` names the gateway proxy endpoint, model routing rules SHALL decide whether the call is local savings or spend.

#### Scenario: Traffic routed to a cluster local backend
- **WHEN** a request has `served_by` set to `http://ollama-48gib-fast.llm.svc.cluster.local:11434`
- **THEN** `is_local` is true and the tokens carry `local` `true`

#### Scenario: Traffic routed to a cloud backend
- **WHEN** a request has `served_by` set to an RFC 1918 private address or an internal domain
- **THEN** `is_local` is false, `devops_cli_ai_spend_usd_total` records the spend, and the tokens carry `local` `false`

#### Scenario: Request names the gateway proxy endpoint as served_by
- **WHEN** a request names the gateway proxy endpoint `http://llm-gateway.llm.svc.cluster.local:4000/v1` in `served_by` for a hosted model
- **THEN** `is_local` is false, `devops_cli_ai_spend_usd_total` records the spend, and the tokens carry `local` `false`
