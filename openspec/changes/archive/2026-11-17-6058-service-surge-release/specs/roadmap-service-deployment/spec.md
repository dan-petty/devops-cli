## REMOVED Requirements

### Requirement: The Service runs as one pod
**Reason**: The Lease `roadmap-service-rows`, not the strategy, now keeps the rows to one pod, and the strategy changes to a surge release in a second step (#6058, #6107). Its scenario read a value of the manifest, which the owner rule of 2026-11-16 leaves to kubeconform (#6060).
**Migration**: The requirements "The Service keeps Recreate until its Lease code runs" and "One pod of the Service holds the rows" hold the rule: one replica, `Recreate` until the Lease code runs, and the Lease `roadmap-service-rows` that lets one pod run the rows.

## ADDED Requirements

### Requirement: The Service keeps Recreate until its Lease code runs
`deployment/roadmap-service` SHALL set `replicas: 1` and the `Recreate` strategy until the release that carries the Lease code of the rows runs, so that release stops the old pod, which has no Lease code, before the new pod starts. The switch to `RollingUpdate` with `maxSurge: 1` and `maxUnavailable: 0` SHALL come in a second change (#6107). The readiness of a pod SHALL NOT wait for the Lease `roadmap-service-rows`.

#### Scenario: The release that carries the Lease code
- **WHEN** that release replaces a pod that has no Lease code
- **THEN** the old pod stops before the new pod starts, and the new pod takes the Lease and runs the rows

### Requirement: One pod of the Service holds the rows
Only the pod that holds the Lease `roadmap-service-rows` (`coordination.k8s.io/v1`) SHALL read the state files of the rows and run the workers and the poll. A pod that waits for the Lease SHALL keep each delivery in its lane queues until it takes the Lease. A pod SHALL give the Lease back after its drain, and a holder that is killed SHALL lose it after its `leaseDurationSeconds`.

#### Scenario: A pod waits while the holder drains
- **WHEN** a pod holds the Lease and drains, and another pod is ready
- **THEN** the other pod takes deliveries and runs no round, and it takes the Lease only after the holder gives it back

#### Scenario: The holder is killed
- **WHEN** the holder stops with no release
- **THEN** the other pod takes the Lease at its first try after `leaseDurationSeconds` from its first read of the holder, and not before

#### Scenario: The holder cannot renew the Lease
- **WHEN** no renewal works for the renew deadline
- **THEN** the pod stops its workers and its poll, cuts the budget, and `/healthz` fails
