## MODIFIED Requirements

### Requirement: The job takes a Staged or a Planned item that the filter names
A Staged item SHALL have a recorded branch on `origin` and an open draft pull request. The pair is `implement.branch` and `implement.pr`, else `stage.branch` and `stage.pr`. A Planned item SHALL have no recorded branch on `origin` and its change folder on `origin/<default branch>`. A branch on `origin` makes it Staged. The default filter SHALL be `status=ready` and `status=planned`, and the effort passes SHALL apply to it. `--limit` SHALL default to 1.

#### Scenario: The default filter
- **WHEN** the roadmap holds a Staged Ready P1 bug of low effort, a Staged Ready P1 bug of high effort, a Staged Ready P3 feature of low effort, and a Staged Ready P2 bug of medium effort
- **THEN** the plan selects the first item when the limit is 1, and with a limit of 2 it selects the first item and the feature; it does not select the bug of high effort, and it does not select the bug of medium effort, which the fallback pass takes only when no low-effort item is selectable

#### Scenario: A plan on the default branch and a branch that is gone
- **WHEN** a Ready P1 bug of low effort has a record with a merged `stage.pr` and a `stage.branch` that is not on `origin`, and `origin/main` holds its change folder
- **THEN** the plan selects it as a Planned item, with the branch `fix/<issue>-<slug>` and no pull request, and the slug is the one of the change folder

#### Scenario: A plan on the default branch and a branch that is there
- **WHEN** the staged branch of the item is on `origin` with an open draft, and `origin/main` also holds the change folder
- **THEN** the plan selects the item with its staged branch and its pull request, as a Staged item

#### Scenario: Two Planned items
- **WHEN** two Ready P1 bugs of low effort have their change folders on `origin/main`, and the limit is 2
- **THEN** the plan selects both, the lower number first

#### Scenario: A Planned feature
- **WHEN** a Ready P2 item titled `feat(cli): add a flag`, of low effort, has its change folder on `origin/main` and no branch
- **THEN** the plan selects it as a Planned item with the branch `feat/<issue>-<slug>`

#### Scenario: An item with the Status Planned
- **WHEN** a P1 bug of low effort has the Status Planned and its change folder is on `origin/main`
- **THEN** the plan selects it as a Planned item

### Requirement: The plan lists the items that matched no filter when asked
`implement --plan` SHALL list, under "Matched no filter" and only with `--why`, each open item that the filter does not name. Each line SHALL name the family that the item misses, the values the filter takes, and the value the item has. The section SHALL not be part of "Left out". Without `--why`, the output SHALL not change.

#### Scenario: Why
- **WHEN** the default filter is in force and a Planned item holds `effort/high`
- **THEN** `implement --plan --why` lists the item under "Matched no filter" with the family `effort`, the values `low or medium`, and the value `high`

#### Scenario: No why
- **WHEN** the same plan runs without `--why`
- **THEN** the output has no section "Matched no filter"

## ADDED Requirements

### Requirement: The job takes the effort passes in order
The job SHALL run one pass for each value of the setting `roadmap.implement.effort`, in the order of the setting. Each pass SHALL take the items of its effort that the filter names, highest priority first. The first pass that takes an item SHALL supply the run, up to the limit.

#### Scenario: A low-effort item is taken before a medium-effort item
- **WHEN** the store holds a Staged Ready P0 item of medium effort and a Staged Ready P2 item of low effort, and the limit is 1
- **THEN** the plan selects the low-effort item and does not select the medium-effort item

#### Scenario: A medium-effort item is taken when no low-effort item is selectable
- **WHEN** the store holds one Staged Ready item of medium effort and no low-effort item, and the limit is 1
- **THEN** the plan selects the medium-effort item, and the plan names the effort pass `medium` as the fallback

#### Scenario: A high-effort item stays out of the default set
- **WHEN** the store holds one Staged Ready item of high effort and no low-effort or medium-effort item
- **THEN** the plan selects no item

### Requirement: A pass that takes no item lets the next pass run
A pass that takes no item SHALL let the next pass run. The items that an earlier pass left out SHALL keep their reasons.

#### Scenario: A claimed low-effort item lets the fallback pass take a medium-effort item
- **WHEN** an agent claims the only Staged Ready low-effort item, a Staged Ready item of medium effort is free, and the limit is 1
- **THEN** the plan selects the medium-effort item and leaves out the low-effort item with the reason that it is claimed

### Requirement: An explicit effort filter replaces the set
When the filter names `effort`, the job SHALL run one pass with the filter as given, and the setting SHALL not apply.

#### Scenario: An explicit effort filter replaces the set
- **WHEN** the job runs with `--filter effort=high`, and the store holds a Staged Ready item of high effort and a Staged Ready item of low effort
- **THEN** the plan selects the high-effort item only

### Requirement: The effort set is a setting
The setting `roadmap.implement.effort` SHALL hold the ordered effort values of the job, and SHALL default to `low` and then `medium`. Each value SHALL be `low`, `medium` or `high`. The setting SHALL refuse a value that is no effort value, and a value that it holds twice. The refusal SHALL name the value.

#### Scenario: One effort value in the set
- **WHEN** the setting `roadmap.implement.effort` holds `low` only, and the store holds one Staged Ready item of medium effort and no low-effort item
- **THEN** the plan selects no item

#### Scenario: The default set
- **WHEN** no config file or variable sets `roadmap.implement.effort`
- **THEN** the setting is `low` and then `medium`

#### Scenario: An unknown value
- **WHEN** `roadmap.implement.effort` holds `low` and `huge`
- **THEN** the settings load fails with a validation error that names `huge`

#### Scenario: A value held twice
- **WHEN** `roadmap.implement.effort` holds `low` and `low`
- **THEN** the settings load fails with a validation error that names `low`

### Requirement: The run report names the effort pass
The run report of the job SHALL name the effort pass that the run uses. When the pass is not the first value of the set, the report SHALL name it as the fallback pass.

#### Scenario: A run takes a medium-effort item
- **WHEN** the plan selects a medium-effort item because no low-effort item is selectable
- **THEN** the rendered plan states the effort pass `medium` and states that it is the fallback pass
