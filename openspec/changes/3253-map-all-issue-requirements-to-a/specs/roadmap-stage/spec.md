## ADDED Requirements

### Requirement: The stage context lists each requirement line of the issue
The stage job SHALL list each requirement line of the issue body in the `requirements` list of the request, each with an ID of the form `REQ-<number>`.

#### Scenario: A named caller is listed
- **WHEN** The issue body holds a bullet under a refined section that names `devops pr ready`.
- **THEN** The `requirements` list holds one entry with the ID `REQ-001`, the kind `command` and the text `devops pr ready`.

#### Scenario: The acceptance criteria list is left out
- **WHEN** The issue body holds a list under the heading `Acceptance criteria`.
- **THEN** The `requirements` list holds no entry for an item of that list.

### Requirement: The plan maps each requirement ID
The plan check SHALL refuse a reply whose `coverage` list holds no entry for an ID of the `requirements` list, and the problem SHALL quote the text of the requirement.

#### Scenario: An unmapped caller is refused with its name
- **WHEN** The issue names `devops pr ready` and the reply holds no coverage entry for its ID.
- **THEN** The `coverage` gate returns one problem that quotes `devops pr ready`.

#### Scenario: Full coverage passes
- **WHEN** The reply holds one coverage entry for each ID, each with a group number or `pending-person` and a reason.
- **THEN** The `coverage` gate returns no problem.

### Requirement: The plan check refuses a vague scenario WHEN clause
The plan check SHALL refuse a scenario whose `when` clause holds a phrase of a person's intent and no backticked literal.

#### Scenario: A vague WHEN is refused
- **WHEN** A spec delta scenario has the `when` clause `its author says so`.
- **THEN** The `coverage` gate returns one problem that quotes `its author says so`.

#### Scenario: A WHEN with a literal passes
- **WHEN** A spec delta scenario has the `when` clause that names the literal `REQ-001`.
- **THEN** The `coverage` gate returns no problem for the scenario.

### Requirement: The plan reader reads the coverage of the change folder
The plan reader SHALL read each coverage line of the `## Criteria` section of `tasks.md` into the `coverage` list of the plan.

#### Scenario: A coverage line is read back
- **WHEN** The `## Criteria` section holds the line `REQ-001: group 2`.
- **THEN** The plan holds one coverage entry with the ID `REQ-001` and the group 2.

#### Scenario: A split renumbers the coverage
- **WHEN** The split reply gives the group 2 for `REQ-001`.
- **THEN** `tasks.md` names the group 2 for `REQ-001`.
