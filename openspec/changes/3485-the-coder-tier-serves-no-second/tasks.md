# Tasks

## 1. Add the Loki ruler rule and its Alertmanager path

Reads: `k8s/logging/loki-values.yaml`, `k8s/logging/networkpolicy.yaml`, `k8s/monitoring/networkpolicy.yaml`, `k8s/logging/kustomization.yaml`, `k8s/monitoring/grafana-values.yaml`. Changes: `k8s/logging/loki-rules.yaml` (new), `k8s/logging/loki-values.yaml`, `k8s/logging/kustomization.yaml`, `k8s/logging/networkpolicy.yaml`, `k8s/monitoring/networkpolicy.yaml`, `k8s/README.md`.

- [ ] 1.1 Create the ConfigMap `loki-rules` in the `logging` namespace with the key `ollama-evictions.yaml`. Its group `ollama-tier-evictions` holds the alert `OllamaTierEvictions` with `expr: sum(count_over_time({service_name="ollama-48gib"} |= "model predicted to exceed available memory, evicting" [1h])) > 0`, `for: 5m`, the label `severity: warning`, and a description that names the tier and the KV cache loss. Add `loki.ruler` to `k8s/logging/loki-values.yaml` with `storage.type: local`, `storage.local.directory: /etc/loki/rules`, `rule_path: /tmp/loki/rules`, `alertmanager_url: http://prometheus-alertmanager.monitoring.svc.cluster.local:9093`, `ring.kvstore.store: inmemory` and `enable_api: true`. Add `singleBinary.extraVolumes` for the ConfigMap and an emptyDir, and `singleBinary.extraVolumeMounts` at `/etc/loki/rules/fake` and `/tmp/loki`. List `loki-rules.yaml` in `k8s/logging/kustomization.yaml`. Add an egress rule to `k8s/logging/networkpolicy.yaml` to the `monitoring` namespace on TCP 9093, and an ingress rule to `k8s/monitoring/networkpolicy.yaml` from the `logging` namespace on TCP 9093
  - Verification: `uv run devops ci test tests/invariants/test_k8s_manifests.py` passes
- [ ] 1.2 Edit `k8s/README.md` with the rule, its window and threshold, and the ruler to Alertmanager path
  - Verification: `uv run devops ci docs` passes

## 2. Test the eviction alert, its ruler settings and its network peers

Reads: `tests/prometheus/test_k8s_monitoring_alerting.py`, `k8s/logging/loki-values.yaml`, `k8s/logging/loki-rules.yaml`, `k8s/logging/networkpolicy.yaml`, `k8s/monitoring/networkpolicy.yaml`. Changes: `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/logs/ollama_evictions.yaml` (new).

- [ ] 2.1 Add `test_the_loki_ruler_fires_on_tier_evictions` to `tests/prometheus/test_k8s_monitoring_alerting.py`. It reads `k8s/logging/loki-rules.yaml` and `k8s/logging/loki-values.yaml`, asserts the ruler storage, rule path and `alertmanager_url`, asserts that the single binary mounts the ConfigMap at `/etc/loki/rules/fake`, and takes the expression of `OllamaTierEvictions`. It parses the selector, the `|=` literal, the window and the threshold, then counts the fixture lines that hold the literal inside the window: the alert fires above the threshold and stays quiet at or below it. Add `test_the_logging_perimeter_reaches_alertmanager_on_9093` over both network policy files: one egress rule to `monitoring` on 9093, one ingress rule from `logging` on 9093, and no other port for that pair. The fixture `tests/fixtures/logs/ollama_evictions.yaml` holds a stream name, a window and lines with offsets: a case above the threshold, a case at it, and a case with no eviction line
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes

## Criteria

- Group 1: A Loki ruler rule fires when `ollama-48gib-fast` logs more eviction lines than a configured threshold in a window, and the alert reaches Alertmanager.
- Group 2: A test holds an alert on tier evictions over a threshold.
