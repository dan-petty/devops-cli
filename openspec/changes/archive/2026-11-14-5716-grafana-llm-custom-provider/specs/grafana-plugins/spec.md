## MODIFIED Requirements

### Requirement: Grafana provisions grafana-llm-app for LiteLLM gateway
The Grafana values SHALL configure `extraConfigmapMounts` and `extraObjects` to provision `grafana-llm-app` at `/etc/grafana/provisioning/plugins/apps.yaml`. The provisioning file SHALL configure provider `custom`, url `http://llm-gateway.llm.svc.cluster.local:4000`, models `qwen3.8:27b`, and API key `$__env{GF_LLM_GATEWAY_KEY}`. The values SHALL map `GF_LLM_GATEWAY_KEY` to Secret `grafana-admin` key `llm-gateway-key`.

#### Scenario: Plugin provisioning in Grafana values
- **WHEN** `k8s/monitoring/grafana-values.yaml` is read
- **THEN** `extraConfigmapMounts` mounts `apps.yaml` to `/etc/grafana/provisioning/plugins/apps.yaml`
- **AND** `extraObjects` defines ConfigMap `grafana-llm-plugin` targeting LiteLLM gateway and `qwen3.8:27b` with provider `custom` and url `http://llm-gateway.llm.svc.cluster.local:4000`
- **AND** `envValueFrom` maps `GF_LLM_GATEWAY_KEY` to `grafana-admin` `llm-gateway-key`
