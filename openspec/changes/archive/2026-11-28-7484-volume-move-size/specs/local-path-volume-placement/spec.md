## ADDED Requirements

### Requirement: A volume move can make the new claim larger
`devops k8s volume move <namespace>/<claim> --size <quantity>` SHALL make `<claim>-move` and the claim made again with that storage request. The plan SHALL refuse a size that is not a Kubernetes quantity or that is under the size of the old claim, and a size equal to it SHALL be a move that keeps the size. `--plan` SHALL print the size before and after the move.

#### Scenario: Data larger than the claim
- **WHEN** a `local-path` claim of 1Gi holds 1.2 GiB, and the move runs with `--storage-class longhorn --size 2Gi`
- **THEN** both new claims request 2Gi, the copy fits, and the two sides are equal

#### Scenario: A smaller size
- **WHEN** the move of a claim of 5Gi runs with `--size 1Gi`
- **THEN** the plan raises `VolumeMoveRefusedError` that names both sizes, and the cluster gets no request that changes it
