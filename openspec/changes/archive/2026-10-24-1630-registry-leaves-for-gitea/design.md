# Design

## Context

The root kustomization `k8s/` applies `namespaces.yaml`, `cloudflared` and `registry`. Argo CD's Application `base` syncs it with automated prune and self-heal. Every Namespace in `k8s/namespaces.yaml` and the PVC `registry-data` carry `argocd.argoproj.io/sync-options: Prune=false,Delete=false`, so Argo CD never deletes them. Both AppProjects, `homelab` (the project of `base`) and `homelab-system`, list namespace `registry` in their destinations.

Gitea is not deployed yet (#1081). Until it is, the cluster has no internal registry, and every workload pulls its image from a public registry (GHCR, Docker Hub, Quay, NVIDIA NGC and `registry.k8s.io`).

## Goals / Non-Goals

**Goals:**

- Remove the unauthenticated registry from the manifests, so that Argo CD prunes its Deployment and Service.
- Make a test fail if a manifest under `k8s/` runs the Distribution image or declares an object in namespace `registry` again.
- Record the decision and the person's clean-up step in `k8s/README.md`.

**Non-Goals:**

- Deploy Gitea or its container registry (#1081), or point Argo CD and the pull-request images at it (#1082).
- Apply anything to the cluster, or delete the namespace. Argo CD applies the change after the merge, and a person deletes the namespace.
- Change the node mirror configuration. It is in dan-petty/homelab (#7).

## Decisions

- **Decision: remove the registry, do not secure it.**
  *Choice:* the issue's "Remove" branch, as the owner decided on 2026-10-24.
  *Rejected alternative:* the "Keep" branch: htpasswd from a pushed Secret, a non-root securityContext, `REGISTRY_STORAGE_DELETE_ENABLED` off and a `registry-perimeter` NetworkPolicy.
  *Evidence for rejection:* nothing uses the registry (no pull and no push request in 30 days of Loki logs, no workload image names it), and Gitea's container registry replaces it. Securing it adds a Secret row, a policy and tests for a workload that leaves.
- **Decision: keep `registry` in the AppProject destinations.**
  *Choice:* `k8s/argocd/apps/projects.yaml` does not change in this pull request. A follow-up removes the destinations after a person deletes the namespace.
  *Rejected alternative:* remove the destinations in the same commit.
  *Evidence for rejection:* Argo CD v3.5.3 `controller/state.go` drops from the live set each object that `IsLiveResourcePermitted` refuses. The `cluster` Application syncs `projects.yaml` and `base` syncs `k8s/` in no fixed order. If the project change syncs first, `base` no longer sees the Deployment and the Service, so it does not prune them, and the registry keeps running with no owner.
- **Decision: a person deletes the Namespace and the PVC.**
  *Choice:* the `Prune=false,Delete=false` annotations stay on every Namespace, and `k8s/README.md` gives the two `kubectl delete` commands.
  *Rejected alternative:* remove the annotation from the PVC first, so that Argo CD prunes it.
  *Evidence for rejection:* that needs two pull requests in order (the annotation change must sync before the removal), and the Namespace keeps its annotation anyway. The annotations protect data, and the owner deletes data.
- **Decision: the test reads the images with docker-py.**
  *Choice:* `docker.utils.parse_repository_tag` and `docker.auth.resolve_repository_name` resolve `registry:2.8.3`, `registry` and `docker.io/library/registry` to Docker Hub's Distribution repository. `tests/test_k8s_llm_gateway.py` already uses `parse_repository_tag`.
  *Rejected alternative:* a regular expression on the image string.
  *Evidence for rejection:* the repository uses libraries for parsing, and a pattern would miss the `library/` and `docker.io/` forms.

## Risks / Trade-offs

- [Application `base` is OutOfSync, and `ArgoCdApplicationOutOfSync` fires, from the merge until a person deletes the Namespace and the PVC] → `k8s/README.md` and the tasks name the commands. The lead asks the owner to run them after the merge.
- [Deleting the PVC removes the volume's data on the node (reclaim policy `Delete`)] → the volume holds only old `squid` and `test-app` images, and nothing pulls them.
- [The node mirror configuration in dan-petty/homelab still names the registry's NodePort] → no image names those hosts, so no pull goes through them. dan-petty/homelab#7 points its mirrors at Gitea's registry instead. A node's containerd cannot resolve a cluster Service name, so that mirror needs a host name that the nodes can reach.
