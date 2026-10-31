# Spec Delta

## MODIFIED Requirements

### Requirement: The label filter names the items to stage
`devops roadmap stage` SHALL take the open items whose labels match the `--filter family=value` options. The families are `status`, `priority`, `type`, `value` and `effort`. Values of one family SHALL be alternatives, and the families SHALL all apply. With no `--filter`, the filter SHALL be `status=ready`. A family that is not in the list SHALL be refused.

#### Scenario: The default filter
- **WHEN** the roadmap holds a Ready P1 bug, a Ready P3 feature, a Ready P2 docs item and a New P1 bug, and the command runs with no filter
- **THEN** the plan holds the three Ready items, and not the New one

#### Scenario: Values of one family
- **WHEN** the command runs with `--filter priority=p2-medium --filter priority=p3-low --filter status=ready`
- **THEN** the plan holds the Ready items of priority P2 and P3, and no item of another priority

#### Scenario: An unknown family
- **WHEN** the command runs with `--filter color=red`
- **THEN** the command exits 1, names the families it accepts, and makes no request

### Requirement: The settings name the filter, the limit and the step budget
The settings `roadmap.stage.filter`, `roadmap.stage.limit` and `roadmap.stage.step_tokens` SHALL set what the stage job takes. Each SHALL have the variable `DEVOPS_CLI_ROADMAP_STAGE_FILTER`, `DEVOPS_CLI_ROADMAP_STAGE_LIMIT` or `DEVOPS_CLI_ROADMAP_STAGE_STEP_TOKENS`. The defaults SHALL be the filter `status=ready`, the limit 3 and the step budget 40000. The example ConfigMap of the Service SHALL hold the default filter.

#### Scenario: The defaults
- **WHEN** no config file and no variable sets a `roadmap.stage` setting
- **THEN** the filter, the limit and the step budget are the defaults above

#### Scenario: A config file and a variable
- **WHEN** the config file sets `roadmap.stage.limit` to 1 and the variable `DEVOPS_CLI_ROADMAP_STAGE_FILTER` holds `status=ready,type=feature`
- **THEN** the limit is 1 and the filter is `status=ready` and `type=feature`

#### Scenario: A round uses the settings
- **WHEN** the filter is `type=feature` and the limit is 1, and the roadmap holds two Ready features and a Ready bug
- **THEN** a round of the `stage` row plans the first feature only

#### Scenario: The example ConfigMap
- **WHEN** the example ConfigMap of the Service is rendered and loaded as settings
- **THEN** its stage filter equals the default filter

## ADDED Requirements

### Requirement: The job takes the highest priority first
A run SHALL take the items that the filter names with the highest priority first, and the lowest issue number first among equal priorities. An item with no priority SHALL go last. The type of the branch of a staged item SHALL be the Conventional Commit type of its title.

#### Scenario: Priority order
- **WHEN** the default filter names a Ready P3 chore, a Ready P2 feature and a Ready P0 docs item, and the limit is 2
- **THEN** the plan stages the P0 docs item and the P2 feature

#### Scenario: The type of the branch
- **WHEN** the plan stages a feature titled `feat(cli): add a flag` and a docs item titled `docs(k8s): fix a path`
- **THEN** the branches start with `feat/` and `docs/`
