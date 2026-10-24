# Tasks

## 1. Server-side apply of the homelab Applications

- [x] Add the failing test that the Applications `devops` and `ingress`, and no other Application, have `ServerSideApply=true` in their sync-options annotation, and that `cluster` names `argocd-controller` as its client-side apply migration manager (`uv run devops ci test tests/test_k8s_argocd_apps.py`).
- [x] Add the annotations to `k8s/argocd/apps/devops.yaml`, `k8s/argocd/apps/ingress.yaml` and `k8s/argocd/bootstrap/cluster.yaml` (`uv run devops ci test tests/test_k8s_argocd_apps.py tests/test_k8s_argocd_gate.py tests/test_k8s.py`).
- [x] Tell in `k8s/README.md`, GitOps, Homelab Values at Deploy Time, why a sync keeps the overrides, which actions remove them, and the commands that set them again, and regenerate the documentation (`uv run devops docs generate --sync-readme` and `uv run devops docs check`).

## 2. Alert on a placeholder host

- [x] Add the failing tests for the rule `IngressServesPlaceholderHost`, its series `kube_ingress_path`, and its host pattern against every Ingress host in git (`uv run devops ci test tests/test_k8s_monitoring_alerting.py`).
- [x] Add `kube_ingress_path` to the kube-state-metrics `includeMetrics` in `k8s/monitoring/k8s-monitoring-values.yaml`, and the rule to `homelab-services` in `k8s/monitoring/prometheus-values.yaml` (`uv run devops ci test tests/test_k8s_monitoring_alerting.py tests/test_k8s_monitoring_integration.py tests/test_k8s_monitoring_dashboards.py tests/test_stack_dashboards.py`).
- [x] Add the alert to the table in `k8s/README.md`, Alerting (`uv run devops docs check`).

## 3. Checks

- [x] Run the static checks (`uv run devops ci --only lint,format,typecheck,docs,openspec,security`).
- [x] Run the repository-wide tests (`uv run devops ci test tests/test_swallowed_failures_ratchet.py tests/test_architectural_invariants.py`).
- [x] Run the changed tests with no developer tool on `PATH` (`env PATH=/usr/bin:/bin .venv/bin/python -m pytest tests/test_k8s_argocd_apps.py tests/test_k8s_monitoring_alerting.py`).

Pending a person: after the merge, when `cluster` has synced the two Applications, check that `devops argo cd apps status cluster` is Synced with no ComparisonError, that `kubectl -n argocd get application devops ingress --show-managed-fields -o yaml` shows an `argocd-controller` entry with operation `Apply`, no `argocd-controller` entry with operation `Update`, and `spec.source.kustomize` with the host patches, and that `IngressServesPlaceholderHost` does not fire.
Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
