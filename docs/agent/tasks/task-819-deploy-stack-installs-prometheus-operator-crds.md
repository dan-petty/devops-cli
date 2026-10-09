# Task 819: Deploy-Stack Installs the Prometheus Operator CRDs Its ServiceMonitors Need

**Issue**: [#819](https://github.com/dan-petty/devops-cli/issues/819)
**Status**: Done
**Milestone**: `v0.2.24`
**Priority**: `priority/p0-critical`
**Scope**: `type/bug`, `scope/k8s`, `priority/p0-critical`

---

## 1. Description & Objectives

Before fdd4d0f (#734), kube-prometheus-stack installed the `monitoring.coreos.com` CRDs. #734 replaced it with k8s-monitoring 4.5.2 and the standalone prometheus chart, and neither ships them: k8s-monitoring's alloy-operator subchart ships only the Alloy and PodLogs CRDs. The infra stack still renders two ServiceMonitors, `llm-gateway` in k8s-monitoring's `extraObjects` and dcgm-exporter's own monitor, so on a cluster without the CRDs Helm refused both releases ("no matches for kind ServiceMonitor"). `_install_single_release` only prints that error, so `devops k8s deploy-stack --stack infra` finished with no Alloy: no cluster metrics, no pod logs, no gateway or GPU metrics.

Clusters that once ran kube-prometheus-stack still hold its CRDs, because Helm keeps CRDs on uninstall. Those CRDs carry no Helm ownership, and `_adopt_helm_resource_if_conflict` could not adopt them: its pattern required a non-empty namespace and it always passed `-n`.

#### Key Deliverables:
- **Deliverable**: Install `prometheus-community/prometheus-operator-crds` as the first infra release, ahead of k8s-monitoring and dcgm-exporter. Let conflict adoption handle cluster-scoped resources (`in namespace ""`, no `-n`). Teardown skips the CRD release.
- **Acceptance criteria**: On a scratch cluster without the CRDs, `deploy-stack --stack infra` installs k8s-monitoring and dcgm-exporter without errors; on a cluster with unowned leftover CRDs, the same command adopts them and succeeds. Unit tests cover the release order and a cluster-scoped conflict, and `uv run devops ci` passes.
- **Constraint**: A reputable, maintained chart only (prometheus-community). Tests never touch the network, a cluster, Helm or kubectl.

## 2. Delivered

- [x] **Approach: the standalone CRD chart.** k8s-monitoring 4.5.2 has no supported option to deploy these CRDs: its values offer none, and the alloy-operator subchart's `crds` switches cover only the Alloy and PodLogs CRDs. The chart's `UPGRADING.md` ("Prometheus Operator Object CRDs removed", 4.0) tells users of `prometheusOperatorObjects` to install `prometheus-operator-crds` from prometheus-community before the chart, so that is the conventional, maintained path. Its repo was already registered for infra.
- [x] **Release** (`src/devops_cli/commands/k8s/stack_lifecycle.py`): `prometheus-operator-crds` is the first entry of `_HELM_RELEASES_BY_STACK["infra"]`, in the `monitoring` namespace and, like every chart deploy-stack installs, without a pinned version. Chart 32.0.1 ships the ten `monitoring.coreos.com` CRDs as templates, so upgrades update them.
- [x] **Values** (`k8s/monitoring/prometheus-operator-crds-values.yaml`): sets `helm.sh/resource-policy: keep` on every CRD, so a hand-run `helm uninstall` leaves them in place too.
- [x] **Teardown**: `teardown-stack` skips the releases in `CONST_HELM_TEARDOWN_RETAINED_RELEASES` (`prometheus-operator-crds`). Deleting a CRD deletes every object of its kind in the cluster, every ServiceMonitor included. Deleting the `monitoring` namespace drops the release record but not the cluster-scoped CRDs, and their ownership metadata still matches the release, so the next deploy takes them back without a conflict. `k8s/README.md` says teardown leaves them.
- [x] **Cluster-scoped adoption**: `CONST_HELM_OWNERSHIP_CONFLICT_RE` matches Helm's `<Kind> "<name>" in namespace "<namespace>"` with an empty namespace, and adoption omits `-n` for it. The `meta.helm.sh/release-namespace` annotation now carries the release's namespace, which Helm checks it against. It used to carry the resource's namespace: empty for a CRD, and `llm` for k8s-monitoring's `llm-gateway` ServiceMonitor, whose release lives in `monitoring`, so neither could be adopted.
- [x] **One deploy adopts every leftover CRD**: Helm names one conflicting resource per failed attempt (`existingResourceConflict` in Helm's `pkg/action/validate.go` stops at the first). The old cap of five retries could adopt only five of the ten CRDs. `_run_helm_with_adoption_retries` now allows `DEFAULT_HELM_RECOVERY_MAX_RETRIES` (20) retries and stops as soon as a retry fails exactly like the attempt before it, so a conflict that adoption cannot clear costs one extra Helm run instead of the whole budget.
- [x] **Unit tests** (`tests/test_k8s.py`), with `runtime._run_cmd` and `_cluster_reachable` mocked:
  - `test_prometheus_operator_crds_install_before_every_service_monitor`: the CRD release is the first infra release, from a registered repo, and the only releases whose values render a ServiceMonitor are k8s-monitoring and dcgm-exporter, both later in infra. Since #1130 only k8s-monitoring does: k8s-monitoring's dcgm-exporter integration scrapes the exporter, and its chart's monitor is off.
  - `test_adopt_helm_resource_addresses_cluster_scoped_and_namespaced_conflicts`: the exact kubectl commands for a cluster-scoped CRD (no `-n`) and for the namespaced `llm-gateway` ServiceMonitor (`-n llm`, release namespace `monitoring`).
  - `test_helm_retries_adopt_each_leftover_crd_until_the_release_installs`: ten successive CRD conflicts are adopted in one run and the eleventh attempt installs; an unchanged repeated conflict stops after one retry.
  - `test_teardown_stack_keeps_the_prometheus_operator_crds`: `teardown-stack --stack infra` uninstalls every other infra release in reverse order and never the CRD release, whose values carry the keep policy.

## 3. Verification

- All 6 new k8s test cases fail against 308a71f's `stack_lifecycle.py` and pass with this change. The k8s, logging stack, LLM pool metrics, Qdrant, Jaeger, architectural invariant and task file suites pass.
- `helm template` of `prometheus-operator-crds` 32.0.1 with the new values, rendered offline: ten CustomResourceDefinitions, each annotated `helm.sh/resource-policy: keep`.
- `uv run devops ci` from a linked worktree, on top of #824's tripwire fix: all 13 checks pass.

### Live acceptance runs (pending a person)

The agent ran no command against a cluster. A person runs both checks below and records the results here.

1. Scratch cluster without the CRDs (k3d shown; `minikube start -p crd-check` works too, with `--context crd-check`):

   ```bash
   k3d cluster create crd-check
   kubectl --context k3d-crd-check get crd servicemonitors.monitoring.coreos.com  # expect NotFound
   uv run devops k8s deploy-stack --stack infra --context k3d-crd-check  # expect no "Failed to install" line
   helm list -n monitoring --kube-context k3d-crd-check  # prometheus-operator-crds, k8s-monitoring, dcgm-exporter: deployed
   kubectl --context k3d-crd-check get servicemonitors -A  # llm/llm-gateway and the dcgm-exporter monitor
   uv run devops k8s teardown-stack --stack infra --context k3d-crd-check
   kubectl --context k3d-crd-check get crd servicemonitors.monitoring.coreos.com  # still present
   k3d cluster delete crd-check
   ```

2. Homelab cluster, which still holds the ten unowned CRDs that kube-prometheus-stack left:

   ```bash
   kubectl --context <homelab-context> get crd -o name | grep monitoring.coreos.com  # the leftovers
   uv run devops k8s deploy-stack --stack infra --context <homelab-context>
   # expect one "Adopting pre-existing customresourcedefinition/<name>.monitoring.coreos.com" line
   # per leftover CRD, then "prometheus-operator-crds installed", and no "Failed to install" line
   helm list -n monitoring --kube-context <homelab-context>
   kubectl --context <homelab-context> get crd servicemonitors.monitoring.coreos.com \
     -o jsonpath='{.metadata.annotations.meta\.helm\.sh/release-name}'  # prometheus-operator-crds
   ```
