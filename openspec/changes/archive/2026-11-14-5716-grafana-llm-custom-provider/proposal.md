# Proposal: #5716

## Why
The Grafana LLM plugin configures `provider: openai` and appends `/v1` to the gateway URL.
This makes Grafana use standard OpenAI defaults and creates an invalid path `/v1/v1`. Closes #5716.

## What Changes
Configure `provider: custom` and `url: http://llm-gateway.llm.svc.cluster.local:4000` in `k8s/monitoring/grafana-values.yaml`. Update the integration tests and documentation.

## Capabilities
- `grafana-plugins`

## Impact
Grafana displays the Custom API provider in its web interface. The plugin connects to the in-cluster LiteLLM gateway without duplicate path prefixes.

## Feasibility
The `grafana-llm-app` plugin supports `provider: custom` and joins `/v1` to the base URL automatically. The change modifies only Kubernetes values, tests, and documentation.

## Existing Tool Considered
Grafana native plugin provisioning.
