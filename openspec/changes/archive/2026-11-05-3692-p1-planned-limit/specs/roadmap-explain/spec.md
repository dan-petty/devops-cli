## MODIFIED Requirements

### Requirement: The command names the limit on Planned items
For the stage job, `devops roadmap explain <issue>` SHALL print `no` for an item that the limit `roadmap.stage.planned_limit` holds, and the reason SHALL name the setting, the count of open Planned items and the priorities that pass the limit. It SHALL print `yes` for an item with the priority `P1-High` that passes every other rule. When no `--limit` or other option names it, the limit SHALL be the setting that the Service uses.

#### Scenario: An item that the limit holds
- **WHEN** 2 items are Planned, the setting is 2, and a Ready `P2-Medium` item passes every other rule
- **THEN** the stage job is `no`, and the reason names `roadmap.stage.planned_limit`, the count 2, and `P0-Critical or P1-High`

#### Scenario: A P1 item at the limit
- **WHEN** 1 item is Planned, the setting is 1, and a Ready `P1-High` item passes every other rule
- **THEN** the stage job is `yes`

#### Scenario: An item under the limit
- **WHEN** 2 items are Planned, the setting is 3, and a Ready `P2-Medium` item passes every other rule
- **THEN** the stage job is `yes`

#### Scenario: The limit from the settings
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_PLANNED_LIMIT` holds 1, 1 item is Planned, and a Ready `P2-Medium` item passes every other rule
- **THEN** the stage job is `no` with the reason of the limit
