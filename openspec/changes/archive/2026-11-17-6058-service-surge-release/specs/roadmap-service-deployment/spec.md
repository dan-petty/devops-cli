## REMOVED Requirements

### Requirement: The Service runs as one pod
**Reason**: A surge release runs the old and the new pod at the same time, so the Service no longer uses `Recreate` (#6058). Its scenario read a value of the manifest, which the owner rule of 2026-11-16 leaves to kubeconform (#6060).
**Migration**: The requirements "The Service rolls with a surge release" and "One pod of the Service holds the rows" hold the rule: one replica, a surge release, and the Lease `roadmap-service-rows` that lets one pod run the rows.

## ADDED Requirements

### Requirement: The Service rolls with a surge release
`deployment/roadmap-service` SHALL set `replicas: 1` and the `RollingUpdate` strategy with `maxSurge: 1` and `maxUnavailable: 0`. The readiness of a pod SHALL NOT wait for the Lease `roadmap-service-rows`, so the new pod of a release gets the webhooks before the old pod gets SIGTERM.

#### Scenario: A release starts
- **WHEN** the new pod of a release starts while the old pod holds the Lease
- **THEN** `/readyz` of the new pod answers 200, and the new pod takes deliveries before the old pod stops

### Requirement: One pod of the Service holds the rows
Only the pod that holds the Lease `roadmap-service-rows` (`coordination.k8s.io/v1`) SHALL read the state files of the rows and run the workers and the poll. A pod that waits for the Lease SHALL keep each delivery in its lane queues until it takes the Lease. A pod SHALL give the Lease back after its drain, and a holder that is killed SHALL lose it after its `leaseDurationSeconds`.

#### Scenario: The old pod drains during a release
- **WHEN** the old pod holds the Lease and drains, and the new pod is ready
- **THEN** the new pod takes deliveries and runs no round, and it takes the Lease only after the old pod gives it back

#### Scenario: The holder is killed
- **WHEN** the holder stops with no release
- **THEN** the other pod takes the Lease at its first try after `leaseDurationSeconds` from its first read of the holder, and not before

#### Scenario: The holder cannot renew the Lease
- **WHEN** no renewal works for the renew deadline
- **THEN** the pod stops its workers and its poll, cuts the budget, and `/healthz` fails
