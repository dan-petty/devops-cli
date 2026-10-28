# Proposal

## Why

Issue #1023: Deployment `cloudflared` (`k8s/cloudflared/deployment.yaml`) runs 2 replicas, but nothing tells the scheduler to put them on different nodes, and no PodDisruptionBudget protects them. Both tunnel connectors can land on one node. A failure or a drain of that node then cuts all external ingress, because every external request comes in through the tunnel. kube-linter 0.8.3 reports `no-anti-affinity` on the file, and every branch review of 2026-10-02 reported it.

## What Changes

- The pod template of Deployment `cloudflared` gets a preferred `podAntiAffinity` term on `kubernetes.io/hostname` that selects the pods with `app.kubernetes.io/name: cloudflared`. The scheduler puts the two replicas on different nodes when it can. The term is soft, so a replica still starts when only one node can take it, for example while a node is offline.
- A new PodDisruptionBudget `cloudflared` (`k8s/cloudflared/pdb.yaml`) with `minAvailable: 1` selects the same pods. A drain evicts a cloudflared pod only while another one is available. It sets `unhealthyPodEvictionPolicy: AlwaysAllow`, so a pod that is not ready, and so serves no traffic, never blocks a drain. kube-linter's `pdb-unhealthy-pod-eviction-policy` check asks for this.
- `k8s/cloudflared/kustomization.yaml` lists `pdb.yaml`. Argo CD's `base` Application syncs it with the rest of the root kustomization; the `homelab` and `homelab-system` AppProjects restrict no namespaced kind.
- `k8s/README.md` lists `pdb.yaml` in the layout and says how the replicas are placed.
- A manifest changes what the cluster runs, so the change carries a spec delta: the new capability `cloudflared-tunnel-availability`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `cloudflared-tunnel-availability`: how the cloudflared tunnel replicas are placed on nodes and kept available through a voluntary disruption.

## Impact

- `k8s/cloudflared/deployment.yaml`, `k8s/cloudflared/pdb.yaml` (new), `k8s/cloudflared/kustomization.yaml`.
- `k8s/README.md`.
- `tests/test_k8s_cloudflared.py`.

## Feasibility

- On `origin/main` 5064f31f, `k8s/cloudflared/deployment.yaml` has `replicas: 2` and no `affinity` or `topologySpreadConstraints`, and `k8s/cloudflared/` has no PodDisruptionBudget.
- `kubectl -n cloudflared get deploy,pods,pdb -o wide` on 2026-10-28: 2 of 2 replicas ready, one pod on each of two nodes, and no PodDisruptionBudget. The cluster has four ready nodes, so the soft term can always place the two replicas apart.
- kube-linter 0.8.3 (the version in `tools.lock`) on `k8s/cloudflared/`: "object has 2 replicas but does not specify inter pod anti-affinity (check: no-anti-affinity)". The refinement of #1023 on 2026-10-08 measured that a `topologySpreadConstraints` entry alone still fails this check, and that a preferred `podAntiAffinity` term passes it.
- With the term and the budget, kube-linter 0.8.3 reports no lint error on `k8s/cloudflared/`. A budget without `unhealthyPodEvictionPolicy` failed its `pdb-unhealthy-pod-eviction-policy` check.
- `kubectl apply -k k8s/cloudflared/ --dry-run=server` against the cluster (Kubernetes v1.31.4+k3s1, where `unhealthyPodEvictionPolicy` is GA) configures the Deployment and creates the budget, and the server keeps `unhealthyPodEvictionPolicy: AlwaysAllow`.
- A `requiredDuringScheduling` term was rejected: with one node offline, it leaves a replica Pending.

## Existing Tool Considered

The change uses two Kubernetes features, inter-pod anti-affinity (`podAntiAffinity`) and `policy/v1` PodDisruptionBudget, and kube-linter checks the result. It builds nothing and deletes no internal code.
