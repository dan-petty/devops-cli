# Proposal

## Why

Issue #1630: the in-cluster image registry (`registry:2.8.3` in namespace `registry`) accepts pushes and deletes over plain HTTP on a fixed NodePort on every node, with no authentication. It runs as root with no securityContext, and its namespace has no NetworkPolicy. Its local-path volume does not enforce the 50Gi request, so an unauthenticated push can fill the disk of a node. No workload pulls from it.

The owner decided on 2026-10-24 that the internal registry moves to Gitea: Gitea's container registry (#1081) is the internal registry, and the nodes pull the pull-request images from it (#1082). This change delivers the issue's "Remove" branch. It does not deliver the "Keep" branch (htpasswd, securityContext, NetworkPolicy), because the registry leaves.

## What Changes

- Delete `k8s/registry/` (Deployment, Service, PVC and kustomization), remove `registry` from the root `k8s/kustomization.yaml`, and remove the Namespace `registry` from `k8s/namespaces.yaml`.
- Remove the egress rule from the monitoring perimeter (`k8s/monitoring/networkpolicy.yaml`) to the registry's metrics port 5001 in namespace `registry`.
- Keep `registry` in the destinations of the AppProjects `homelab` and `homelab-system`. Argo CD ignores a live object in a namespace that the project does not permit, so the destination must stay until Argo CD has pruned the Deployment and the Service and a person has deleted the namespace.
- Add a test that fails when a manifest under `k8s/` runs the Distribution image or declares an object in namespace `registry`, or when the root kustomization renders one.
- Delete the tests of the removed registry: its memory assertion in `tests/test_k8s.py` and its scrape entries in `tests/test_k8s_monitoring_integration.py`. Keep `tests/test_security_kubelinter.py`, which pins a recorded report.
- Record the decision in `k8s/README.md` (Internal Image Registry), with the commands that delete the Namespace and the PVC that Argo CD keeps. Remove the registry from the scrape list and the directory tree of `k8s/README.md` and from `src/devops_cli/ai/knowledge_base/devops_cli/tasks/k8s_stack_deployment.md`.
- The manifests are observable behavior, so the change has a spec delta: the new capability `cluster-image-registry`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `cluster-image-registry`: where the cluster keeps its internal container images, and that the manifests deploy no in-cluster Distribution registry.

### Modified Capabilities

None.

## Impact

- `k8s/kustomization.yaml`, `k8s/namespaces.yaml`, `k8s/registry/` (deleted), `k8s/monitoring/networkpolicy.yaml`.
- `tests/test_k8s.py`, `tests/test_k8s_monitoring_integration.py`.
- `k8s/README.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/k8s_stack_deployment.md`.
- The live cluster after the merge: Application `base` prunes Deployment `registry/registry` and Service `registry/registry`. Namespace `registry` and PVC `registry-data` stay, and `base` shows them OutOfSync, until a person deletes them.

## Feasibility

Checked read-only on 2026-10-24, against Argo CD v3.5.3 on the homelab cluster:

- No consumer. No container image under `k8s/` names the registry: `git grep` finds its NodePort and its names only in `k8s/registry/`. `kubectl get pods -A` shows 58 pods, and no container image names the registry's NodePort or its other host name. The node image caches hold only old `squid` images from the registry, and squid left in #734.
- No request in 30 days. Loki (`{namespace="registry"}`, 719 hours) holds 131 lines that are not kube-probe lines. They are Kubernetes events and the registry's daily upload purge. `{namespace="registry"} != "kube-probe" |~ "HTTP/1|http.request.method"` returns 0 lines. The volume holds two repositories, `squid` and `test-app` (74 MB), and nothing pulls them.
- No mirror routes to it. The homelab playbook `configure_registries.yaml` (dan-petty/homelab, read through the contents API) lists mirrors only for the registry's own host names (its NodePort on each node, and one alias), not for a public registry. Only an image that names one of these host names goes through it, and no workload names one. The hosts' `registries.yaml` files cannot be read from the cluster.
- Pruning. Application `base` (project `homelab`, path `k8s`, `automated.prune: true`, `selfHeal: true`) tracks the Namespace, the PVC, the Service and the Deployment. Argo CD's sync options page says that a resource with `Prune=false` is not pruned and that "the app will be out of sync if Argo CD expects a resource to be pruned". `Delete=false` acts only when the Application is deleted. So `base` prunes the Deployment and the Service, keeps the Namespace and the PVC, and stays OutOfSync until a person deletes them. Prometheus rule `ArgoCdApplicationOutOfSync` fires after 15 minutes.
- Project destinations. `controller/state.go` at v3.5.3 deletes from the live set every object that `IsLiveResourcePermitted` refuses ("filter out all resources which are not permitted in the application project"). Without `registry` in the destinations of `homelab`, Argo CD would not see the Deployment and would not prune it. So the destinations stay in this change.
- The PersistentVolume of `registry-data` has reclaim policy `Delete` (storage class `local-path`), so deleting the PVC removes its data on the node.

## Existing Tool Considered

Gitea's built-in container registry (Gitea packages, #1081) is the open, maintained tool that replaces the in-cluster Distribution registry, with authentication and a forge around it. Argo CD's own pruning removes the workload, so the change adds no deletion code. The test uses docker-py's `parse_repository_tag` and `resolve_repository_name` to read image references, and `kubectl kustomize` to render the root kustomization.

The change deletes `k8s/registry/` (four manifests), the Namespace `registry`, the monitoring egress rule to port 5001 in `registry`, and the registry's assertions in two test modules. It adds no internal code.
