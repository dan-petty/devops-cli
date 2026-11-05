## ADDED Requirements

### Requirement: A setting names the limit on Planned items
The setting `roadmap.stage.planned_limit` SHALL be the count of open Planned items at which the stage job plans no new item. It SHALL have the variable `DEVOPS_CLI_ROADMAP_STAGE_PLANNED_LIMIT`, the default 20 and a least value of 1. The example ConfigMap of the Service SHALL hold the default.

#### Scenario: The default
- **WHEN** no config file and no variable sets `roadmap.stage.planned_limit`
- **THEN** the limit is 20

#### Scenario: A config file and a variable
- **WHEN** the config file sets `roadmap.stage.planned_limit` to 7 and then the variable `DEVOPS_CLI_ROADMAP_STAGE_PLANNED_LIMIT` holds 9
- **THEN** the limit is 7 from the file and 9 with the variable

#### Scenario: A limit under 1
- **WHEN** the config file sets `roadmap.stage.planned_limit` to 0
- **THEN** loading the settings fails

### Requirement: The stage job plans no new item at the limit on Planned items
When the count of open Planned items is at `roadmap.stage.planned_limit` or over it, the stage job SHALL take no item. It SHALL leave out each item that passes every other rule, with a reason that names the count and the setting. An item with the priority `P0-Critical` SHALL pass the limit, and so SHALL the item that `--item` names. The count SHALL hold open items with the Status Planned only. The limit SHALL NOT apply to the filing of issues.

#### Scenario: At the limit
- **WHEN** 2 items are Planned, the limit is 2, and a Ready item passes every other rule
- **THEN** the job takes no item, and the reason of the Ready item names the count 2 and the setting `roadmap.stage.planned_limit`

#### Scenario: Under the limit
- **WHEN** 1 item is Planned, the limit is 2, and two Ready items pass every other rule
- **THEN** the job takes both items

#### Scenario: An item of the highest priority
- **WHEN** 2 items are Planned, the limit is 2, and a Ready `P0-Critical` item and a Ready `P1-High` item pass every other rule
- **THEN** the job takes the `P0-Critical` item and leaves out the `P1-High` item with the reason of the limit

#### Scenario: A closed item and an item of another Status
- **WHEN** 1 open item is Planned, 1 closed item is Planned, 1 item is Staged, and the limit is 2
- **THEN** the count is 1 and the job takes a Ready item

#### Scenario: A named item
- **WHEN** 2 items are Planned, the limit is 2, and `--item` names a Ready item
- **THEN** the job takes that item

#### Scenario: Another rule fails first
- **WHEN** 2 items are Planned, the limit is 2, and a Ready item is claimed by a person
- **THEN** the reason of that item is the claim, not the limit

#### Scenario: The command at the limit
- **WHEN** 1 item is Planned, the setting is 1, and `devops roadmap stage --plan` runs with Ready items
- **THEN** the plan holds no branch, makes no model call, and lists each Ready item as left out with the reason of the limit
