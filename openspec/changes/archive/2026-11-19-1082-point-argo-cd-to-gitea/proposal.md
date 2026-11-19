# Proposal: #1082

## Why
Argo CD applications must point to Gitea for git sources and PR development container images (#1082).
Production applications keep reading `main` from GitHub.
Internal iteration branches on Gitea need a deployment path into the cluster that does not touch GitHub.
A new `trial` AppProject and CLI commands give developers an isolated path to test manifests and images from Gitea branches. Closes #1082.

## What Changes
- Add the `trial` AppProject to `k8s/argocd/apps/projects.yaml` restricted to in-cluster Gitea repositories and `trial-*` namespaces.
- Add `trial-*` Applications to the orphan ignore list of the `homelab` AppProject.
- Add network policy egress for Argo CD to namespace `gitea` on TCP port 3000 in `k8s/argocd/networkpolicy.yaml`.
- Add `argocd/gitea-repo-creds` Secret to `CLUSTER_SECRETS`, gated by namespace `gitea`.
- Add `gitea.argocd_username` configuration setting and `gitea.argocd_token` credential declaration.
- Add `branch` and `contents` query methods to `GiteaClient`.
- Add `devops argo cd trial start`, `end`, and `list` CLI commands.
- Add safety rule tests ensuring no git source outside project `trial` points to Gitea.

## Capabilities
- `argo-cd-trial`: Run transient trial applications from internal Gitea branches in fenced `trial-*` namespaces.

## Impact
- Developers can deploy iteration branches from Gitea into isolated cluster namespaces.
- Mainline and production applications continue to deploy only from GitHub.
- Minikube skips Gitea repo-creds push cleanly when namespace `gitea` is missing.

## Feasibility
Confirmed against Gitea API documentation, Argo CD custom resource definitions, and current cluster manifests.

## Existing Tool Considered
Argo CD Application controller and Gitea REST API. No new external tool required.
