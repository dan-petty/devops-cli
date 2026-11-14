# Proposal: #5696

## Why
Grafana 13 in the cluster lacks the `grafana-llm-app` plugin. Operators cannot use LLM-assisted observability features such as panel explanations and query generation. Closes #5696.

## What Changes
Add `grafana-llm-app@1.2.0` to the pinned `plugins` list in `k8s/monitoring/grafana-values.yaml`. Update `k8s/README.md` to document the plugin configuration for the in-cluster LiteLLM AI Gateway.

## Capabilities
- `grafana-plugins`

## Impact
Grafana downloads and installs `grafana-llm-app@1.2.0` at container start. The change requires no schema migration.

## Feasibility
`https://grafana.com/api/plugins/grafana-llm-app/versions` confirms that release 1.2.0 requires `grafanaDependency: >=13.0.0-0`. Grafana in the cluster runs version 13.3.1. Egress to the in-cluster LiteLLM Gateway on port 4000 is permitted by `k8s/monitoring/networkpolicy.yaml`. The change fits one pull request.

## Existing Tool Considered
The Grafana LLM plugin (`grafana-llm-app`, Apache-2.0, Grafana Labs) is the supported LLM extension point for Grafana.
