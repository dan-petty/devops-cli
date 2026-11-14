# Design

## Decisions
- Pin `grafana-llm-app@1.2.0` in `k8s/monitoring/grafana-values.yaml` under `plugins`.
- Document routing Grafana LLM requests to `http://llm-gateway.llm.svc.cluster.local:4000/v1` targeting model `qwen3.8:27b`.

## Rejected alternatives
- Unpinned `grafana-llm-app`: Rejected because the Grafana chart disables automatic major updates and unpinned plugins stay at the version on the volume.
- Public provider endpoints: Rejected because the cluster provides an in-cluster zero-trust AI Gateway (`llm-gateway`).
