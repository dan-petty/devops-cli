## ADDED Requirements

### Requirement: A task of a group holds more than one word
`form_problems` SHALL give a problem for each `test`, `implementation` or `documentation` text of a group that holds one word or less, with a code span counted as one word. The problem SHALL name the group by its number and its title, and the part of the text.

#### Scenario: A bare filename as the first task
- **WHEN** the `test` of a behavior group is `src/devops_cli/roadmap/stage_form.py`
- **THEN** `form_problems` gives one problem, and it names the group and the part `test`

#### Scenario: A single word as the work
- **WHEN** the `implementation` of a group is `Refactor`
- **THEN** `form_problems` gives one problem that names the part `implementation`

#### Scenario: A code span alone
- **WHEN** the `test` of a group is a path in a code span
- **THEN** `form_problems` gives one problem

#### Scenario: A task with a verb and an object
- **WHEN** the `test` of a group is `Add a test in tests/roadmap/test_roadmap_stage_form.py for a bare filename task`
- **THEN** `form_problems` gives no problem for the task
