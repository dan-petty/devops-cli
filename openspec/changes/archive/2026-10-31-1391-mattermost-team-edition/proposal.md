# Proposal

## Why

Issue #1391: no chat server runs in the Kubernetes cluster. The cluster delivers no alert or deploy notification to a person. Mattermost Team Edition provides chat hosting and incoming webhooks for cluster integrations. This change deploys Mattermost Team Edition under Argo CD from the Mattermost Operator on a CloudNativePG database and a protected volume.

## What Changes

- `k8s/namespaces.yaml` gains namespaces `mattermost`, `cnpg-system`, and `mattermost-operator`, each with restricted Pod Security and `Prune=false,Delete=false`.
- `k8s/kustomization.yaml` gains `mattermost-operator-limitrange.yaml`, defining container request and limit defaults for namespace `mattermost-operator`.
- `k8s/argocd/apps/projects.yaml` updates `homelab-system` with the CloudNativePG and Mattermost Helm repositories and destination namespaces `cnpg-system` and `mattermost-operator`. `homelab` gains destination `mattermost` and ignores orphan Secret `mattermost-db`.
- `k8s/argocd/apps/` gains Applications `cloudnative-pg.yaml`, `mattermost-operator.yaml`, and `mattermost.yaml`.
- `k8s/argocd/bootstrap/cluster.yaml` ignores differences on `/spec/source/kustomize` for `mattermost`.
- `k8s/mattermost/` gains operator values files `cloudnative-pg-values.yaml` and `mattermost-operator-values.yaml`.
- `k8s/mattermost/` gains `database.yaml` (CloudNativePG `Cluster` named `mattermost-db`), `files-pvc.yaml` (PersistentVolumeClaim `mattermost-files`), `mattermost.yaml` (Mattermost Custom Resource), `podmonitor.yaml` (`PodMonitor`), and `networkpolicy.yaml` (`mattermost-default-perimeter` and `mattermost-db-api`).
- `src/devops_cli/config/constants.py` adds `chat` to `CONST_K8S_STACKS`, `mattermost` to `CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS`, and maps stack `chat` to `("mattermost",)` in `CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS_BY_STACK`.
- `src/devops_cli/k8s/argocd_overrides.py` extracts hosts from `Mattermost` Custom Resources.
- `src/devops_cli/commands/k8s/stack_lifecycle.py` registers Helm repositories, Helm releases, and post-Helm kustomization paths for stack `chat`.
- `src/devops_cli/k8s/cluster_secrets.py` adds `mattermost/mattermost-db` of type `kubernetes.io/basic-auth` with literal user, generated password, and derived connection string.
- `k8s/monitoring/prometheus-values.yaml` adds alerts `MattermostUnavailable` and `MattermostDatabaseDown`.
- `k8s/monitoring/networkpolicy.yaml` allows monitoring egress to `mattermost` and `cnpg-system`.
- `k8s/README.md` documents Mattermost architecture, rollout sequence, and operations.
- The new stack, manifests, and CLI options are observable by users, so this change carries spec deltas.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `gitops-host-overrides`: `mattermost` joins the homelab Applications that receive deploy-time host overrides applied server-side.
- `k8s-helm-deploy`: `deploy-stack` deploys Helm releases for `cloudnative-pg` and `mattermost-operator` at pinned versions.
- `stack-credential-sync`: the cluster Secret push table includes `mattermost/mattermost-db` with basic-auth and derived connection string.

## Impact

- `k8s/namespaces.yaml`, `k8s/kustomization.yaml`, `k8s/mattermost-operator-limitrange.yaml`.
- `k8s/argocd/apps/projects.yaml`, `k8s/argocd/apps/cloudnative-pg.yaml`, `k8s/argocd/apps/mattermost-operator.yaml`, `k8s/argocd/apps/mattermost.yaml`, `k8s/argocd/bootstrap/cluster.yaml`.
- `k8s/mattermost/kustomization.yaml`, `k8s/mattermost/cloudnative-pg-values.yaml`, `k8s/mattermost/mattermost-operator-values.yaml`, `k8s/mattermost/database.yaml`, `k8s/mattermost/files-pvc.yaml`, `k8s/mattermost/mattermost.yaml`, `k8s/mattermost/podmonitor.yaml`, `k8s/mattermost/networkpolicy.yaml`.
- `src/devops_cli/config/constants.py`, `src/devops_cli/k8s/argocd_overrides.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `src/devops_cli/k8s/cluster_secrets.py`.
- `k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/networkpolicy.yaml`, `k8s/README.md`.
- `tests/commands/k8s/test_k8s_mattermost.py`, `tests/invariants/test_k8s_argocd_apps.py`, `tests/k8s/test_k8s_argocd_overrides.py`, `tests/commands/k8s/test_k8s_network_policies.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`, `tests/core/test_third_party_telemetry.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`.

## Feasibility

Checked on `main` at 24aefb60.

- `mattermost-operator` chart 1.0.5 installs operator v1.25.4. The CRD supports `spec.image`, `spec.externalVolume`, `spec.deploymentStrategyType`, and `spec.ingressClass`.
- `cloudnative-pg` chart 0.29.1 deploys PostgreSQL 17 via CloudNativePG Operator v1.30.1.
- `ClusterSecret` supports `secret_type="kubernetes.io/basic-auth"` and `DerivedSource` added in #2008.
- `_POST_HELM_BY_STACK` executes post-Helm kustomization directories with `kubectl apply -k`.
- The wildcard Cloudflare Tunnel and Traefik router forward HTTP traffic to `mattermost.example.com`.

## Existing Tool Considered

Upstream Helm chart `mattermost-team-edition` was evaluated. The chart is officially deprecated and unsupported by Mattermost upstream. The official Mattermost Kubernetes Operator was chosen instead. CloudNativePG was chosen for automated database lifecycle and PostgreSQL operations instead of a standalone unmanaged StatefulSet.
