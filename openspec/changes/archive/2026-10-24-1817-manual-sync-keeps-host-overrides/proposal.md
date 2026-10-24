# Proposal

## Why

Issue #1817: on 2026-10-21, a manual sync of 17 Applications from the Argo CD UI, among them `cluster`, deleted the host overrides in `spec.source.kustomize` of the Applications `ingress` and `devops`. Argo CD then rendered the placeholder hosts of git. Traefik matches hosts exactly, so every public host returned 404 until `devops k8s deploy-stack` set the overrides again.

`cluster` applied its child Applications with client-side apply. Client-side apply deletes each field that the `kubectl.kubernetes.io/last-applied-configuration` annotation holds and the manifest from git does not. The `RespectIgnoreDifferences=true` option of `cluster` copies the live overrides into the manifest that it applies, so that annotation holds them. A sync that does not have the option applies the manifest from git, and the overrides go.

## What Changes

- `k8s/argocd/apps/ingress.yaml` and `k8s/argocd/apps/devops.yaml` get the annotation `argocd.argoproj.io/sync-options: ServerSideApply=true`. Argo CD reads it in every sync of `cluster`, automated or by hand, with any sync options. Server-side apply deletes only the fields of its own field manager, and the overrides belong to deploy-stack's `kubectl-patch` and to Image Updater. So a sync keeps them.
- `k8s/argocd/bootstrap/cluster.yaml` gets the annotation `argocd.argoproj.io/client-side-apply-migration-manager: argocd-controller`. The first server-side sync moves the fields of the old client-side apply entry `argocd-controller` (operation `Update`) to the server-side apply entry, so a field that git removes from the two Applications also leaves the cluster.
- A check that fails when the problem comes back (AGENTS.md rule 11): the alert `IngressServesPlaceholderHost` (critical, 5m) in group `homelab-services` of `k8s/monitoring/prometheus-values.yaml`. It fires for each Ingress that routes a host under the placeholder domain, from `kube_ingress_path`. `k8s/monitoring/k8s-monitoring-values.yaml` adds `kube_ingress_path` to the kube-state-metrics `includeMetrics`, because the chart's default allow list drops it. The alert only reads; it does not write the overrides.
- `k8s/README.md`: GitOps, Homelab Values at Deploy Time tells why a sync keeps the overrides, which actions remove them, which alert fires, and the commands that set them again. It names #1291 as the change that moves the values out of the Applications. Alerting gets a row for the new alert.
- Tests: `tests/test_k8s_argocd_apps.py` pins the two annotations. `tests/test_k8s_monitoring_alerting.py` pins the rule and its series, and checks that its host pattern matches every Ingress host in git and no host under another domain.
- The manifests are behavior that a consumer observes, so the change has a spec delta: the new capability `gitops-host-overrides`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `gitops-host-overrides`: the deploy-time host overrides on the Argo CD Applications `devops` and `ingress` stay through a sync of the app-of-apps, and an alert fires when a live Ingress routes a placeholder host.

### Modified Capabilities

None.

## Impact

- `k8s/argocd/apps/ingress.yaml`, `k8s/argocd/apps/devops.yaml`: the server-side apply annotation.
- `k8s/argocd/bootstrap/cluster.yaml`: the client-side apply migration manager annotation, and a comment on why a sync keeps the ignored field.
- `k8s/monitoring/prometheus-values.yaml`: the alert `IngressServesPlaceholderHost`.
- `k8s/monitoring/k8s-monitoring-values.yaml`: `kube_ingress_path` in the kube-state-metrics `includeMetrics`.
- `k8s/README.md`: GitOps and Alerting.
- `tests/test_k8s_argocd_apps.py`, `tests/test_k8s_monitoring_alerting.py`: the new and changed tests.

## Feasibility

Checked on 2026-10-24 against Argo CD v3.5.3 (the image of the live `argocd-server` and `argocd-application-controller`, chart 10.9.6), its source at tag `v3.5.3`, and read-only commands on the homelab cluster with kubectl v1.37.1:

