## ADDED Requirements

### Requirement: The command names the limit on Planned items
For the stage job, `devops roadmap explain <issue>` SHALL print `no` for an item that the limit `roadmap.stage.planned_limit` holds, and the reason SHALL name the setting and the count of open Planned items. When no `--limit` or other option names it, the limit SHALL be the setting that the Service uses.

#### Scenario: An item that the limit holds
- **WHEN** 2 items are Planned, the setting is 2, and a Ready item passes every other rule
- **THEN** the stage job is `no`, and the reason names `roadmap.stage.planned_limit` and the count 2

#### Scenario: An item under the limit
- **WHEN** 2 items are Planned, the setting is 3, and a Ready item passes every other rule
- **THEN** the stage job is `yes`

#### Scenario: The limit from the settings
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_PLANNED_LIMIT` holds 1, 1 item is Planned, and a Ready item passes every other rule
- **THEN** the stage job is `no` with the reason of the limit
