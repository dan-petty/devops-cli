# Spec Delta

## MODIFIED Requirements

### Requirement: A local gateway group counts as local
`is_local` SHALL count a gateway reply as local when it names a local group of `k8s/llm/gateway/config.yaml`, a model with the `local/` prefix, or a model with the `ollama/`, `ollama_chat/` or `ollama:` prefix. It SHALL keep a hosted group hosted.

#### Scenario: A local fallback
- **WHEN** a gateway reply names `ollama_chat/qwen3.8:27b`
- **THEN** `is_local` is true and the record holds the source `local`

#### Scenario: A local group outside the virtual models
- **WHEN** a gateway reply names `devops-review`, `devops-background`, `devops-triage`
- **THEN** `is_local` is true

#### Scenario: A local group with a local prefix
- **WHEN** a gateway reply names `local/devops-chat`, `local/devops-coder` or `local/qwen3.8:27b`
- **THEN** `is_local` is true

#### Scenario: A hosted group
- **WHEN** a gateway reply names `claude-sonnet-5-5`
- **THEN** `is_local` is false

#### Scenario: A hosted group with a provider prefix
- **WHEN** a gateway reply names `anthropic/claude-sonnet-5-5`
- **THEN** `is_local` is false

## ADDED Requirements

### Requirement: Spend and local savings follow the backend route
All traffic routed to a `*.local` `api_base` SHALL count as local savings. All requests not routed to a `*.local` `api_base` SHALL count as spend.

#### Scenario: Traffic routed to a cluster local backend
- **WHEN** a request has `served_by` set to `http://ollama-48gib-fast.llm.svc.cluster.local:11434`
- **THEN** `is_local` is true and the tokens carry `local` `true`

#### Scenario: Traffic routed to a cloud backend
- **WHEN** a request has `served_by` set to an RFC 1918 private address or an internal domain
- **THEN** `is_local` is false, `devops_cli_ai_spend_usd_total` records the spend, and the tokens carry `local` `false`
