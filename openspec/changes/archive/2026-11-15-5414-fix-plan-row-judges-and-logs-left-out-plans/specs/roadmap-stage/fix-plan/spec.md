## MODIFIED Requirements

### Requirement: The step selects one plan pull request that holds the label plan/needs-fix
The step `fix-plan` SHALL select at most one repository item: an open item with Status Ready whose record holds `stage.pr`, without `implement.job` or claims. Its pull request SHALL be an open draft with `plan/needs-fix`. Attempts and revisions SHALL be under bounds, with no attempt in 6 hours. Priority SHALL order items. A candidate with a branch stop SHALL log a warning and let selection continue. In mode `plan`, the step SHALL judge all candidates and log the selection and reasons.

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
- **WHEN** the branch of a candidate pull request holds a commit by an author other than the clone identity
- **THEN** the step leaves that candidate out with a warning and continues selection to the next candidate

#### Scenario: A branch stop selects the next candidate in the same round
- **WHEN** the first candidate has a commit by another author on its branch and a second candidate passes the rules
- **THEN** the step selects the second candidate

#### Scenario: Mode plan judges each candidate
- **WHEN** the step runs in mode plan with multiple plan pull requests
- **THEN** the step logs the mode line naming the would-be selection, and logs each left-out plan with its reason
