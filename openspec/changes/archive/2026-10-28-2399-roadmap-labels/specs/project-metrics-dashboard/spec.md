## REMOVED Requirements

### Requirement: The items gauge counts the items of the project board
**Reason**: The roadmap jobs read no project board (#2399). An Item is an issue with a `priority/*` label, and its Priority comes from that label.
**Migration**: The requirement "The items gauge counts the Items of the repository" holds the rule.

## ADDED Requirements

### Requirement: The items gauge counts the Items of the repository
`devops_cli_project_items` SHALL count the Items of the repository, open and closed, with the labels `milestone`, `state`, `type` and `priority`. The `milestone` label SHALL be empty for an Item in no milestone. The `type` label SHALL be the `type/*` label of the issue without its prefix, empty when the issue has none, and the `priority` label SHALL be the Item's Priority.

#### Scenario: An open Item in no milestone
- **WHEN** the repository holds two open issues with `type/bug` and `priority/p1-high` and no milestone
- **THEN** the report has one item count with `milestone` empty, `state` `open`, `type` `bug`, `priority` `P1-High` and a count of 2

#### Scenario: Open and closed Items of a milestone
- **WHEN** the repository holds one open Item and one closed Item in the milestone `2026-11-01`
- **THEN** the report has one count for each state, and both name the milestone `2026-11-01`

#### Scenario: A pull request or an issue that is not an Item
- **WHEN** the repository has a pull request with `priority/p1-high`, and an issue with no `priority/*` label
- **THEN** the report counts neither

#### Scenario: The issues cannot be read
- **WHEN** the read of the issues fails
- **THEN** the collection of the report raises the failure and returns no report
