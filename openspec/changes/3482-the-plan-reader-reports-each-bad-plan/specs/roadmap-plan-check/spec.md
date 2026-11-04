## ADDED Requirements

### Requirement: The plan reader raises only a read error
The plan reader SHALL raise `PlanReadError` for each change folder that it cannot read, and SHALL NOT let a pydantic `ValidationError` leave `read_change`. The error of a task group SHALL name `tasks.md` and the title of the group.

#### Scenario: Each change folder of the tree
- **WHEN** a test runs `read_change` over each change folder of the tree
- **THEN** no error other than `PlanReadError` appears.

#### Scenario: A group that changes no file
- **WHEN** a group of `tasks.md` names no file in a code span after `Changes:`
- **THEN** `read_change` raises `PlanReadError` for `tasks.md` that names the group.

#### Scenario: A group that changes a path of the change folder
- **WHEN** a group changes `proposal.md` of the change folder
- **THEN** `read_change` raises `PlanReadError` for `tasks.md` that names the group.

### Requirement: The reader judges every verification command
The plan reader SHALL judge each code span of each `Verification:` line of a group with `verification_problem`, and SHALL raise `PlanReadError` for `tasks.md` that names each span that the implement step cannot run.

#### Scenario: A later task names a refused command
- **WHEN** the second task of a group names the verification `helm template loki`
- **THEN** `read_change` raises `PlanReadError` that names the command and the reason.

### Requirement: Plan-check reports a plan that the model refuses
The command SHALL report a `read` problem for a plan whose task group the model refuses, and SHALL exit with code 1 and print no traceback.

#### Scenario: A group with no changed file or a changed file in the change folder
- **WHEN** plan-check reads a plan with such a group
- **THEN** the output holds one problem with the path `tasks.md` and the rule `read`, the exit code is 1, and the output holds no traceback.
