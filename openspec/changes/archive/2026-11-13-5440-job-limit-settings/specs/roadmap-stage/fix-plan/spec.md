## MODIFIED Requirements

### Requirement: The step selects one plan pull request that holds the label plan/needs-fix
The step `fix-plan` SHALL select, for one call, at most one item of the repository: an open item with the Status Ready whose record holds `stage.pr`, with no `implement.job` and no claim of an agent or a person. Its pull request SHALL be an open draft that holds `plan/needs-fix`. The item SHALL have fewer attempts on the head than `roadmap.fix_plan.head_attempts`, no attempt in the last 6 hours, and fewer revisions than `roadmap.fix_plan.revisions`. The highest priority SHALL go first.

#### Scenario: A plan pull request with the label
- **WHEN** a Staged item has an open draft plan pull request that holds `plan/needs-fix` and no fix-plan mark
- **THEN** the step selects that pull request

#### Scenario: The bounds leave an item out
- **WHEN** the item has as many attempts on the head as `roadmap.fix_plan.head_attempts`, or an attempt less than 6 hours old, or as many revisions on the pull request as `roadmap.fix_plan.revisions`, or a claim, or a runner Job, or a Status other than Ready
- **THEN** the step selects no pull request and makes no model call

#### Scenario: Doubled settings select a plan at the old bounds
- **WHEN** `roadmap.fix_plan.head_attempts` is 4 and `roadmap.fix_plan.revisions` is 6 in the settings of the call, with no restart, and the item has 2 attempts on the head or 3 revisions on the pull request (the defaults)
- **THEN** the step selects that pull request

#### Scenario: A bound above its ceiling
- **WHEN** `roadmap.fix_plan.head_attempts` is 9, 4 times its default and one more
- **THEN** the settings load fails with an error that names `roadmap.fix_plan.head_attempts`

#### Scenario: The pull request is not an open draft with the label
- **WHEN** the recorded pull request has no `plan/needs-fix` label or is not an open draft
- **THEN** the step selects no pull request and makes no model call

#### Scenario: A person pushed to the branch
- **WHEN** the branch of the selected pull request holds a commit by an author other than the clone identity
- **THEN** the step makes no model call and writes nothing

### Requirement: A named run with skip_wait skips the wait
A run with `skip_wait` SHALL leave out the rule of the 6 hours and keep the other rules of the selection. It SHALL also take a head at or over the cap of `roadmap.fix_plan.head_attempts` when `fix_plan.version` gives an older release than the current one, or no release, and SHALL log the reason. `--skip-wait` of the command SHALL give `skip_wait`, and the command SHALL refuse it without `--confirm` or without one of `--item` and `--pull`. The row of the Service SHALL never pass `skip_wait`.

#### Scenario: A named run skips the wait
- **WHEN** a run with `skip_wait` names a plan pull request whose record holds `fix_plan.at` 1 hour ago and 1 attempt on the head
- **THEN** the step selects that pull request

#### Scenario: The skip of the wait keeps the cap of the head
- **WHEN** a run with `skip_wait` names a plan pull request with 2 attempts on the head from the current release
- **THEN** the step selects no pull request and makes no model call

#### Scenario: A head whose attempts ran on an older release
- **WHEN** a run with `skip_wait` names a plan pull request with 2 attempts on the head, and `fix_plan.version` is an older release or is not set
- **THEN** the step selects that pull request and logs that the head gets one more attempt

#### Scenario: The row keeps the wait
- **WHEN** the row `fix_plan` runs on an item whose record holds `fix_plan.at` 1 hour ago
- **THEN** the row selects no pull request and makes no model call

#### Scenario: The skip of the wait without a name or a confirm
- **WHEN** a person runs `devops roadmap step fix-plan --skip-wait` without `--confirm`, or without `--item` and `--pull`
- **THEN** the command exits 1 and sends no request
