## ADDED Requirements

### Requirement: Drift covers plan repos
The `devops infra drift --all` command SHALL run the drift of each repo in `infra.repos` whose agent access level is `plan` or higher, and SHALL run no drift for a repo at `none`.

#### Scenario: Plan repo drifts and none repo does not
- **WHEN** `uv run pytest tests/infra/test_infra_drift_all.py -q` runs with a settings fixture that holds one repo at `plan` and one at `none`
- **THEN** the command runs the drift once for the `plan` repo and no time for the `none` repo

### Requirement: Drift CronWorkflow is daily
The `infra-drift` CronWorkflow SHALL run the `infra-drift` WorkflowTemplate once a day.

#### Scenario: Daily CronWorkflow passes the Kubernetes check
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the command prints `k8s: <N> cases, 0 failed`

### Requirement: Drift pod is a job pod with the key Secret
The `infra-drift` pod template SHALL carry the `app.kubernetes.io/name: devops-cli-job` label, SHALL run the runner image, and SHALL mount the SSH key Secret read-only as its only SSH credential.

#### Scenario: Rendered drift pod passes the Kubernetes check
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the command prints `k8s: <N> cases, 0 failed`

### Requirement: Runner image holds the Ansible runner
The runner image SHALL hold `ansible-runner`, and `RUNNER_TOOLS` SHALL name it with a `job:` reason.

#### Scenario: Runner tools name the Ansible runner
- **WHEN** `uv run pytest tests/roadmap/test_roadmap_runner_tools.py -q` runs
- **THEN** `ansible-runner` is in `RUNNER_TOOLS` with a `job:` reason

### Requirement: Drift egress is SSH to node CIDRs only
The `infra-ssh-egress` NetworkPolicy SHALL admit TCP 22 egress from the drift and plan pods only to the configured node CIDRs.

#### Scenario: Rendered policy passes the Kubernetes check
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the command prints `k8s: <N> cases, 0 failed`
