# Tasks

## 1. Add the idle interval setting

Kind: behavior. Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`. Changes: the same paths, `tests/config/test_service_poll_intervals.py`.

- [x] 1.1 Add `service.poll_interval_idle_seconds` with a default of 600 and a validator that refuses a value below `poll_interval_seconds`
  - Verification: `$ uv run devops ci test tests/config/test_service_poll_intervals.py` passes

## 2. Poll an idle repository less often

Kind: behavior. Reads: `src/devops_cli/server/service.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/serve.py`. Changes: the same paths, `tests/server/test_server_service.py`, `tests/roadmap/test_roadmap_service_idle.py`.

- [x] 2.1 Keep the idle state per repository, and give each repository the interval that its state names
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py` passes
- [x] 2.2 Have the lane job report the state from the store, and a webhook clear it
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_service_idle.py tests/roadmap/test_roadmap_run_lanes.py` passes

## 3. Run the gates

Kind: other. Reads: `tests/`. Changes: none.

- [x] 3.1 Run the gate of the branch
  - Verification: `$ uv run devops ci test tests/config tests/server tests/roadmap` passes
  - Verification: `$ uv run devops ci --check --only lint,format,typecheck` passes