- **The sync options of a manual sync.** `controller/sync.go` `SyncAppState` reads `RespectIgnoreDifferences=true` only from the operation (`syncOp.SyncOptions`), not from `spec.syncPolicy.syncOptions`. An automated sync copies the options of the spec into its operation (`controller/appcontroller.go`). For a manual sync, `server/application/application.go` `Sync` uses the options of the spec only when the request has no `syncOptions`. A request with a list, also an empty list, replaces them. The single-app sync panel of the UI fills in the options of the spec, and a person can clear them. The multi-app panel sends the options that the person selected, one list for all Applications. So the option is not certain in a manual sync, and no Argo CD setting makes the controller add it.
- **Why the overrides went.** The Argo CD sync-options documentation says that client-side apply calculates the patch "using a 3-way-merge between the live state the desired state and the `last-applied-configuration` annotation". In the live Applications `ingress` and `devops`, that annotation holds `spec.source.kustomize` (`kubectl -n argocd get application -o json`). `kubectl diff --field-manager=argocd-controller` of `k8s/argocd/apps/ingress.yaml` and `devops.yaml` as git holds them shows the deletion of `spec.source.kustomize` on both. `kubectl diff` is a server-side dry run and writes nothing. That deletion is the failure of 2026-10-21.
- **Server-side apply keeps them.** `gitops-engine/pkg/sync/sync_context.go` `shouldUseServerSideApply` uses server-side apply for a resource whose `argocd.argoproj.io/sync-options` annotation holds `ServerSideApply=true`, whatever the options of the operation are, except in a dry run. In `applyObject`, `Replace=true` comes before it. The Kubernetes server-side apply documentation says that when an applier omits a field, the field is deleted only if no other field manager owns it. The live managed fields (`kubectl get application --show-managed-fields`) give `spec.source.kustomize.patches` to `kubectl-patch` (deploy-stack runs `kubectl patch --type merge`), and `kustomize.images` on `devops` to Image Updater (`manager`). The `argocd-controller` entry owns no field under `kustomize`. `kubectl diff --server-side --force-conflicts --field-manager=argocd-controller` of the two manifests with the annotation shows only the new annotation, and `spec.source.kustomize` stays.
- **The migration manager.** The default client-side apply migration manager of Argo CD is `kubectl-client-side-apply` (`gitops-engine/pkg/sync/common/types.go`). But the client-side apply of Argo CD writes the entry `argocd-controller` with operation `Update`, because `gitops-engine/pkg/utils/kube/resource_ops.go` sets the field manager in both apply modes. Without a migration, that entry keeps its fields, so a field that git removes later stays in the cluster. `performCSAUpgradeMigration` calls client-go `csaupgrade.UpgradeManagedFieldsPatch`, which joins only the field sets of the entries and does not read the last-applied annotation. So with the annotation, the server-side apply entry gets the fields of git and no field under `kustomize`.
- **The series of the alert.** kube-state-metrics v2.20.0 serves `kube_ingress_path` with the labels `host`, `ingress` and `namespace` (`tests/fixtures/metrics/kube-state-metrics.yaml`). The live Prometheus has no current `kube_ingress_path` series, because the default allow list of the chart (`tests/fixtures/k8s_monitoring/cluster_metrics/kube-state-metrics.yaml`) does not keep it. It has `kube_ingress_info` for 19 to 20 Ingresses in each of the last 20 days. kube-state-metrics does not serve Traefik IngressRoutes, so the alert does not see the one IngressRoute with a host match.
- **Scope.** #1291 removes the cause: the values leave the Applications for a private repository on the in-cluster Gitea. It needs #1082 and a repository Secret that only the owner pushes, so it is not in this change. This change stops a sync from deleting the overrides and adds the check that rule 11 asks for.

## Existing Tool Considered

The per-resource sync option `ServerSideApply=true` of Argo CD and its client-side apply migration annotation, with the field ownership of Kubernetes server-side apply, keep the overrides. The `kube_ingress_path` series of kube-state-metrics and the existing Prometheus alert rules give the check. The change adds two manifest annotations, one allow-list entry and one alert rule, and no code.

The change deletes no internal code.
