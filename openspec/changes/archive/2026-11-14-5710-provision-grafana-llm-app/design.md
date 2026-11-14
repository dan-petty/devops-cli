# Design: #5710

## Context
Grafana 13 preinstalls `grafana-llm-app` at version 1.2.0. The plugin connects to an OpenAI-compatible endpoint to provide LLM capabilities across Grafana. The cluster hosts LiteLLM Gateway in namespace `llm` at `http://llm-gateway.llm.svc.cluster.local:4000/v1`, serving model `qwen3.8:27b`. Egress is allowed by network policy `monitoring-default-perimeter`.

## Decisions

### 1. Provision apps.yaml via Helm extraObjects and extraConfigmapMounts
- Define ConfigMap `grafana-llm-plugin` in `extraObjects` of `k8s/monitoring/grafana-values.yaml`.
- Mount `apps.yaml` to `/etc/grafana/provisioning/plugins/apps.yaml` using `extraConfigmapMounts`.
- Configure provider `openai`, url `http://llm-gateway.llm.svc.cluster.local:4000/v1`, models `base: qwen3.8:27b`, `large: qwen3.8:27b`, and API key `$__env{GF_LLM_GATEWAY_KEY}`.

### 2. Map GF_LLM_GATEWAY_KEY from Secret grafana-admin
- Add SecretEntry `llm-gateway-key` to `monitoring/grafana-admin` in `src/devops_cli/k8s/cluster_secrets.py`.
- Source the key from `_LLM_GATEWAY_KEY` (`llm_gateway_master_key` in the keyring).
- Map `GF_LLM_GATEWAY_KEY` in `envValueFrom` of `grafana-values.yaml`.

## Rejected Alternatives
- Web UI configuration: Rejected because manual steps break reproducible GitOps deployments.
- Hardcoded API key: Rejected because AGENTS.md rule 10 forbids storing credentials in git.
