## MODIFIED Requirements

### Requirement: The step selects one plan pull request that holds the label plan/needs-fix
The step `fix-plan` SHALL select, for one call, at most one item of the repository: an open item with the Status Ready whose record holds `stage.pr`, with no `implement.job` and no claim of an agent or a person. Its pull request SHALL be an open draft that holds `plan/needs-fix`. The item SHALL have fewer attempts on the head of the pull request than `roadmap.fix_plan.head_attempts` (default 2), no attempt in the last 6 hours, and fewer revisions on the pull request than `roadmap.fix_plan.revisions` (default 3). The step SHALL read both settings at each selection, and the settings load SHALL refuse a value of either setting above 4 times its default with an error that names the setting. The highest priority SHALL go first.

#### Scenario: A plan pull request with the label
- **WHEN** a Staged item has an open draft plan pull request that holds `plan/needs-fix` and no fix-plan mark
- **THEN** the step selects that pull request

#### Scenario: The bounds leave an item out
- **WHEN** the item has as many attempts on the head as `roadmap.fix_plan.head_attempts`, or an attempt less than 6 hours old, or as many revisions on the pull request as `roadmap.fix_plan.revisions`, or a claim, or a runner Job, or a Status other than Ready
- **THEN** the step selects no pull request and makes no model call

#### Scenario: Doubled settings select a plan at the old bounds
- **WHEN** `roadmap.fix_plan.head_attempts` is 4 and `roadmap.fix_plan.revisions` is 6, and the item has 2 attempts on the head or 3 revisions on the pull request
- **THEN** the step selects that pull request

#### Scenario: The pull request is not an open draft with the label
- **WHEN** the recorded pull request has no `plan/needs-fix` label or is not an open draft
- **THEN** the step selects no pull request and makes no model call

#### Scenario: A person pushed to the branch
- **WHEN** the branch of the selected pull request holds a commit by an author other than the clone identity
- **THEN** the step makes no model call and writes nothing
