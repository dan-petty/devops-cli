## MODIFIED Requirements

### Requirement: The tunnel replicas prefer different nodes
The pod template of Deployment `cloudflared` in `k8s/cloudflared/deployment.yaml` SHALL have a preferred `podAntiAffinity` term with topology key `kubernetes.io/hostname` whose label selector matches the Deployment's own pod labels. It SHALL have no required `podAntiAffinity` term, so a replica still starts when only one node can take it.

#### Scenario: The Deployment's affinity
- **WHEN** two nodes can take a tunnel pod, and a person runs `kubectl -n cloudflared get pods -o wide`
- **THEN** the two replicas run on two nodes
- **AND** when only one node can take a pod, both replicas run on that node and none stays `Pending`
- **AND** `uv run devops k8s lint k8s/cloudflared` reports no finding

### Requirement: A drain keeps one tunnel replica available
The `cloudflared` kustomization SHALL apply a `policy/v1` PodDisruptionBudget with `minAvailable: 1` and `unhealthyPodEvictionPolicy: AlwaysAllow` whose selector matches the pods of Deployment `cloudflared`. A pod that is not ready serves no traffic, so it never blocks a drain.

#### Scenario: The PodDisruptionBudget
- **WHEN** both replicas are ready, and a person runs `kubectl -n cloudflared get pdb`
- **THEN** the PodDisruptionBudget of the Deployment shows the minimum 1 and one allowed disruption
- **AND** a `kubectl drain --dry-run=server` of the node of one replica evicts that replica, and the other replica keeps the tunnel up
