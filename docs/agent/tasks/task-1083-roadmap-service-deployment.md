# Task: Roadmap service runs in the cluster devops namespace (#1083)

**Issue**: [#1083](https://github.com/dan-petty/devops-cli/issues/1083)
**Status**: Done
**Milestone**: v0.2.26
**Priority**: priority/p1-high
**Scope**: type/feature, scope/k8s, priority/p1-high

## Description
Deploys the roadmap service as a single-replica `Recreate` Deployment in namespace `devops` running `devops serve --service --host 0.0.0.0 --port 8000 --workers 1` with a dedicated 1Gi `local-path` PersistentVolumeClaim mounted at `/home/devops`.

Exposes the service externally strictly on `POST /webhooks/github` through a Traefik Ingress with restricted entrypoints and path scoping. Isolates traffic via `roadmap-service-ingress` NetworkPolicy admitting only Traefik from `kube-system` and Prometheus scraping from `monitoring` on TCP 8000, and enables Prometheus cross-namespace scraping via an egress rule in `k8s/monitoring/networkpolicy.yaml`. Integrates `service.webhook_secrets` (`DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS`) into the cluster secrets push table with rollout restart targeting on `deployment/roadmap-service`.

## Acceptance Criteria
- [x] Manifests tested in `tests/test_k8s_roadmap_service.py`:
  - 1 replica, `Recreate`, container `service`, and args containing `--service`, `--host 0.0.0.0` and `--workers 1`.
  - Restricted security context (`runAsNonRoot: true`, `readOnlyRootFilesystem: true`, drop ALL capabilities).
  - `envFrom` is only secretRef `devops-cli`, with no literal credential `value`.
  - The PVC is mounted at `/home/devops`, `DEVOPS_CLI_DATA_DIR` starts with it, and the PVC's sync-options contain `Prune=false` and `Delete=false`.
  - Annotations name port 8000 (`prometheus.io/scrape: "true"`, `prometheus.io/port: "8000"`).
  - The Ingress has class `traefik`, one host and one `Exact` path, `/webhooks/github`.
  - `roadmap-service-ingress` admits only Traefik in kube-system and namespace `monitoring`, on 8000.
  - `k8s/monitoring/networkpolicy.yaml` has an egress rule to `devops` on 8000.
  - The ConfigMap validates as `Settings` with non-empty `service.repos` and `service.machine_account`.
  - `k8s/devops/kustomization.yaml` lists `roadmap-service`, and `k8s/devops/roadmap-service/kustomization.yaml` lists exactly the five manifests, each of which exists.
- [x] The push-secrets table has the webhook entry, optional and without a generator, with its env name from `OPTION_TO_ENV_VAR`. `devops/devops-cli` lists `deployment/roadmap-service` as a restart target. Tested in `tests/test_k8s_push_secrets.py`.
- [x] `changelog.d/1083.md` exists, `CHANGELOG.md` and `docs/ROADMAP.md` remain untouched, and `devops pr check-readiness` passes.
- [x] Fast in-gate tests total under 1 s and open no network sockets. `uv run devops ci` passes.
- Pending a person: live rollout and exposure verification on `homelab-k3s`:
  - `kubectl -n devops rollout status deploy/roadmap-service --timeout=180s` succeeds.
  - `kubectl -n devops get deploy roadmap-service -o jsonpath='{.spec.replicas} {.spec.strategy.type} {.status.readyReplicas}'` prints `1 Recreate 1`.
  - `curl -s -o /dev/null -w '%{http_code}\n' https://hooks.<domain>/health` prints `404` (or `302` under Access), never `200`.
  - `curl -s -o /dev/null -w '%{http_code}\n' -X POST https://hooks.<domain>/webhooks/github -d '{}'` prints `401`.
  - `devops prometheus query 'up{namespace="devops"}'` returns one series with value `1`.

## Deliverables
- [x] `k8s/devops/roadmap-service/deployment.yaml`: Deployment manifest with service mode arguments, security context, secretRef, volume mounts, probes, and prometheus annotations.
- [x] `k8s/devops/roadmap-service/pvc.yaml`: 1Gi local-path PVC with Argo CD Prune/Delete preservation.
- [x] `k8s/devops/roadmap-service/service.yaml`: ClusterIP service on port 8000.
- [x] `k8s/devops/roadmap-service/ingress.yaml`: Traefik Ingress routing `/webhooks/github` (Exact path).
- [x] `k8s/devops/roadmap-service/networkpolicy.yaml`: Ingress NetworkPolicy allowing Traefik and Prometheus on TCP 8000.
- [x] `k8s/devops/roadmap-service/kustomization.yaml`: Kustomization defining the roadmap service resources.
- [x] `k8s/devops/kustomization.yaml`: Added `roadmap-service` to resources list.
- [x] `k8s/devops/configmap.yaml`: Added `service.repos` and `service.machine_account`.
- [x] `k8s/monitoring/networkpolicy.yaml`: Added egress rule to namespace `devops` on TCP 8000.
- [x] `src/devops_cli/k8s/cluster_secrets.py`: Added `DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS` entry and `deployment/roadmap-service` restart target to `devops/devops-cli`.
- [x] `k8s/README.md`: Added Roadmap service runbook and updated cluster secret and directory structure documentation.
- [x] `tests/test_k8s_roadmap_service.py`: Added comprehensive manifest validation tests.
- [x] `tests/test_k8s_push_secrets.py`: Updated cluster secrets table tests.
- [x] `tests/test_k8s_devops_runtime.py`: Updated resources assertion to include `roadmap-service`.
- [x] `changelog.d/1083.md`: Added release changelog fragment.
