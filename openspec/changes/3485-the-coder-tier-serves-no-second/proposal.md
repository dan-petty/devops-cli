# Proposal

## Why

The ollama-48gib tier can still evict its only model when a client calls the tier directly with another model name, and an eviction loses the KV cache for 55 to 330 s. No alert tells a person, because the eviction is a Loki log line and no Prometheus metric names it (#3485).

## What Changes

- Add `k8s/logging/loki-rules.yaml` with the Loki ruler group `ollama-tier-evictions` and the alert `OllamaTierEvictions`, which counts the eviction lines of `{service_name="ollama-48gib"}` over a window and fires above a threshold.
- Add the ruler config to `k8s/logging/loki-values.yaml`: local rule storage at `/etc/loki/rules`, a writable rule path, `alertmanager_url` of `prometheus-alertmanager.monitoring.svc.cluster.local:9093`, and the ConfigMap and emptyDir volumes of the single binary.
- List `loki-rules.yaml` in `k8s/logging/kustomization.yaml` so Application `logging` applies the ConfigMap.
- Add an egress rule to `k8s/logging/networkpolicy.yaml` for TCP 9093 to `monitoring`, and an ingress rule to `k8s/monitoring/networkpolicy.yaml` for TCP 9093 from `logging`.
- Extend `tests/prometheus/test_k8s_monitoring_alerting.py` with the ruler settings, the mounted rule file, the alert over a fixture of log lines, and the two network policy peers, and update `tests/commands/k8s/test_k8s_logging_stack.py` for the Alertmanager egress rule.
- Document the rule, its threshold and the Alertmanager path in `k8s/README.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `loki-ruler-alerts`: The Loki ruler fires on Ollama tier evictions, The Loki ruler reaches Alertmanager through the network policies

### Modified Capabilities

None.

## Impact

- Code: `k8s/logging/loki-rules.yaml`, `k8s/logging/loki-values.yaml`, `k8s/logging/kustomization.yaml`, `k8s/logging/networkpolicy.yaml`, `k8s/monitoring/networkpolicy.yaml`
- Documents: `k8s/README.md`
- Tests: `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/commands/k8s/test_k8s_logging_stack.py`, `tests/fixtures/logs/ollama_evictions.yaml`

## Feasibility

- `probes` confirms the premise path word for word: "The path `k8s/llm/profiles/ollama-profiles.yaml` is a file of the staging commit."
- `probes` confirms the files this change edits word for word: "The path `k8s/logging/loki-values.yaml` is a file of the staging commit.", "The path `k8s/logging/networkpolicy.yaml` is a file of the staging commit." and "The path `k8s/monitoring/networkpolicy.yaml` is a file of the staging commit."
- The tier can still evict: `k8s/llm/profiles/ollama-profiles.yaml` records that `# one of those names makes Ollama unload qwen3.8:27b and load it. Change these settings and the` and `# gateway routes together.`
- No ruler runs: `read_file` of `k8s/logging/loki-values.yaml` lines 100-140 showed the values end at `backend.replicas` with no `loki.ruler` block, and the rules sidecar is off at `k8s/logging/loki-values.yaml:117:# Disable rule sidecar container in dev-mode Monolithic cluster to eliminate k8s API watch crashloop`.
- The sidecar stays off for a stated reason: `k8s/logging/loki-values.yaml:122:# With the rules sidecar off, no Loki pod calls the Kubernetes API, so none mounts a ServiceAccount`.
- The logging perimeter admits only intra-namespace and DNS egress: the two peers after `k8s/logging/networkpolicy.yaml:63:egress:` are a pod selector of the namespace and CoreDNS on 53.
- The monitoring perimeter admits no `logging` peer: `k8s/monitoring/networkpolicy.yaml:13:ingress:` holds the namespace, Traefik and the OTel collector, and `k8s/monitoring/networkpolicy.yaml:53:# 3. Allow OpenTelemetry collector to push metrics (9090) and profiles (4040)` names the last of them.
- The Alertmanager address is already served: `k8s/monitoring/grafana-values.yaml:134:url: http://prometheus-alertmanager.monitoring.svc.cluster.local:9093`.
- No Prometheus series names ollama: the allow list of the alert tests starts at `tests/prometheus/test_k8s_monitoring_alerting.py:113:SERVED_SERIES = frozenset(`, and its entries name no ollama metric.
- The existing rule tests cover PromQL only: `tests/prometheus/test_k8s_monitoring_alerting.py:106:RULE_GROUP_TESTS = (` lists the promtool rule tests, so the LogQL rule needs a test of its own.
- `list_files` of `k8s/logging` showed `kustomization.yaml`, `loki-values.yaml` and `networkpolicy.yaml`, and `k8s/logging/kustomization.yaml:4:resources:` lists `networkpolicy.yaml` only, so the new ConfigMap joins it.
- `list_files` of `tests/prometheus` showed `tests/prometheus/test_k8s_monitoring_alerting.py`, and `list_files` of `tests/fixtures` showed no `logs` folder, so the fixture file is new.
- First check against the real system: `uv run devops k8s validate k8s/logging` confirms the ConfigMap and both NetworkPolicies, and `kubectl -n logging get configmap loki-rules -o yaml` confirms the rule file that Loki mounts.
- First check against the real system: `kubectl -n logging logs statefulset/loki -c loki | grep -i ruler` shows the ruler loading the group, and `curl -s http://localhost:3100/loki/api/v1/rules` over `kubectl -n logging port-forward statefulset/loki 3100:3100` lists `OllamaTierEvictions`.
- Precondition: the call `uv run devops k8s validate k8s/logging` needs a checkout of the repository and a network for the schema fetch of kubeconform.
- Precondition: the calls `kubectl -n logging get configmap loki-rules` and `kubectl -n logging logs statefulset/loki` need a client of the cluster.
- Precondition: the call `curl http://localhost:3100/loki/api/v1/rules` needs a network to the Loki port-forward.

## Existing Tool Considered

The Loki ruler and Alertmanager cover the need. Loki already stores the log lines, its ruler evaluates LogQL, and Alertmanager already receives the cluster's alerts. `promtool` cannot parse a LogQL expression, and Loki ships no offline rule unit test, so the test in `tests/prometheus/test_k8s_monitoring_alerting.py` reads the rule and applies its selector, filter, window and threshold to a fixture of log lines.

## Dependencies

None.
