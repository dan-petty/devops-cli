# Task: deploy-stack Applies the Monitoring Services Alloy, Grafana and Port-Forward Use (#912)

**Issue**: [#912](https://github.com/dan-petty/devops-cli/issues/912)
**Status**: Done
**Milestone**: v0.2.24
**Priority**: priority/p0-critical
**Scope**: scope/k8s

## Description
`devops k8s deploy-stack` applies only the root kustomization (`kubectl apply -k k8s/`, `stack_lifecycle.py:762`), which listed `namespaces.yaml`, `cloudflared`, `registry` and `monitoring/dashboards`. fdd4d0f (#734), which is not in v0.2.23, replaced kube-prometheus-stack and pointed three consumers at Services that only `k8s/monitoring/service-aliases.yaml` defines:
- **Alloy's Prometheus destination** (`k8s-monitoring-values.yaml:12`) and **Grafana's Prometheus datasource** (`grafana-values.yaml`) use `prometheus.monitoring.svc`. The `prometheus-community/prometheus` release creates `prometheus-server`.
- **`devops k8s port-forward`** targets `svc/kube-prometheus-grafana` and `svc/kube-prometheus-kube-prome-prometheus` (`networking.py:936-940`).

On a cluster built by v0.2.24's `deploy-stack` alone, no metric reached Prometheus, Grafana's Prometheus panels were empty, and port-forward failed. On homelab-k3s the `prometheus` Service exists only because it was applied by hand: it carries the `devops-cli-stack` label and no Helm ownership, and both kube-prometheus aliases are missing.

The root kustomization now lists `monitoring/service-aliases.yaml`. `kubectl kustomize k8s/` renders `prometheus`, `kube-prometheus-kube-prome-prometheus` and `kube-prometheus-grafana` in namespace `monitoring`. `devops k8s teardown-stack` (`kubectl delete -k k8s/`) now removes them too. Removing the two kube-prometheus aliases and their lookups stays with #818. `k8s/monitoring/networkpolicy.yaml` has never been applied by `deploy-stack`, in v0.2.23 or v0.2.24, and is filed separately.

## Acceptance Criteria
- [x] The root kustomization applies `monitoring/service-aliases.yaml`. `kubectl kustomize k8s/` renders the `prometheus`, `kube-prometheus-kube-prome-prometheus` and `kube-prometheus-grafana` Services in namespace `monitoring`, alongside `registry/registry`.
- [x] `test_deploy_stack_applies_the_monitoring_services_the_stack_addresses` (`tests/test_k8s_monitoring_integration.py`) collects the Services reachable from `k8s/kustomization.yaml`. It asserts that the hosts named by Alloy's Prometheus destination and Grafana's Prometheus datasource, and the monitoring Services `_collect_port_forward_services(["infra"], ...)` targets, are all among them. Against the previous root kustomization it reported all three Services missing.
- [x] The test reads only repository files, with no cluster or network.
- [x] `uv run devops ci` passes.
