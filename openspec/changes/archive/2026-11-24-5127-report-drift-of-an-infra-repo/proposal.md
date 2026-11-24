# Proposal: #5127

## Why
Hosts in an infra repo can diverge from the repository configuration without notice. For example, manual edits during an incident or merged pull requests that were not applied cause drift. Argo CD shows drift for Kubernetes cluster resources, but hosts below the cluster have no drift detection. This change closes #5127 by adding drift detection for infra repos.

## What Changes
- Add the CLI command `devops infra drift <repo> [--playbook <path>] [--path <path>] [--dry-run]`.
- Plan the playbook (`site.yaml` by default) at the default branch head for every in-service host in check mode.
- Report hosts with drift and list their changed tasks and unchecked tasks.
- Exit 0 when no host drifts, 2 when at least one host drifts, and 1 when the plan fails or access is refused.
- Record the count of drifted hosts in gauge `devops_cli_infra_drift_hosts{repo}`.
- Count drift runs in counter `devops_cli_infra_runs_total{repo,command="drift",result="ok"|"drift"|"failed"}`.
- Manage one marker issue in the target infra repo via GitHub REST API: create or update the issue with drift details, leave it unchanged when the plan ID matches, and close it when drift clears.
- Support `--dry-run` to inspect drift without sending HTTP requests to GitHub.
- Enforce the `plan` agent access level.

## Capabilities
- Detect infrastructure drift across inventory hosts from check-mode execution.
- Maintain a single GitHub issue with a hidden HTML marker tracking active drift status.
- Emit Prometheus metrics for monitoring host drift and execution results.

## Impact
- Users and automated schedules can detect and track host configuration drift early.
- No changes to existing commands or database schemas.

## Feasibility
- Check mode and plan facts are already implemented and proven in `src/devops_cli/infra/plan.py` (#5124).
- GitHub REST integration uses existing `GitHubSession` and `GitHubClient` patterns.

## Existing Tool Considered
- Tool: `ansible/ansible` (https://github.com/ansible/ansible), GPL-3.0, in-use.
- Reason: Ansible check mode detects host drift from playbooks, but lacks integration with GitHub issue lifecycle, Prometheus metrics, specific exit codes (2 on drift), and dry-run execution.
- Cost to build: about 2M tokens and 3 hours.
