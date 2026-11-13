## MODIFIED Requirements

### Requirement: The step selects one plan pull request that holds the label plan/needs-fix
The step `fix-plan` SHALL select, for one call, at most one item of the repository: an open item with the Status Ready whose record holds `stage.pr`, with no `implement.job` and no claim of an agent or a person. Its pull request SHALL be an open draft that holds `plan/needs-fix`. The item SHALL have fewer than 2 attempts on the head of the pull request, no attempt in the last 6 hours, and fewer than 3 revisions on the pull request. The highest priority SHALL go first. A run with `skip_wait` SHALL leave out the rule of the 6 hours and keep the other rules, and SHALL take a head with 2 or more counted attempts when the record gives a release older than the current release, or no release, for those attempts. Such a run SHALL log the reason. The row of the Service SHALL never pass `skip_wait`.

#### Scenario: A plan pull request with the label
- **WHEN** a Staged item has an open draft plan pull request that holds `plan/needs-fix` and no fix-plan mark
- **THEN** the step selects that pull request

#### Scenario: The bounds leave an item out
- **WHEN** the item has 2 attempts on the head, or an attempt less than 6 hours old, or 3 revisions on the pull request, or a claim, or a runner Job, or a Status other than Ready
- **THEN** the step selects no pull request and makes no model call

#### Scenario: The pull request is not an open draft with the label
- **WHEN** the recorded pull request has no `plan/needs-fix` label or is not an open draft
- **THEN** the step selects no pull request and makes no model call

#### Scenario: A person pushed to the branch
- **WHEN** the branch of the selected pull request holds a commit by an author other than the clone identity
- **THEN** the step makes no model call and writes nothing

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

### Requirement: The step records each attempt before the model call
The step SHALL read the plan of the head before it writes a mark. For a plan that it reads, it SHALL write `fix_plan.key` (`<pull>:<head>`), `fix_plan.attempts`, `fix_plan.at` and `fix_plan.version`, the release of devops-cli that runs the attempt, before its first model call, and `fix_plan.result` and `fix_plan.revisions` after the attempt. It SHALL post one comment with the marker `<!-- devops roadmap fix-plan -->` on the issue for each attempt that ends `revised`, `cleared`, `regated`, `dismissed` or `stopped`. No new attempt SHALL start once the Service stops.

#### Scenario: The attempt marks
- **WHEN** an attempt pushes a revision
- **THEN** the record holds `fix_plan.key` with the new head and `fix_plan.attempts` 0, `fix_plan.revisions` 1 and `fix_plan.result` `revised` or `cleared`

#### Scenario: The release of the attempt
- **WHEN** an attempt ends
- **THEN** the record holds `fix_plan.version` with the release that ran it

#### Scenario: The Service stops
- **WHEN** the Service stops before the attempt starts
- **THEN** the step makes no model call and writes no mark

### Requirement: The command devops roadmap step fix-plan
`devops roadmap step fix-plan` SHALL print the plan pull request that the step selects, and SHALL make no model call and no write without `--confirm`. With `--confirm` it SHALL run the attempt. `--item` SHALL name the one item to judge. `--skip-wait` SHALL run the step with `skip_wait`, and the command SHALL refuse it without `--confirm` or without one of `--item` and `--pull`. While the command runs, the first SIGTERM SHALL end the attempt as a kill, and the command SHALL exit 75 after an evicted attempt and 143 after a deadline kill. `--dry-run` SHALL make no request and SHALL list the requests and the writes of a run, with the read of the plan of the head before the attempt marks, the marks of a plan that the reader refuses, the marks of a killed attempt, and the conditions of the push, of the label and of the comment.

#### Scenario: The dry run
- **WHEN** a person runs `devops roadmap step fix-plan --dry-run`
- **THEN** the command sends no request to GitHub or a model, starts no git command, and lists the reads and the writes, with the read of the head before the attempt marks

#### Scenario: The skip of the wait without a name or a confirm
- **WHEN** a person runs `devops roadmap step fix-plan --skip-wait` without `--confirm`, or without `--item` and `--pull`
- **THEN** the command exits 1 and sends no request

#### Scenario: SIGTERM during the attempt
- **WHEN** SIGTERM reaches the command during a model run of the attempt, before the time budget is spent
- **THEN** the record holds the result `evicted`, and the command exits 75

## ADDED Requirements

### Requirement: A kill after the time budget is a deadline kill that counts
An attempt that SIGTERM ends after its attempt marks and after the time budget `roadmap.fix_plan.time_budget_seconds` is spent SHALL be a kill of the class `deadline`. The attempt SHALL count, the record SHALL get the result `timeout`, and the step SHALL log one result line with `result=timeout`, the class `timeout` and `kill=deadline`. The step SHALL post no comment and push nothing.

#### Scenario: A kill after the budget
- **WHEN** SIGTERM ends an attempt after the budget is spent
- **THEN** the record holds `fix_plan.attempts` 1 and `fix_plan.result` `timeout`, and the result line holds `result=timeout`, `class=timeout` and `kill=deadline`

### Requirement: An evicted attempt does not count for 3 evicted attempts on a head
SIGTERM before the time budget is spent, or a stop of the Service, SHALL end an attempt as `evicted`. While the head has fewer than 3 in `fix_plan.evicted`, the record SHALL keep the count, the time and the release of the attempt before it, add 1 to `fix_plan.evicted` and get the result `evicted`. A later evicted attempt SHALL count. An evicted attempt SHALL write no result line, post no comment and push nothing.

#### Scenario: An eviction before the budget
- **WHEN** SIGTERM ends an attempt on a head with 1 counted attempt before the budget is spent
- **THEN** the record holds `fix_plan.attempts` 1, `fix_plan.evicted` 1 and `fix_plan.result` `evicted`, and the log holds no result line

#### Scenario: A stop of the Service during the attempt
- **WHEN** the Service stops while the attempt runs, and the planner stops at its next safe point
- **THEN** the attempt is evicted, and the stop of the Service goes on

#### Scenario: A unit that a kill always ends
- **WHEN** each attempt on one head ends with an eviction
- **THEN** the step selects the head 5 times and then leaves it out with the attempt cap
