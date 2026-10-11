# Task: Remove monitoring alias Services and direct consumers to Helm chart Services (#1104)

**Issue**: [#1104](https://github.com/dan-petty/devops-cli/issues/1104)
**Status**: Done
**Feasibility**: Verified against local manifests, Helm chart definitions, and codebase search: Prometheus chart 29.35.0 deploys Service `prometheus-server` on port 9090; Grafana chart creates Service `grafana` on port 80; plain manifest `service-aliases.yaml` declares unpinned Services that collide with Helm release ownership during `devops k8s deploy-stack`.

## Deliverables
- [x] Deleted plain manifest `k8s/monitoring/service-aliases.yaml`, removed its entry from `k8s/kustomization.yaml`, and updated references in `k8s/monitoring/kustomization.yaml` and `k8s/README.md`.
- [x] Updated all consumers of Prometheus to point directly at `prometheus-server.monitoring.svc.cluster.local:9090`:
  - Alloy `localPrometheus` destination URL in `k8s/monitoring/k8s-monitoring-values.yaml`.
  - Grafana Prometheus datasource URL in `k8s/monitoring/grafana-values.yaml`.
  - Ingress backend service name in `k8s/ingress/ingress-routes.yaml`.
  - TLS SAN list in `src/devops_cli/crypto/tls_certificates.py`.
- [x] Updated `devops k8s configure-urls` and `devops k8s port-forward` to target `svc/grafana` (port 80) and `svc/prometheus-server` (port 9090), removing legacy `kube-prometheus-*` aliases.
- [x] Removed `kube-prometheus-stack-grafana` from candidate secrets list in `fetch_grafana_password`.
- [x] Added guard test in `tests/test_k8s_monitoring_integration.py` ensuring no Service in kustomize base or plain manifests applied by `deploy-stack` sits in a Helm-managed namespace without an explicit owned exemption.
- [x] Added `{group: argoproj.io, kind: AppProject, name: default}` to `orphanedResources.ignore` in `k8s/argocd/apps/projects.yaml` and updated `tests/test_k8s_argocd_apps.py`.
- Pending a person: once after deploy on live cluster:
  `kubectl delete service -n monitoring prometheus kube-prometheus-kube-prome-prometheus kube-prometheus-grafana`
