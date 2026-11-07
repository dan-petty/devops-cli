## ADDED Requirements

### Requirement: The plan reader reads the dependencies of a plan
`read_change` SHALL fill `StageProposal.dependencies` with one entry for each bullet of the `## Dependencies` section of `proposal.md`, and MUST give an empty list when the section holds no bullet.

#### Scenario: Writer and reader round trip
- **WHEN** `render_change` writes a change whose `dependencies` list holds `#3201: the check command`, and `read_change` reads its `proposal.md`
- **THEN** `StageProposal.dependencies` holds `#3201: the check command`

#### Scenario: An empty section
- **WHEN** `render_change` writes a change whose `dependencies` list is empty, and `read_change` reads its `proposal.md`
- **THEN** `StageProposal.dependencies` is an empty list

### Requirement: The number reader takes only the issue form
`issue_dependencies` SHALL return the issue number of each `dependencies` entry that starts with `#<number>:`, and MUST skip every other entry.

#### Scenario: One issue entry and one overlap entry
- **WHEN** the dependencies hold `#3201: the check command` and `an open pull request changes src/devops_cli/roadmap/plan_check.py`
- **THEN** `issue_dependencies` returns `[3201]`

#### Scenario: An entry with no number
- **WHEN** the dependencies hold only `a metric name and its other files`
- **THEN** `issue_dependencies` returns an empty list

### Requirement: Plan-check reports an open issue dependency
`devops roadmap plan-check` SHALL report one problem with the rule `issue-dependency` for each issue dependency whose state is open, and MUST report no problem for an issue dependency whose state is not open.

#### Scenario: An open dependency
- **WHEN** the plan lists `#3224: the dependency record`, and the client answers that issue 3224 is open
- **THEN** the check reports one problem with the rule `issue-dependency` that names issue 3224

#### Scenario: A dependency that is not open
- **WHEN** the plan lists `#3224: the dependency record`, and the client answers that issue 3224 is not open
- **THEN** the check reports no problem for issue 3224

#### Scenario: An overlap entry
- **WHEN** the plan lists only the entry `an open pull request changes src/devops_cli/roadmap/plan_check.py`
- **THEN** the check reports no `issue-dependency` problem
