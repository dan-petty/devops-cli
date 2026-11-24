# Tasks

## 1. Behavior

- [x] 1.1 Add infra-apply service row and runner tools
  - Verification: `$ uv run devops ci test tests/github/test_repo_ref.py`
- [x] 1.2 Implement stop before own node and control plane node in infra apply
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py`
- [x] 1.3 Implement roadmap step infra-apply and CLI command
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_infra_apply.py`
- [x] 1.4 Wire webhook handler and service for merged infra pull requests
  - Verification: `$ uv run devops ci test tests/server/test_server_infra_apply.py`

## 2. Documents

- [x] 2.1 Update documentation and generate CLI reference
  - Verification: `$ uv run devops ci --check --only docs`
