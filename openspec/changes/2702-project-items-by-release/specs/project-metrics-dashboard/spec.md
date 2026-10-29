# Spec Delta

## MODIFIED Requirements

### Requirement: The panels that read the items gauge describe what it counts
The panels "Items by Release" and "Active Items by State" SHALL group `devops_cli_project_items` only by labels that the gauge sends. The description of each panel and of the instrument SHALL name the labels, and the panel "Items by Release" SHALL show an item in no release as `unreleased`.

#### Scenario: A panel groups by a label that the gauge does not send
- **WHEN** a query of the project dashboard groups `devops_cli_project_items` by a label that is not `release`, `state`, `type` or `priority`
- **THEN** the dashboard invariant of `tests/test_telemetry_instruments.py` fails and names the query and the label

#### Scenario: The items of each release
- **WHEN** the panel "Items by Release" reads the items gauge
- **THEN** its query is `label_replace(sum by (release, state) (last_over_time(devops_cli_project_items[$__range])), "release", "unreleased", "release", "^$")`

#### Scenario: The items of each state
- **WHEN** the panel "Active Items by State" reads the items gauge
- **THEN** its query is `sum by (state) (last_over_time(devops_cli_project_items[$__range]))`

### Requirement: The items gauge counts the Items of the repository
`devops_cli_project_items` SHALL count the Items of the repository, open and closed, with the labels `release`, `state`, `type` and `priority`. The `release` label SHALL be the first `v*` tag whose commits close the Item with a closing keyword, and empty for an open Item or a closed Item that no release holds. The `type` label SHALL be the `type/*` label of the issue without its prefix, empty when the issue has none, and the `priority` label SHALL be the Item's Priority.

#### Scenario: An open Item
- **WHEN** the repository holds two open issues with `type/bug` and `priority/p1-high`
- **THEN** the report has one item count with `release` empty, `state` `open`, `type` `bug`, `priority` `P1-High` and a count of 2

#### Scenario: A closed Item that a release closed
- **WHEN** a commit in the range of the tag `v0.2.24` has the footer `Closes #2`, and issue 2 is a closed Item
- **THEN** the report counts issue 2 with `release` `v0.2.24` and `state` `closed`

#### Scenario: An issue closed again in a later release
- **WHEN** a commit of `v0.1.0` has `Closes #4`, and a commit of `v0.2.0` has `fixes #4`
- **THEN** the release of issue 4 is `v0.1.0`

#### Scenario: A pull request or an issue that is not an Item
- **WHEN** the repository has a pull request with `priority/p1-high`, and an issue with no `priority/*` label
- **THEN** the report counts neither

#### Scenario: The issues cannot be read
- **WHEN** the read of the issues fails
- **THEN** the collection of the report raises the failure and returns no report
