# Design

## Decisions

### 1. Re-use `run_plan` from `infra.plan`
- **Decision**: Execute the check-mode plan by calling `run_plan` with the default branch head, specified playbook (`site.yaml` default), and no host limit.
- **Reason**: `run_plan` already executes Ansible check mode in an isolated checkout, parses runner events, identifies changed/unchecked/disruptive tasks, and computes deterministic plan IDs.

### 2. Extend `devops_cli_infra_runs_total`
- **Decision**: Extend counter `devops_cli_infra_runs_total` with label `command="drift"` and results `"ok"`, `"drift"`, and `"failed"`.
- **Reason**: Keeps telemetry unified across infra operations (`apply`, `node drain`, `node uncordon`, `node restart`, `node reboot`, `drift`).

### 3. Add `devops_cli_infra_drift_hosts` gauge
- **Decision**: Register gauge `devops_cli_infra_drift_hosts` with label `repo` set to the number of hosts with drift.
- **Reason**: Operators and dashboards need a continuous gauge of hosts out of sync with configuration.

### 4. Single GitHub marker issue tracked by hidden HTML comment
- **Decision**: Identify the drift issue in the infra repository using a hidden HTML comment: `<!-- devops-infra-drift: {repo} {plan_id} -->`.
- **Reason**: Hidden comments survive title and label changes by users. The issue is updated when `plan_id` changes, closed when drift clears, and skipped when `plan_id` is identical.

### 5. Access level requirement
- **Decision**: Require agent access level `plan`.
- **Reason**: The command only reads the repository and checks hosts without modifying them. A repo configured at level `none` refuses agent access.

## Rejected alternatives

### 1. Separate counter `devops_cli_infra_drift_runs_total`
- **Rejected**: Adding a distinct counter requires separate queries and dashboards.
- **Evidence**: `devops_cli_infra_runs_total` already divides runs by command label.

### 2. Compare rendered issue body instead of plan ID
- **Rejected**: Minor formatting, timestamp, or ordering changes cause redundant write requests when underlying facts are identical.
- **Evidence**: `plan_id` is a canonical SHA-256 digest of plan facts (`PlanContent`), making it deterministic.

### 3. Track issue state via issue label or title
- **Rejected**: Labels can be removed manually, and titles can be edited, leading to duplicate issues.
- **Evidence**: Hidden HTML comments persist through title edits and user labels.

### 4. Require `safe` agent access level
- **Rejected**: The command does not apply changes or modify hosts.
- **Evidence**: `plan` level provides sufficient read and check mode privileges without granting apply rights.
