# Proposal: #3672

## Why

A repository with no open work polls at the same rate as a busy repository. In the window of #3497, an idle repository cost 1178 to 1373 requests a day, and the shared budget stood at or above 1990 of 2000 for 246 of 1440 minutes. `service.poll_interval_seconds` is one value for all repositories, and `RequestBudget.poll_interval` looks only at the cost of a round, not at the open work of a repository. Closes #3672.

## What Changes

- The `service` section gains `service.poll_interval_idle_seconds`, default 600 seconds, and a value below `poll_interval_seconds` is a validation error that names both settings.
- The Service reads each repository's last round: a repository with no open issue and no open pull request gets the idle interval, and one with open work keeps the normal interval.
- A webhook delivery clears the idle state and starts the update at once, as ADR 0017 says.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-limits`: A repository with no open work polls at the idle interval.

## Impact

- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/server/service.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/serve.py`
- Tests: `tests/config/test_service_poll_intervals.py` (new), `tests/server/test_server_service.py`, `tests/roadmap/test_roadmap_service_idle.py` (new)

## Feasibility

Read on 2026-11-14 against `origin/main` at `04107728d`.

- One interval serves every repository: `src/devops_cli/config/settings.py:1573:poll_interval_seconds`.
- The engine sleeps the budget-aware interval: `src/devops_cli/server/service.py:853:def poll_interval` and `:848:await self.sleep_func(self.poll_interval())`.
- The store answers both counts from its listing: `src/devops_cli/roadmap/stores/store.py:1033:def open_items` and `:1037:def open_pulls`.
- The job opens the store: `src/devops_cli/roadmap/run.py:2016:service_job`.
- The new tests pass on the branch: `uv run devops ci test tests/config/test_service_poll_intervals.py tests/roadmap/test_roadmap_service_idle.py tests/server/test_server_service.py`.

## Existing Tool Considered

ADR 0003 keeps the poll and ADR 0017 keeps the webhooks. No open tool sets a slower poll for a repository with no work, and the change adds one setting to the loop the project already runs. The work is about 80 lines of code and 120 lines of tests.
