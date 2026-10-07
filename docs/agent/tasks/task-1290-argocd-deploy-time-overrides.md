# Task: Argo CD Takes Homelab Values From Deploy-Time Overrides (#1290)

**Issue**: [#1290](https://github.com/dan-petty/devops-cli/issues/1290)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p0-critical
**Scope**: scope/k8s

## Description
Commit 3f02ee9 (#1281) tried to keep homelab values out of this public repository with a gitignored `.argocd-source.yaml` generator. Argo CD reads that file only from the Git repository at an Application's path: repo-server checks out its own clone and runs `git clean -ffdx`. The generated files therefore never reached it. The kubectl applies and fail-open Application patches added afterwards were reverted by self-heal or left unprotected. The tracked placeholder `k8s/devops/configmap.yaml` (`owner/repo`, `devops-bot`) was enforced by the `devops` Application over the ConfigMap that deploy-stack rendered.

Homelab values now come from `config.yaml` at deploy time, the same way Secrets come from the keyring. The owner decided this on 2026-10-07. A follow-up item moves the private Argo CD configuration into the in-cluster Gitea once the Gitea items land.

## Key Changes
- **ConfigMap outside git and outside Argo CD** (`k8s/devops/`, `src/devops_cli/k8s/configmap.py`, `.gitignore`, `k8s/argocd/apps/projects.yaml`):
  - Deleted the tracked `k8s/devops/configmap.yaml`, removed it from `k8s/devops/kustomization.yaml`, and gitignored it.
  - `render_active_devops_configmap` renders `devops-cli-config` in memory from `configmap.example.yaml` and the active config. It refuses with an error naming `service.repos` or `service.machine_account` (or `k8s.github_account`) when one is unset.
  - `render_devops_configmap_content` requires both values and has no placeholder fallback.
  - AppProject `homelab` ignores the ConfigMap among its orphaned resources.
  - Removed `ensure_devops_configmap`, which wrote the file.
- **Host overrides built at the Application's revision** (`src/devops_cli/k8s/argocd_overrides.py`, `k8s/argocd/bootstrap/cluster.yaml`, `src/devops_cli/config/constants.py`):
  - deploy-stack reads each homelab Application's live source. `render_at_revision` fetches its `targetRevision` from its `repoURL` into a temporary directory and builds its path with Kustomize. Whichever branch is checked out locally, the hosts come from what Argo CD builds. `--argocd-revision <ref>` stages another revision before a release merges.
  - git reads the repository and revision after `--end-of-options`, without prompts and within a time limit, so a value from the cluster or the command line can never act as a git option. A multi-source Application, or one without a repository, is refused by name.
  - `host_patches` turns each Ingress or IngressRoute host under the placeholder (rule, TLS or route match) into a Kustomize JSON patch that tests the placeholder value, then replaces it. The replacement comes from `render_manifest_template`, the substitution native deploys use.
  - The `cluster` app-of-apps ignores `/spec/source/kustomize` on the Applications `devops` and `ingress`, and syncs with `RespectIgnoreDifferences=true`.
  - The homelab Applications, and which stack sets which, live in `config/constants.py`.
- **deploy-stack and teardown-stack** (`src/devops_cli/commands/k8s/stack_lifecycle.py`):
  - deploy-stack renders the ConfigMap first, so a missing setting stops a dry run and a deploy alike.
  - On an Argo CD-managed cluster it derives the host patches before it pushes Secrets or writes anything, and refuses an Application that renders no host under the placeholder rather than clear staged hosts with an empty patch list. It then applies the ConfigMap and patches each Application; any failure exits 1 with kubectl's reason. It applies no Ingress itself.
  - On a native cluster it applies the rendered ConfigMap before the devops manifests.
  - The dry run lists the ConfigMap and the host overrides, with the domain they would use or a note that an Argo CD-managed cluster needs one, without running anything.
  - teardown-stack deletes the ConfigMap by name.
- **Removed:**
  - the `devops k8s argocd-source` command;
  - `devops_cli.k8s.argocd_source`;
  - the `.argocd-source*.yaml` gitignore lines;
  - the session fixture and kustomize-build hook that wrote `k8s/devops/configmap.yaml`.
- **Docs:**
  - `k8s/README.md` gains "Homelab Values at Deploy Time", with the release-merge steps. The bootstrap and recovery steps end with deploy-stack.
  - `devops k8s apply k8s/devops/ --template` is no longer offered as an equivalent; the run-job hint and the knowledge base point at deploy-stack.
  - `AGENTS.md` names the template and `config.yaml` as the ConfigMap's sources.

## Acceptance Criteria
- [x] The repository holds no homelab value and no devops-cli ConfigMap; `k8s/devops/configmap.yaml` is deleted, gitignored and unlisted (`tests/test_k8s_argocd_apps.py`).
- [x] deploy-stack renders ConfigMap `devops-cli-config` from the active config on native and Argo CD-managed clusters, and exits non-zero when rendering or applying it fails (`tests/test_k8s.py`, `tests/test_k8s_configmap.py`).
- [x] On an Argo CD-managed cluster, deploy-stack sets the hosts that each Application renders at its revision, or at `--argocd-revision`, as `spec.source.kustomize.patches`. It pushes Secrets only after deriving them, exits non-zero on failure, and applies no Ingress (`tests/test_k8s.py`).
- [x] Kustomize applies the generated patches to every host each Application renders, and fails the build when a host moved within its object (`tests/test_k8s_argocd_overrides.py`).
- [x] `k8s/argocd/bootstrap/cluster.yaml` ignores `/spec/source/kustomize` on both Applications with `RespectIgnoreDifferences=true`, neither Application declares that field in git, and AppProject `homelab` ignores the orphaned ConfigMap (`tests/test_k8s_argocd_apps.py`).
- [x] The dry run reports the ConfigMap and the host overrides and runs nothing, and teardown-stack deletes the ConfigMap (`tests/test_k8s.py`).
- [x] A revision or repository value is never read as a git option, an Application that renders no placeholder host is refused, and a multi-source Application is refused by name (`tests/test_k8s_argocd_overrides.py`, `tests/test_k8s.py`).
- [x] The `.argocd-source.yaml` generator, its command, its gitignore lines and the stdin Ingress applies are removed; no test or fixture writes `k8s/devops/configmap.yaml`.
- [x] `k8s/README.md` describes the deploy-time values and the release-merge steps.
- Pending a person (the one-time v0.2.28 cutover, while the live leaf Applications still track `release/v0.2.27`, whose overlays carry the real hosts): right before `release/v0.2.28` merges into `main`, run `uv run devops k8s deploy-stack --stack devops --argocd-revision release/v0.2.28` from a checkout of `release/v0.2.28`. Until the merge, Application `ingress` shows ComparisonError `testing value /spec/rules/0/host failed`, and the live Ingresses are unchanged. After the merge, roadmap-service waits for image `service:v0.2.28` from the Release Orchestration workflow; once it is published, run `kubectl -n devops rollout restart deploy/roadmap-service`. Then run `devops argo cd apps status devops`, `devops argo cd apps status ingress`, `kubectl get ingress,ingressroute -A -o yaml | grep example.com` (prints nothing) and `kubectl -n devops get configmap devops-cli-config -o yaml`.
- Release process: before #1283 merges, the v0.2.28 section of `CHANGELOG.md` takes this fragment and drops the #1279 entry that adds `devops k8s argocd-source`, through a `chore/open-v0.2.28-<slug>` pull request as #1284 did for 1279.md.
