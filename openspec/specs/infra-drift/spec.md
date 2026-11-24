# infra-drift Specification

## Purpose

How `devops infra drift` detects divergence between declared configuration and live hosts of an infra repo, reports changed and unchecked tasks, manages an issue lifecycle in GitHub, and records metrics.

## Requirements

### Requirement: Drift exit codes
The command SHALL exit 0 with no drift, 2 with drift on at least one host, and 1 when a plan fails.

#### Scenario: One host drifts
- **WHEN** a test runs `devops infra drift` on recorded plan events where one host has a changed task
- **THEN** the command exits 2 and prints the host name and the changed task

### Requirement: Drift host gauge
Each run SHALL set the gauge `devops_cli_infra_drift_hosts` with the label `repo` to the number of hosts with drift.

#### Scenario: Gauge with drift and with no drift
- **WHEN** a test runs the command on recorded plan events with two hosts in drift and then with none
- **THEN** the gauge sample for the repo reads 2 after the first run and 0 after the second

### Requirement: Run counter
Each run SHALL add one to `devops_cli_infra_runs_total` with the repo, the command `drift` and the result `ok`, `drift` or `failed`.

#### Scenario: Counter result with drift
- **WHEN** a test runs the command with drift and reads the counter samples from the registry
- **THEN** one sample has the labels `command=drift` and `result=drift` with the value 1

### Requirement: Drift issue
A run with drift SHALL open one issue in the infra repo, or update its open marker issue, with the hosts, the changed and unchecked tasks and the plan id.

#### Scenario: First run with drift
- **WHEN** a test runs the command with drift and an HTTP fake that records each request
- **THEN** the fake records one issue create whose body holds the marker, the host, the changed task, the unchecked task and the plan id

### Requirement: No write for the same drift
A run whose plan id equals the plan id in the marker issue SHALL send no write request.

#### Scenario: Second run with the same plan id
- **WHEN** a test runs the command twice on the same recorded plan events
- **THEN** the HTTP fake records no create, update or comment request on the second run

### Requirement: Close when drift clears
A run with no drift SHALL close the open marker issue of the infra repo.

#### Scenario: Drift clears
- **WHEN** a test runs the command with no drift and an open marker issue
- **THEN** the HTTP fake records one close request for that issue

### Requirement: Failed plan
A run whose plan ends `failed` SHALL exit 1 and SHALL write no issue.

#### Scenario: Plan fails
- **WHEN** a test runs the command on recorded plan events that end `failed`
- **THEN** the command exits 1 and the HTTP fake records no issue create or update

### Requirement: Dry run
`devops infra drift --dry-run` SHALL send no HTTP request.

#### Scenario: Dry run with drift
- **WHEN** a test runs the command with `--dry-run` on recorded plan events with drift
- **THEN** the HTTP fake records zero requests and the command exits 2

### Requirement: Access level gate
The command MUST refuse to run when the agent access level of the infra repo is below `plan`.

#### Scenario: Repo at level none
- **WHEN** a test sets the agent access level of the infra repo to `none` and runs the command
- **THEN** the command exits 1, prints the level and the required level, and the HTTP fake records no request

### Requirement: Task names in the report
The report SHALL name each changed task and each unchecked task of each host with drift.

#### Scenario: A task writes the kubelet config file
- **WHEN** a test runs the command on recorded plan events where the task that writes the kubelet config file is changed
- **THEN** the issue body names that task and the plan id

### Requirement: Playbook and commit
The command SHALL plan the playbook that `--playbook` names, `site.yaml` by default, at the head of the default branch of the infra repo.

#### Scenario: Explicit playbook
- **WHEN** a test runs the command with `--playbook harden.yaml` and a recorded head commit
- **THEN** the recorded plan call names `harden.yaml` and that commit

### Requirement: Live drift check on the homelab repo
The item MUST record a live run of `uv run devops infra drift dan-petty/homelab` in a PR comment with the exit code, the hosts with drift and the issue that the run opened or the fact that none was needed.

#### Scenario: Live run on dan-petty/homelab
- **WHEN** a person runs `uv run devops infra drift dan-petty/homelab` at the head of the default branch
- **THEN** the command exits 0 or 2, prints each host with drift, and names the issue that it opened or updated
