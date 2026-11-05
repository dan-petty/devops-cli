## ADDED Requirements

### Requirement: Plan-check measures each task group
`devops roadmap plan-check` SHALL measure each task group of the plan with `measure_groups`, the function of the stage job, on the tracked files of the pull request head. It SHALL read the budget from the setting `roadmap.stage.step_tokens`. A created file SHALL count one estimated line, because the plan holds no estimate. The command SHALL report a `group-over-budget` problem for each group above the budget, and a `group-no-files` problem for each group that packs no file.

#### Scenario: The figure equals the figure of the stage job
- **WHEN** a plan has a group that creates no file, and the budget is one token below the figure that `measure_groups` gives the stage job for that group
- **THEN** the `group-over-budget` problem holds that figure.

#### Scenario: A group over the budget is reported
- **WHEN** a group measures more tokens than `roadmap.stage.step_tokens`
- **THEN** the output holds a `group-over-budget` problem that names the group, its figure and the budget, and the exit code is 1.

#### Scenario: A group under the budget is not reported
- **WHEN** each group measures no more tokens than `roadmap.stage.step_tokens`
- **THEN** the output holds no `group-over-budget` problem.

#### Scenario: A group that packs no file is reported
- **WHEN** no code span of the tasks of a group names a file of the pull request head
- **THEN** the output holds a `group-no-files` problem that names the group, and the exit code is 1.
