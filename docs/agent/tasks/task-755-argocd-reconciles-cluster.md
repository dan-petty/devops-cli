# Task 755: Argo CD Keeps the Homelab Cluster at the Declared State

**Issue**: [#755](https://github.com/dan-petty/devops-cli/issues/755)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: type/feature, scope/k8s

---

## 1. Description & Objectives

The homelab cluster previously relied on manual imperative reconciliation (`devops k8s deploy-stack`, `kubectl apply -k`, manual Helm upgrades, ad-hoc domain patching), which allowed configuration drift, split ownership, and undocumented manual steps.

This deliverable establishes full GitOps reconciliation for the homelab cluster via Argo CD:
- **Two-level Root Application Topology**:
  - `bootstrap` (`k8s/argocd/bootstrap/bootstrap.yaml`) tracks `main` and syncs the root `cluster` Application.
  - `cluster` (`k8s/argocd/bootstrap/cluster.yaml`) tracks the active release branch (`release/vX.Y.Z`) and syncs project boundaries (`projects.yaml`) and 20 leaf Applications (8 raw leaf applications and 12 multi-source Helm applications).
- **Single Manifest Ownership & Data Safety**:
  - Exactly one Application owns each rendered raw resource; duplicate `namespace.yaml` manifests removed in favor of `k8s/namespaces.yaml`.
  - Data safety annotations (`argocd.argoproj.io/sync-options: Prune=false,Delete=false`) applied to all Namespaces and PersistentVolumeClaims.
  - Helm chart values configured to prevent PVC deletion on prune (`enableStatefulSetAutoDeletePVC: false`).
- **Declarative Domain Overlays**:
  - Replaced unused `k8s/overlays/templated/` with `k8s/overlays/homelab/ingress/` and `k8s/overlays/homelab/devops/`, patching `example.com` to the homelab domain.
- **Push Secrets Integration**:
  - Added `monitoring/grafana-admin` to the keyring push table with live password adoption, removing hardcoded auto-generated admin passwords from Helm values.
- **Lifecycle & Release Automation**:
  - `devops k8s deploy-stack` detects when Argo CD manages the cluster, executes secret push, and delegates manifest/Helm reconciliation to Argo CD; `teardown-stack` refuses execution.
  - `release prepare` and `release cut` automatically rewrite git-source `targetRevision` fields across `k8s/argocd/` to match the prepared release version (`release/vX.Y.Z`).
  - `release check` validates that git targetRevisions under `k8s/argocd/` are uniform and match `release/v<pyproject_ver>`.

---

## 2. Acceptance Criteria

- [x] **Applications Topology (`tests/test_k8s_argocd_apps.py`)**:
  - Every Application's project is `homelab` or `homelab-system`, except `bootstrap` and `cluster` which use `default`.
  - No `homelab` Application targets `kube-system` or `default`.
  - Every Application enables `automated.prune: true` and `automated.selfHeal: true`.
  - Git sources name this repository with uniform `release/vX.Y.Z` targetRevisions, except `bootstrap` on `main`.
  - Helm sources pin exact SemVer versions matching `_HELM_RELEASES_BY_STACK` and `traefik`.
  - Synced paths and kustomizations exist on disk; `bootstrap`, `cluster`, and `argocd` carry no resources finalizer.
- [x] **Single Manifest Ownership & Data Safety**:
  - Rendered raw objects appear in exactly one Application's synced paths; duplicate namespaces eliminated.
  - Namespaces and PVCs carry `argocd.argoproj.io/sync-options: Prune=false,Delete=false`.
  - Helm chart values set PVC sync-options annotations and disable auto-delete on StatefulSets.
- [x] **Domain Overlays**:
  - `k8s/overlays/homelab/ingress/` and `devops/` patch Ingress hosts and route matches to the homelab domain with zero occurrences of `example.com` in rendered output.
- [x] **Push Secrets Integration**:
  - `CLUSTER_SECRETS` includes `monitoring/grafana-admin` for the `infra` stack with live password adoption and deployment restart; tested in `tests/test_k8s_push_secrets.py`.
  - `grafana-values.yaml` specifies `admin.existingSecret: grafana-admin` without plain text passwords.
- [x] **Stack Lifecycle Delegation**:
  - `devops k8s deploy-stack` pushes keyring secrets and exits 0 when `kubectl -n argocd get application cluster` exists; `teardown-stack` exits 1; tested in `tests/test_k8s.py`.
  - Under `--dry-run`, neither command executes cluster API or subprocess calls.
  - Helm upgrade commands carry pinned `--version`.
- [x] **Release Automation (`tests/test_release.py`)**:
  - `_release_paths(root)` stages `k8s/argocd/`.
  - `release prepare` rewrites git targetRevisions under `k8s/argocd/` to match the prepared release branch (`release/vX.Y.Z`) while preserving chart versions.
  - `release check` validates uniform git targetRevisions matching `release/v<pyproject_ver>`.
- [x] **Documentation & Fragment**:
  - `k8s/README.md` updated with "GitOps" section (bootstrap, recovery, drift commands, replaced hand steps table) and directory structure.
  - Docs regenerated and verified via `devops docs check`.
  - Changelog fragment `changelog.d/755.md` authored.
- [x] All tests run offline and pass in `uv run devops ci`.
- Pending a person: `homelab-k3s` cluster adoption:
  - Record PVC UIDs and set PV reclaim policies to `Retain`.
  - Run `kubectl diff -k` and `helm template | kubectl diff` across all stacks to settle differences.
  - Run `uv run devops k8s push-secrets --stack infra --context homelab-k3s` and verify Grafana login.
  - Merge PR, run `uv run devops argo cd apps bootstrap-gitops -f k8s/argocd/bootstrap/cluster.yaml --context homelab-k3s`, and verify all 20 applications show `Synced` and `Healthy`.
  - Verify self-heal: scale down `deploy/jaeger` in namespace `otel` and observe automatic recovery to replica count 1 within 5 minutes.

---

## 3. Deliverables

- [x] `k8s/namespaces.yaml`: Added data safety annotations and unified namespace declarations.
- [x] `k8s/registry/pvc.yaml` & Helm value files: Added `Prune=false,Delete=false` annotations and disabled PVC auto-deletion.
- [x] `k8s/argocd/bootstrap/`: Added `bootstrap.yaml` and `cluster.yaml` root applications.
- [x] `k8s/argocd/apps/`: Added `projects.yaml`, 8 raw leaf applications, and 12 multi-source Helm applications.
- [x] `k8s/overlays/homelab/`: Added declarative ingress and devops domain overlays.
- [x] `src/devops_cli/commands/argo.py`: Updated CLI defaults for bootstrap-gitops.
- [x] `src/devops_cli/k8s/cluster_secrets.py`: Added `monitoring/grafana-admin` to push table.
- [x] `src/devops_cli/k8s/credentials.py`: Updated Grafana credential sync to use keyring credentials.
- [x] `src/devops_cli/commands/k8s/stack_lifecycle.py`: Pinned Helm versions, added Argo CD cluster probe, and gated deploy/teardown.
- [x] `src/devops_cli/commands/release.py`: Added `k8s/argocd/` to release paths, automated targetRevision rewriting to match prepared release, and enforced checks.
- [x] `k8s/README.md`: Added GitOps section and updated directory tree.
- [x] `tests/test_k8s_argocd_apps.py`: Added comprehensive Argo CD application test suite.
- [x] `tests/test_k8s.py`: Added lifecycle probe and version pinning tests.
- [x] `tests/test_release.py`: Added targetRevision rewrite and validation tests.
- [x] `changelog.d/755.md`: Authored changelog fragment.
