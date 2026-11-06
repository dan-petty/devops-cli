## ADDED Requirements

### Requirement: Plan-check measures each task group
`devops roadmap plan-check` SHALL measure each task group of the plan with `measure_groups`, the function of the stage job, on the tracked files of the pull request head, with the body of the issue as the store reads it for the stage job, with no record block. The plan holds no estimate of the lines of a created file, so the measure SHALL count one estimated line for each created file.

#### Scenario: The figure equals the figure of the stage job
- **WHEN** a plan has a group that estimates one line for each file that it creates, and the budget is one token below the figure that `measure_groups` gives the stage job for that group
- **THEN** the `group-over-budget` problem holds that figure.

#### Scenario: The record block of the issue is not in the figure
- **WHEN** the body of the issue ends with the record block of the jobs, and the budget is one token below the figure that the stage job gives for the same text with no block
- **THEN** the `group-over-budget` problem holds the figure of the stage job, and a budget equal to that figure gives no problem.

### Requirement: Plan-check reports a group over the budget
The command SHALL read the budget from the setting `roadmap.stage.step_tokens`, and SHALL report a `group-over-budget` problem for each group whose figure is above it.

#### Scenario: A group over the budget is reported
- **WHEN** a group measures more tokens than `roadmap.stage.step_tokens`
- **THEN** the output holds a `group-over-budget` problem that names the group, its figure and the budget, and the exit code is 1.

#### Scenario: A group under the budget is not reported
- **WHEN** each group measures no more tokens than `roadmap.stage.step_tokens`
- **THEN** the output holds no `group-over-budget` problem.

### Requirement: Plan-check reports a group that packs no file
The command SHALL report a `group-no-files` problem for each group that changes a file that exists and packs no file. A group that only creates files SHALL be no problem.

#### Scenario: A group that packs no file is reported
- **WHEN** a group changes a file of the pull request head and no code span of its tasks names a file of the head
- **THEN** the output holds a `group-no-files` problem that names the group, and the exit code is 1.

#### Scenario: A group that only creates files is not reported
- **WHEN** each path that a group changes is a path that it creates
- **THEN** the output holds no `group-no-files` problem for that group.
