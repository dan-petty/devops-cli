# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: a `semgrep` on PATH is the one that runs; a `semgrep` only in `~/.local/bin` gives `DependencyError` with a hint; no `ruff` on PATH gives `DependencyError` with a hint; the Ansible environment is the resolved folder of the `ansible-runner` on PATH, and none without it
  - Verification: `$ uv run devops ci test tests/infra/test_ansible_facts.py tests/commands/test_review_rules_pack.py tests/review/test_review_group_analysis.py`
- [x] 1.2 Find `ruff`, `semgrep` and `ansible-runner` on PATH only, and remove the version of the Ansible environment from the onboard row and the plan record
  - Verification: `$ uv run devops ci test tests/infra tests/commands/test_infra_apply.py tests/commands/test_infra_onboard.py tests/commands/test_infra_plan.py tests/commands/test_infra_status.py`

## 2. Documents

- [x] 2.1 Update the messages and the specs of infra-onboard, infra-plan and review-tool-runs
  - Verification: `$ uv run devops ci docs`
