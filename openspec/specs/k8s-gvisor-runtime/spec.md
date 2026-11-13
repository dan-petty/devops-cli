# k8s-gvisor-runtime Specification

## Purpose
The environment tree declares the gVisor RuntimeClass, so a pod that runs untrusted code can run on a user-space kernel, and only on a node that runs `runsc`.

## Requirements

### Requirement: The environment tree declares RuntimeClass gvisor for the runsc nodes
The root kustomization of the environment tree SHALL list `runtimeclass-gvisor.yaml`. That file SHALL declare RuntimeClass `gvisor` of API `node.k8s.io/v1` with handler `runsc` and `scheduling.nodeSelector` `node-restriction.kubernetes.io/gvisor: "true"`. The class MUST NOT carry tolerations, so a pod of the class runs only on a node with the label.

#### Scenario: The root kustomization holds the class
- **WHEN** a test reads `k8s/kustomization.yaml` and `k8s/runtimeclass-gvisor.yaml`
- **THEN** the resources of the kustomization list `runtimeclass-gvisor.yaml`, and the file declares RuntimeClass `gvisor` of API `node.k8s.io/v1` with handler `runsc`

#### Scenario: The class selects only labelled nodes
- **WHEN** a test reads the `scheduling` of RuntimeClass `gvisor`
- **THEN** its `nodeSelector` is exactly `node-restriction.kubernetes.io/gvisor: "true"`, and it has no `tolerations`

### Requirement: RuntimeClass gvisor declares the measured pod overhead
RuntimeClass `gvisor` in `k8s/runtimeclass-gvisor.yaml` SHALL declare `overhead.podFixed` with a `memory` value from a measurement of `runc` against `runsc` on a labelled node. The value SHALL be the measured memory, rounded up to a whole MiB. The measurement of #5434 gave 15.1 MiB, so the value SHALL be `16Mi`. The class MUST NOT declare a `cpu` overhead, because the measurement found no CPU overhead.

#### Scenario: The class declares only the measured memory overhead
- **WHEN** a test reads the `overhead` of RuntimeClass `gvisor` in `k8s/runtimeclass-gvisor.yaml`
- **THEN** it is exactly `podFixed: {memory: 16Mi}`, with no `cpu` key
