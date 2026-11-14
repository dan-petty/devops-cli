## ADDED Requirements

### Requirement: A plan request replaces a group with a smaller one
A plan request of kind `group` SHALL replace the named group with its new text when the new text holds one group of the same number, fewer tasks than the group, and no path that the group does not name. The applied plan SHALL hold the new text and the amendment bullet.

#### Scenario: A smaller replacement of group 2
- **WHEN** a plan request of kind `group` names group 2 and gives one group numbered 2 with one task, where group 2 has two tasks and names the same paths
- **THEN** `judge` returns `Applied`, `tasks.md` holds the one task under group 2, and its `## Amendments` section holds the bullet of the request

### Requirement: A group replacement that breaks a bound is refused
`judge` SHALL refuse a plan request of kind `group` with a reason when the new text holds as many tasks as the group or more, holds no group of the same number, or names a path that the group does not name.

#### Scenario: A replacement with no fewer tasks
- **WHEN** a plan request of kind `group` gives a group with the same number of tasks as the group it replaces
- **THEN** `judge` returns `Refused` with a reason, and `tasks.md` does not change

#### Scenario: A replacement that changes the number
- **WHEN** a plan request of kind `group` names group 2 and gives a group numbered 3
- **THEN** `judge` returns `Refused` with a reason

#### Scenario: A replacement that names a new path
- **WHEN** a plan request of kind `group` names a path that its group does not name
- **THEN** `judge` returns `Refused` with a reason that names the path
