# command-dry-run-class Specification Delta

## ADDED Requirements

### Requirement: k8s-cluster-request-plans
The eleven external-request commands in `k8s` (`audit`, `contexts`, `logs`, `pods`, `port-forward`, `rbac-audit`, `security-stream`, `service-url`, `status`, `stream-logs`, and `switch-context`) SHALL carry the `request-plan` dry-run class. Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.

#### Scenario: Dry run on k8s pods
- **WHEN** user executes `devops k8s pods --dry-run`
- **THEN** no external request is made and the planned Kubernetes API list pods request is printed

#### Scenario: Dry run on k8s audit
- **WHEN** user executes `devops k8s audit --dry-run`
- **THEN** no cluster scan is executed and the planned Popeye command is printed

#### Scenario: Dry run on k8s port-forward
- **WHEN** user executes `devops k8s port-forward --dry-run`
- **THEN** no daemon is started and the planned kubectl port-forward commands are printed

### Requirement: k8s-cluster-no-external-request
The three local commands in `k8s` (`gpu-matrix`, `port-forward-status`, and `port-forward-stop`) SHALL carry the `no-external-request` dry-run class.
`k8s gpu-matrix` and `k8s port-forward-status` SHALL execute normally without external requests under `devops --dry-run`.
`k8s port-forward-stop` SHALL accept `--dry-run` and print how many daemons it would stop without terminating any process.

#### Scenario: Dry run on local command k8s gpu-matrix
- **WHEN** user executes `devops --dry-run k8s gpu-matrix`
- **THEN** the command runs normally and prints the local GPU matrix

#### Scenario: Dry run on k8s port-forward-stop
- **WHEN** user executes `devops k8s port-forward-stop --dry-run`
- **THEN** no process receives a termination signal and the preview output describes the action
