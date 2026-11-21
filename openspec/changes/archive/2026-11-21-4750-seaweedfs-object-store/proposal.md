# Proposal: #4750

## Why

The cluster has no object store (#4750). The off-node backups of #2144 and #3741, the project review reports and later the Argo Workflows artifacts need an S3 target that keeps a copy of each object on a node other than its source node. `kubectl get crd` lists no object store, and 19 `local-path` volumes have no backup. The owner asks for a permissive license (decision 1 of #4742), so the store is SeaweedFS with the SeaweedFS operator (both Apache-2.0).

## What Changes

- Add namespace `object-store` to `k8s/namespaces.yaml` with Pod Security `restricted` and `Prune=false,Delete=false`.
- Add the Argo CD Application `seaweedfs-operator` (chart `seaweedfs-operator` 0.1.48 of `https://seaweedfs.github.io/seaweedfs-operator`, app 1.0.45, CRDs from the chart, sync-wave `-1`, server-side apply) with its values in `k8s/object-store/operator-values.yaml`, and the Application `object-store` for `k8s/object-store/`. Add the chart repository and namespace `object-store` to the AppProject `homelab`, and the two pushed Secrets to its orphan ignore list.
- Add `k8s/object-store/seaweed.yaml`, one `Seaweed` CR on `chrislusf/seaweedfs:4.54` pinned by digest: 3 masters (replication `001`, `volumeSizeLimitMB` 1000, `copy_2 = 2`, `-telemetry=false`, a 1Gi `fast-nvme` claim each), 3 volume servers (300Gi `fast-nvme` claims, one per node, `maxVolumeCounts` 300, `minFreeSpacePercent` 10), 2 filers (leveldb2 on 10Gi `fast-nvme` claims, no S3), the standalone S3 gateway with 2 replicas on 8333, 1 admin with `credentialsSecret` `seaweedfs-admin`, and 1 worker (vacuum, volume balance, admin script, S3 lifecycle). JWT signing is on for volume and filer writes. Iceberg, Lance, the IAM API, STS, OIDC, SFTP, WebDAV and S3 Vectors stay off. Each component has a restricted security context, a metrics port and a ServiceMonitor that the operator makes, and a PodDisruptionBudget in `k8s/object-store/poddisruptionbudgets.yaml`.
- Add the NetworkPolicies `object-store-perimeter` and `object-store-operator`: only the worker pods reach the admin gRPC port 33646, a namespace with the label `backup-client: "true"` reaches the S3 port 8333, namespace `monitoring` reaches the metrics port, the pods have no internet egress, and only the operator reaches the Kubernetes API.
- Add the `CLUSTER_SECRETS` rows `object-store/seaweedfs-admin` (a literal user and a generated password under the keyring-only key `seaweedfs_admin_password`) and `object-store/seaweedfs-s3` (an identities file with no identity, so the S3 gateway refuses each request until an identity exists), both with stack `infra`.
- `devops k8s deploy-stack --stack infra` installs the operator chart into `object-store` after cert-manager and applies `k8s/object-store` after the charts (`HELM_REPOS_BY_STACK`, `HELM_RELEASES_BY_STACK`, `POST_HELM_BY_STACK`).
- Add the `k8s` row module `tests/gate/k8s_checks/object_store.py`: the namespace, the two Applications, the AppProject, the release and chart floors, the store layout, the optional features, the placement, the perimeter, the Secret gate, the ServiceMonitors, the budgets, the request sum, the Ingress hosts and the forbidden field `fs.mergeVolumes`. The data safety check also covers a `Seaweed` CR.
- Add the alert group `seaweedfs` (no leader, under-replicated volumes, a volume server down, read-only volumes, low volume disk) and the SeaweedFS dashboard of the pinned tag to `k8s/monitoring/`.
- Add the build test `k8s/object-store/build-test/`, which no Application syncs, and the README section that runs it.
- Add ADR 0034 and the README section `Object Store` (version rule, rollout, node restore).
- The change carries a spec delta: the manifests and the `deploy-stack` and `push-secrets` behavior are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `object-store`: the SeaweedFS object store of the cluster: its manifests, its perimeter, its Secrets, its deploy path, its alerts and its checks.

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/namespaces.yaml`, `k8s/argocd/apps/projects.yaml`, `k8s/argocd/apps/seaweedfs-operator.yaml` (new), `k8s/argocd/apps/object-store.yaml` (new), `k8s/object-store/` (new), `k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/dashboards/`, `k8s/catalog.toml`.
- Code: `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`.
- Tests: `tests/gate/k8s_checks/object_store.py` (new), `tests/gate/k8s_checks/argocd_apps.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/invariants/test_k8s_manifests.py`, `tests/commands/k8s/test_k8s.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`.
- Documents: `k8s/README.md`, `docs/adr/0034-the-object-store-is-seaweedfs-with-its-operator.md` (new), `docs/adr/README.md`.
- A person runs `uv run devops k8s push-secrets --only object-store/seaweedfs-admin --only object-store/seaweedfs-s3` after the merge.

## Feasibility

- The chart index `https://seaweedfs.github.io/seaweedfs-operator/index.yaml`, read on 2026-11-21, lists chart 0.1.48 (`appVersion` 1.0.45, 2026-11-16) as the newest. The release notes of operator 1.0.45 name the SeaweedFS dependency `v0.0.0-20261116053142-5ef99c1d8dbb`, and tag 4.54 (2026-11-16) of `seaweedfs/seaweedfs` is commit `5ef99c1d8dbb`. So 4.54 is the newest release that the newest operator supports, and it is above the floor 4.53 of the version rule.
- `helm template` of chart 0.1.48 renders the CRD `seaweeds.seaweed.seaweedfs.com` (`v1`) with the fields that the CR uses: `master.config`, `master.persistence`, `volume.storageClassName`, `volume.maxVolumeCounts`, `volume.minFreeSpacePercent`, `filer.persistence`, `s3.configSecret`, `s3.iam`, `admin.credentialsSecret`, `worker.jobType`, `securityConfig.jwtSigning` and `serviceMonitor.enabled`. The chart puts the CRDs in `templates/` behind `crds.create`, and its ClusterRole grants `monitoring.coreos.com` `servicemonitors`.
- Operator 1.0.45 `internal/controller/controller_tls.go` (`ensureSecuritySecret`, `randKey`) mints each JWT signing key with 32 random bytes and keeps it in Secret `<name>-security`, which the CR owns. So the JWT keys need no `CLUSTER_SECRETS` row, and a pushed copy would fight the operator.
- SeaweedFS 4.54 `weed/s3api/auth_credentials.go:419-427` allows every request when the gateway has no config file and no identity, and denies every request when it has a config file with no identity; it then merges the identities that the admin UI keeps in the filer. So the gateway gets the identities file of Secret `seaweedfs-s3`.
- SeaweedFS 4.54 `weed/command/s3.go:114-115` serves the Iceberg catalog on 8181 and the Lance namespace on 9101 by default, and operator 1.0.45 `controller_s3.go` passes no flag for them. Advisory GHSA-25hp-4mw7-9c75 (critical, no fix) lets an unauthenticated request act as `admin` on the S3 Tables, Iceberg and Lance APIs when the IAM subsystem starts. `weed/s3api/s3api_server.go:408` starts that subsystem, and STS with it, only for `-iam` or `-iam.config`. So the gateway gets `-iam=false`, `-port.iceberg=0` and `-port.lance=0`.
- SeaweedFS 4.54 `weed/server/master_server.go:143-144` sets `freeze_on_topology_mismatch` true and no recovery wait, and `weed/topology/topology.go` stops volume growth until `volume.growth.resume` when a volume server reports another topology id. A master with no volume mints a new id at each restart, so each master gets a 1Gi claim.
- Advisory GHSA-3qr2-qw48-cj6q (no fix) says that the admin worker gRPC port, the admin HTTP port plus 10000, has no authentication; operator 1.0.45 `controller_admin_service.go` puts 33646 on Service `seaweedfs-admin`. GHSA-m3m8-mrgq-hf9h says that the admin HTTP API has no authentication with no password; operator 1.0.45 `controller_admin_statefulset.go` binds the admin to all addresses only when `credentialsSecret` holds `adminPassword`.
- The Grafana sidecar reads only namespace `monitoring` (`k8s/monitoring/grafana-values.yaml`, `searchNamespace: monitoring`), so the dashboard ConfigMap of the chart in `object-store` would not load. The main dashboard of tag 4.54 (`other/metrics/grafana_seaweedfs.json`, 407233 bytes) is above the 262144 bytes of a ConfigMap, so the change takes `other/metrics/grafana_seaweedfs_k8s.json` (66485 bytes).
- `kubectl get nodes` shows 3 Ready worker nodes and 1 control-plane node, and `kubectl get storageclass` shows `fast-nvme` (`Retain`, `WaitForFirstConsumer`), so the 3 volume servers fit on 3 nodes with the control-plane exclusion.
- No CI check on main refuses a change of the environment paths: the freeze of step 12 of #5134 has not merged (`docs/HOMELAB_REPO_SWITCH.md`, "Step 12").

## Existing Tool Considered

SeaweedFS and the SeaweedFS operator (`seaweedfs/seaweedfs-operator`, Apache-2.0, maintained). The operator makes the StatefulSets, Deployments, Services, ServiceMonitors and the JWT Secret from one `Seaweed` CR, so the change writes no workload. cert-manager, which the cluster runs, issues the webhook certificate of the operator, so no certgen hook Job runs. Rejected in #4742: Garage and MinIO (AGPL-3.0), Ceph RGW (LGPL, raw devices), RustFS (4 nodes or more, a CLA that allows a relicense), versitygw (no replication), s3proxy (no lifecycle), Apache Ozone and CubeFS (4 or 5 service types). The change deletes no internal code.
