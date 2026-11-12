# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: the join of hosts and nodes (a cordoned node, a NotReady node, a host in `offline` with no node, a node with no host), the node name, the table, the SSH check from job events, the access level of `--ping`, no `ansible-runner` without `--ping`, and a dry run with no request
  - Verification: `$ uv run devops ci test tests/infra/test_status.py tests/infra/test_access.py tests/commands/test_infra_status.py`
- [x] 1.2 Add `infra/status.py`, `require_agent_level`, the models and the command `devops infra status`
  - Verification: `$ uv run devops ci test tests/infra/test_status.py tests/infra/test_access.py tests/commands/test_infra_status.py`
- [x] 1.3 Run the command live on dan-petty/homelab, with and without `--ping`
  - Verification: `$ uv run devops infra status dan-petty/homelab --ping`

## 2. Documents

- [x] 2.1 Regenerate the command reference
  - Verification: `$ uv run devops ci docs`
