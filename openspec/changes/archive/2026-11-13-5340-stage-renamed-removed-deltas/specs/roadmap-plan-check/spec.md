## ADDED Requirements

### Requirement: The plan reader reads the RENAMED and REMOVED deltas
The plan reader SHALL read each FROM and TO pair of `## RENAMED Requirements` into `renamed`, and each requirement header of `## REMOVED Requirements` with its `**Reason**:` line and its optional `**Migration**:` line into `removed`. A FROM line with no TO line, a TO line with no FROM line, and a removal with no reason SHALL be a `PlanReadError` that names the spec file.

#### Scenario: A real RENAMED delta reads back
- **WHEN** the reader reads the spec delta of the archived change of #5150, which renames one requirement and modifies it under the new name
- **THEN** the spec holds the rename with both names, and the modified requirement under the new name

#### Scenario: A real REMOVED delta reads back
- **WHEN** the reader reads the spec delta of the archived change of #4798, which removes two requirements, each with a reason and a migration
- **THEN** the spec holds both removals with their names, reasons and migrations

#### Scenario: A FROM line with no TO line
- **WHEN** a RENAMED section holds a FROM line and no TO line after it
- **THEN** the reader raises `PlanReadError` that names the spec file

#### Scenario: A removal with no reason
- **WHEN** a REMOVED section holds a requirement header with no `**Reason**:` line
- **THEN** the reader raises `PlanReadError` that names the spec file

### Requirement: Plan-check compares a renamed requirement under its old name
The moved-spec check SHALL compare a MODIFIED requirement whose name is the `to_name` of a `renamed` entry with the base text under the `from_name`, at the plan commit and at the pull request base.

#### Scenario: A renamed and modified requirement with an unchanged base
- **WHEN** a plan renames a base requirement, modifies it under the new name, and the base spec does not change after the plan commit
- **THEN** plan-check reports no `spec-moved` problem

#### Scenario: The base text under the old name changed
- **WHEN** a plan renames and modifies a base requirement, and the base text under the old name changes after the plan commit
- **THEN** plan-check reports a `spec-moved` problem that names the old name
