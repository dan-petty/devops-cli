# Task: Argo CD Takes Homelab Values From Deploy-Time Overrides (#1290)

**Issue**: [#1290](https://github.com/dan-petty/devops-cli/issues/1290)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p0-critical
**Scope**: scope/k8s

## Description
#1281 (3f02ee9) tried to keep homelab values out of this public repository with a gitignored `.argocd-source.yaml` generator. Argo CD reads that file only from the Git repository at an Application's path: repo-server checks out its own clone and runs `git clean -ffdx`. The generated files therefore never reached it. The kubectl applies and fail-open Application patches added afterwards were reverted by self-heal or left unprotected. The tracked placeholder `k8s/devops/configmap.yaml` (`owner/repo`, `devops-bot`) was enforced by the `devops` Application over the ConfigMap that deploy-stack rendered.

Homelab values now come from `config.yaml` at deploy time, the same way Secrets come from the keyring. The owner decided this on 2026-10-07; a separate configuration repository remains an option for later.

## Key Changes
- **ConfigMap outside git and outside Argo CD** (`k8s/devops/`, `src/devops_cli/k8s/configmap.py`, `.gitignore`):
  - Deleted the tracked `k8s/devops/configmap.yaml`, removed it from `k8s/devops/kustomization.yaml`, and gitignored it.
  - `render_active_devops_configmap` renders `devops-cli-config` in memory from `configmap.example.yaml` and the active config. It refuses with an error naming `service.repos` or `service.machine_account` (or `k8s.github_account`) when one is unset, instead of rendering placeholders.
  - Removed `ensure_devops_configmap`, which wrote the file.
- **Host overrides on the Applications** (`src/devops_cli/k8s/argocd_overrides.py`, `k8s/argocd/bootstrap/cluster.yaml`):
  - `host_patches` turns each Ingress or IngressRoute host under the placeholder `example.com` into a Kustomize JSON patch that tests the placeholder value, then replaces it with the configured domain. A rule that git has moved fails the Application's manifest generation instead of routing a host to another backend.
  - `application_patch` and `application_source_dir` build the merge patch for `spec.source.kustomize` and locate an Application's source directory.
  - The `cluster` app-of-apps ignores `/spec/source/kustomize` on the Applications `devops` and `ingress`, and syncs with `RespectIgnoreDifferences=true`. This is the documented pattern for child Applications.
- **deploy-stack** (`src/devops_cli/commands/k8s/stack_lifecycle.py`):
  - It renders the ConfigMap and derives the host patches (`kubectl kustomize` of each Application's directory, then `host_patches`) before it writes anything to the cluster. A missing setting therefore changes nothing.
  - On an Argo CD-managed cluster it pushes Secrets, applies the ConfigMap and patches each Application. Any failure exits 1 with kubectl's reason. It no longer applies Ingresses itself.
  - On a native cluster it applies the rendered ConfigMap before the devops manifests.
- **Removed:** the `devops k8s argocd-source` command, `devops_cli.k8s.argocd_source`, the `.argocd-source*.yaml` gitignore lines, the session fixture that wrote `k8s/devops/configmap.yaml`, and the kustomize-build hook in `k8s/template.py` that created the file.
- **Docs:** `k8s/README.md` gains a "Homelab Values at Deploy Time" section. `AGENTS.md` names the template and `config.yaml` as the ConfigMap's sources. The CLI reference is regenerated.

## Acceptance Criteria
- [x] The repository holds no homelab value and no devops-cli ConfigMap; `k8s/devops/configmap.yaml` is deleted, gitignored and unlisted (`tests/test_k8s_argocd_apps.py::test_no_application_renders_the_devops_cli_config_map_and_no_commit_holds_it`).
- [x] deploy-stack renders ConfigMap `devops-cli-config` from the active config on native and Argo CD-managed clusters, and exits non-zero on a render or apply failure (`tests/test_k8s.py`, `tests/test_k8s_configmap.py`).
- [x] On an Argo CD-managed cluster, deploy-stack sets the configured hosts as `spec.source.kustomize.patches` on the Applications `devops` and `ingress`, exits non-zero on failure, and applies no Ingress (`tests/test_k8s.py`).
- [x] Kustomize applies the generated patches to every host each Application renders, and fails the build when a host moved (`tests/test_k8s_argocd_overrides.py`).
- [x] `k8s/argocd/bootstrap/cluster.yaml` ignores `/spec/source/kustomize` on both Applications with `RespectIgnoreDifferences=true`, and neither Application declares that field in git (`tests/test_k8s_argocd_apps.py`).
- [x] The `.argocd-source.yaml` generator, its command, its gitignore lines and the stdin Ingress applies are removed.
- [x] No test or fixture writes `k8s/devops/configmap.yaml`.
- [x] `k8s/README.md` describes the deploy-time values and the step order around a release merge.
- Person-run, before the release merges into `main`: run `devops k8s deploy-stack` from `release/v0.2.28`, so the Applications carry the hosts before `cluster` retargets them to `main`. Afterwards, check the Ingress hosts and ConfigMap `devops-cli-config` in the cluster.
