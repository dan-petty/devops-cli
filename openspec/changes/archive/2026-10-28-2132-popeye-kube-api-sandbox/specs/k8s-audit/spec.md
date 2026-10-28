## Purpose
The `devops k8s audit` command checks the resources of the current Kubernetes cluster with Popeye in the tool sandbox, reports what Popeye found, and fails when Popeye did not run.

## ADDED Requirements

### Requirement: Popeye runs in the sandbox with the kube-api profile
`devops k8s audit` SHALL run Popeye in `SandboxToolExecutor`, from a new empty directory, with the network profile `kube-api` for the current context. No option SHALL run Popeye outside the sandbox.

#### Scenario: An audit on a host that can start the sandbox
- **WHEN** `devops k8s audit` runs and Popeye reports issues
- **THEN** the command that starts Popeye starts `kubectl proxy` outside bubblewrap and Popeye in bubblewrap with `--unshare-all`, in an empty directory
- **AND** the command shows the findings and exits 0

### Requirement: A scan that did not run fails the audit
`devops k8s audit` SHALL report a pass only when Popeye ran and found nothing. When Popeye did not run, the command SHALL say that the audit did not run, with the status and the reason, report no pass, and exit 1.

#### Scenario: Popeye runs and finds nothing
- **WHEN** `devops k8s audit` runs and Popeye reports no issue
- **THEN** the command reports the pass and exits 0

#### Scenario: A host that cannot start the sandbox
- **WHEN** `devops k8s audit` runs on a host whose kernel refuses bubblewrap a user namespace
- **THEN** the command says that the audit did not run, with the status `coverage_gap` and the cause, reports no pass, and exits 1
