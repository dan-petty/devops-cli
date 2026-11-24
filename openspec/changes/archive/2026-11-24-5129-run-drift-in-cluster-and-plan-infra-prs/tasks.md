# Tasks

## 1. Behavior

- [x] 1.1 Support `--all` in `devops infra drift` to check repos at access level `plan` or higher
  - Verification: `$ uv run pytest tests/infra/test_infra_drift_all.py -q`
- [x] 1.2 Register `ansible-runner` in `RUNNER_TOOLS` with a `job:` reason
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_runner_tools.py -q`
- [x] 1.3 Add Argo CronWorkflow and WorkflowTemplate manifests for `infra-drift`
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.4 Add NetworkPolicy `infra-ssh-egress` for TCP 22 access to node CIDRs
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.5 Add `infra-plan` step and command to post marked comments on pull requests
  - Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_step_infra_plan.py -q`
- [x] 1.6 Launch `infra-plan` Job on `pull_request` `synchronize` in webhook router
  - Verification: `$ uv run pytest tests/server/test_server_infra_plan.py -q`

## 2. Documents

- [x] 2.1 Update CLI reference and Kubernetes documentation
  - Verification: `$ uv run devops ci docs`
