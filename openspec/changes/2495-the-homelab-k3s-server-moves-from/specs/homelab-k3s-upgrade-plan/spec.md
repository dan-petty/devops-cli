## Purpose
The plan in `k8s/README.md` that moves the homelab k3s server from v1.31 to a release within one minor version of the pinned kubectl, with the check that gates each step and the check after the last one.

## ADDED Requirements

### Requirement: The upgrade plan names each step and its check
`k8s/README.md` SHALL hold a k3s upgrade plan that lists each single-minor step from v1.31 to v1.37 and names the check to run before that step.

#### Scenario: The plan lists every step in order
- **WHEN** a test reads `k8s/README.md`
- **THEN** the plan section names the steps v1.31 to v1.32, v1.32 to v1.33, v1.33 to v1.34, v1.34 to v1.35, v1.35 to v1.36 and v1.36 to v1.37, in that order

#### Scenario: Each step names its check
- **WHEN** a test reads the plan section of `k8s/README.md`
- **THEN** each step names at least one command that reads the cluster before the step runs

### Requirement: The plan names the target and the skew it closes
`k8s/README.md` SHALL name the target k3s release range and the kubectl release whose supported skew it closes, and SHALL name the command that shows the skew is gone after the last step.

#### Scenario: The target is within the supported skew
- **WHEN** a test reads `k8s/README.md`
- **THEN** the plan names the target as 1.37.x and names the pinned kubectl release 1.37.1

#### Scenario: The plan names the check after the last step
- **WHEN** a test reads the plan section of `k8s/README.md`
- **THEN** the plan names `devops k8s deploy-stack --stack devops` as the command whose output must hold no skew warning
