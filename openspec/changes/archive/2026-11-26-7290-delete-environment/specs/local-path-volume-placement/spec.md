## ADDED Requirements

### Requirement: A product pod on a claim requires a node off the control plane
Each pod of a manifest of `k8s/devops/` that mounts a PersistentVolumeClaim SHALL have a required node affinity in which every node selector term holds the expression `node-role.kubernetes.io/control-plane` `DoesNotExist`.

#### Scenario: A pod on a claim
- **WHEN** a person lists the pods of namespace `devops` that mount a claim with `kubectl get pods -n devops -o json`
- **THEN** each such pod has the required node affinity
- **AND** an affinity that holds the expression only as a preference, or not in each required term, does not count

## REMOVED Requirements

### Requirement: A warning before image garbage collection on a node with local-path volumes
**Reason**: The environment repository holds this alert rule and its cases (#7290).
**Migration**: Change the rule in the environment repository.

### Requirement: A pod on a claim requires a node off the control plane
**Reason**: The rule covers the charts and manifests of the environment repository (#7290).
**Migration**: See `A product pod on a claim requires a node off the control plane`.
