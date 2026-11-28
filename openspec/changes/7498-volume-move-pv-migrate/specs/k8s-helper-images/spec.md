## MODIFIED Requirements

### Requirement: Missing template error
A command that needs a template MUST fail with an error that names the missing CronJob and its namespace `devops` when the cluster has none.

#### Scenario: Missing template CronJob
- **WHEN** the cluster returns an empty body for the template read
- **THEN** the command raises `ServiceProbeError` naming `devops/service-probe`

## REMOVED Requirements

### Requirement: Volume move image from template
**Reason**: The volume move copies with pv-migrate, whose own images run the copy, so no pod of the move reads an image from CronJob `devops/volume-move` (#7498).
**Migration**: None. The CronJob `devops/volume-move` is gone from `k8s/devops/`.
