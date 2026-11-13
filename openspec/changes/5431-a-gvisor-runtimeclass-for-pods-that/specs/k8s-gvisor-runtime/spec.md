## Purpose

The environment tree declares the gVisor RuntimeClass, so a pod that runs untrusted code can run on a user-space kernel, and only on a node that runs `runsc`.

## ADDED Requirements

### Requirement: The environment tree declares RuntimeClass gvisor for the runsc nodes
The root kustomization of the environment tree SHALL list `runtimeclass-gvisor.yaml`. That file SHALL declare RuntimeClass `gvisor` of API `node.k8s.io/v1` with handler `runsc` and `scheduling.nodeSelector` `node-restriction.kubernetes.io/gvisor: "true"`. The class MUST NOT carry tolerations, so a pod of the class runs only on a node with the label.

#### Scenario: The root kustomization holds the class
- **WHEN** a test reads `k8s/kustomization.yaml` and `k8s/runtimeclass-gvisor.yaml`
- **THEN** the resources of the kustomization list `runtimeclass-gvisor.yaml`, and the file declares RuntimeClass `gvisor` of API `node.k8s.io/v1` with handler `runsc`

#### Scenario: The class selects only labelled nodes
- **WHEN** a test reads the `scheduling` of RuntimeClass `gvisor`
- **THEN** its `nodeSelector` is exactly `node-restriction.kubernetes.io/gvisor: "true"`, and it has no `tolerations`
