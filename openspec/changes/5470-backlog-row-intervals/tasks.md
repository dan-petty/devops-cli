# Tasks

## 1. The cadence settings

Kind: behavior. Changes: `src/devops_cli/config/settings.py`, `tests/config/test_roadmap_row_cadence_settings.py`, `tests/security/test_config_declarations.py`.

- [x] 1.1 Write failing tests: the defaults of `interval_minutes` of the five sections are the old intervals, the backlog settings are empty, a variable sets each field, and the settings refuse a backlog interval above the interval and a value below 1.
  - Verification: `$ uv run devops ci test tests/config/test_roadmap_row_cadence_settings.py`
- [x] 1.2 Add `RowCadenceConfig` with its check and `minutes_for`, extend the sections `roadmap.intake`, `roadmap.stage`, `roadmap.fix_plan` and `roadmap.alternatives` with it, and add the section `roadmap.refine`.
  - Verification: `$ uv run devops ci test tests/config/test_roadmap_row_cadence_settings.py tests/security/test_config_declarations.py`

## 2. The due rule and the queue record

Kind: behavior. Changes: `src/devops_cli/roadmap/run.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_run_row_cadence.py`.

- [x] 2.1 Write failing tests: a variable changes the interval of stage, a recorded queue at the threshold makes stage due at the backlog interval, a queue below it keeps the interval, a success records its queue in `queues.json`, a failed row and an outcome with no queue keep the record, and an unreadable `queues.json` stops the round.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_row_cadence.py`
- [x] 2.2 Add `JobOutcome.queue` and `JobRow.cadence`, read the settings and `queues.json` at the start of a round, give each row the interval in force to the due check, and write the queue of each success.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_row_cadence.py tests/roadmap/test_roadmap_run_due_table.py`

## 3. The queue of each runner

Kind: behavior. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/run.py`, `tests/support/fakes/roadmap_store.py`, `tests/roadmap/stage/test_roadmap_stage_queue.py`, `tests/roadmap/refine/test_roadmap_refine_queue.py`, `tests/roadmap/stores/test_roadmap_store_labelled_pulls.py`.

- [x] 3.1 Write failing tests: the stage selection counts the open items that the filter names, the refine plan counts the items that the selection orders, the store gives the open pull requests with a label from its listing, and the fix_plan runner in the mode `off` gives no queue.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_queue.py tests/roadmap/refine/test_roadmap_refine_queue.py tests/roadmap/stores/test_roadmap_store_labelled_pulls.py tests/roadmap/test_roadmap_run_row_cadence.py`
- [x] 3.2 Add `StageSelection.queue`, `StagePlan.queue`, `RefinePlan.queue` and `RoadmapStore.labelled_pulls`, and give the queue in the outcome of the rows `intake`, `stage`, `fix_plan`, `refine` and `alternatives`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_queue.py tests/roadmap/refine/test_roadmap_refine_queue.py tests/roadmap/stores/test_roadmap_store_labelled_pulls.py tests/roadmap/test_roadmap_run_row_cadence.py`

## 4. The log line and the gauges

Kind: behavior. Changes: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/run.py`, `tests/telemetry/test_roadmap_row_cadence_gauges.py`.

- [x] 4.1 Write failing tests: a backlog round logs the row, the repository, the queue, the minutes and the threshold, and sends both gauges under `repo` and `row`, and `INSTRUMENTS` and `docs/TELEMETRY.md` list both gauges.
  - Verification: `$ uv run devops ci test tests/telemetry/test_roadmap_row_cadence_gauges.py`
- [x] 4.2 Add the messages and the instruments `devops_cli_roadmap_row_queue_items` and `devops_cli_roadmap_row_interval_seconds`, and log and send them after each success that gives a queue.
  - Verification: `$ uv run devops ci test tests/telemetry/test_roadmap_row_cadence_gauges.py`

## 5. Documents

Kind: other. Changes: `docs/CLUSTER.md`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/roadmap/run.py` (module docstring), the generated documents, and the snapshot of the MCP tool listing.

- [x] 5.1 Describe the cadence settings, the backlog rule, the record, the log line and the gauges in `docs/CLUSTER.md`, update the help of `devops roadmap run` and the docstring of `run.py`, and regenerate the documentation with `devops docs generate`.
  - Verification: `$ uv run devops docs check`
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_tool_listing.py`

## Workflow follow-up

- Pending a person: set the backlog values of the issue in the live ConfigMap `devops-cli-config` after the release, and check the log lines and the rounds per hour of stage and refine.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
