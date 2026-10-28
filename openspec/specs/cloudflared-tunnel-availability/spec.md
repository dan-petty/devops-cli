# cloudflared-tunnel-availability Specification

## Purpose
How the cloudflared tunnel replicas are placed on nodes and kept available through a voluntary disruption, so that the failure or drain of one node does not cut all external ingress.

## Requirements

### Requirement: The tunnel replicas prefer different nodes
The pod template of Deployment `cloudflared` in `k8s/cloudflared/deployment.yaml` SHALL have a preferred `podAntiAffinity` term with topology key `kubernetes.io/hostname` whose label selector matches the Deployment's own pod labels. It SHALL have no required `podAntiAffinity` term, so a replica still starts when only one node can take it.

#### Scenario: The Deployment's affinity
- **WHEN** a test reads the pod template of Deployment `cloudflared`
- **THEN** it has one preferred `podAntiAffinity` term with topology key `kubernetes.io/hostname`
- **AND** the term's `matchLabels` are a subset of the pod template's labels and hold `app.kubernetes.io/name: cloudflared`
- **AND** the pod template has no `requiredDuringSchedulingIgnoredDuringExecution` anti-affinity term

### Requirement: A drain keeps one tunnel replica available
The `cloudflared` kustomization SHALL apply a `policy/v1` PodDisruptionBudget with `minAvailable: 1` and `unhealthyPodEvictionPolicy: AlwaysAllow` whose selector matches the pods of Deployment `cloudflared`. A pod that is not ready serves no traffic, so it never blocks a drain.

#### Scenario: The PodDisruptionBudget
- **WHEN** a test reads the resources that `k8s/cloudflared/kustomization.yaml` lists
- **THEN** one of them is a `policy/v1` PodDisruptionBudget with `minAvailable: 1` and `unhealthyPodEvictionPolicy: AlwaysAllow`
- **AND** its `matchLabels` are a subset of the pod template labels of Deployment `cloudflared`
