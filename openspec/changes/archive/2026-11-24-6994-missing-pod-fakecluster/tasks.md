# Tasks

## 1. Behavior

- [x] 1.1 Return not found for unknown pods in `FakeCluster._read_pod_single` in `tests/support/infra.py`
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py`
- [x] 1.2 Verify `test_an_agent_stops_before_the_control_plane_node` passes with `HOSTNAME` set in `tests/commands/test_infra_apply.py`
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py`

## 2. Verification

- [x] 2.1 Run local quality gates
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py`
