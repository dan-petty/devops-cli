## ADDED Requirements

### Requirement: A volume move can change the access mode of the claim
`devops k8s volume move <namespace>/<claim> --access-mode <mode>` SHALL make `<claim>-move` and the claim made again with `accessModes: [<mode>]`. A mode equal to the access modes of the old claim SHALL be a move that keeps them, and a mode that Kubernetes does not name SHALL be refused. `--plan` SHALL print the access modes before and after the move.

#### Scenario: A claim of two Deployments becomes ReadWriteMany
- **WHEN** a move of a `local-path` claim that two Deployments mount runs with `--storage-class longhorn --access-mode ReadWriteMany`
- **THEN** the move claim and the claim made again have `accessModes: [ReadWriteMany]`, and the pods of the two Deployments can run on two storage nodes

#### Scenario: An unknown access mode
- **WHEN** the move runs with `--access-mode ReadWriteSome`
- **THEN** the plan raises `VolumeMoveRefusedError` that names the four access modes, and the cluster gets no request that changes it
