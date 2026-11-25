## Purpose

Keep stage agent phase snapshot tests independent of the wall clock when testing prepared run folders whose deadlines were generated with a frozen `NOW`.

## ADDED Requirements

### Requirement: Stage snapshot tests match the prepared clock
`test_agent_phase_offers_stock_tools_only_without_read_issue_or_find_issues` MUST run `run_stage_agent` under the same frozen `NOW` timestamp passed to `prepare_stage_job` so `within_budget` does not expire against real wall-clock time.

#### Scenario: Running after 13:00 UTC on 2026-11-25
- **WHEN** `prepare_stage_job` receives `now=NOW` and `run_stage_agent` runs under `time_machine.travel(NOW, tick=False)`
- **THEN** `run_stage_agent` invokes the model once and `script.tools_offered` equals `stock.tools_offered`
