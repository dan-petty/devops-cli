# Proposal: #5710

## Why
Grafana 13 preinstalls `grafana-llm-app@1.2.0`, but lacks automated provisioning for the in-cluster LiteLLM AI Gateway and model `qwen3.8:27b`. Without plugin provisioning, an operator must enter the gateway URL and master key manually in the Grafana web console. Closes #5710.

## What Changes
Provision `grafana-llm-app` in `k8s/monitoring/grafana-values.yaml` using `extraObjects` and `extraConfigmapMounts`. Mount `apps.yaml` to `/etc/grafana/provisioning/plugins/apps.yaml` pointing to `http://llm-gateway.llm.svc.cluster.local:4000/v1` with model mapping for `qwen3.8:27b`. Inject `GF_LLM_GATEWAY_KEY` via `envValueFrom` in `grafana-values.yaml` from Secret `monitoring/grafana-admin` key `llm-gateway-key`. Add `llm-gateway-key` to `monitoring/grafana-admin` in `src/devops_cli/k8s/cluster_secrets.py`. Update `k8s/README.md` and integration tests.

## Capabilities
- `grafana-plugins`
- `stack-credential-sync`

## Impact
Grafana provisions and enables `grafana-llm-app` automatically at startup. The plugin routes requests to LiteLLM Gateway using model `qwen3.8:27b`.

## Feasibility
The Grafana Helm chart supports `extraObjects`, `extraConfigmapMounts`, and `envValueFrom`. The secret management table already manages `monitoring/grafana-admin` and `llm_gateway_master_key`. The change fits one pull request.

## Existing Tool Considered
Grafana native plugin provisioning (`/etc/grafana/provisioning/plugins/apps.yaml`) and `$__env{GF_LLM_GATEWAY_KEY}` variable expansion.
