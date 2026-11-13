## ADDED Requirements

### Requirement: The step records the release of each attempt
For a plan that it reads, the step SHALL write `fix_plan.version`, the release of devops-cli that runs the attempt, with the attempt marks before its first model call.

#### Scenario: The release of the attempt
- **WHEN** an attempt ends
- **THEN** the record holds `fix_plan.version` with the release that ran it

### Requirement: A named run with skip_wait skips the wait
A run with `skip_wait` SHALL leave out the rule of the 6 hours and keep the other rules of the selection. It SHALL also take a head with 2 or more counted attempts when `fix_plan.version` gives an older release than the current release, or no release, and SHALL log the reason. `--skip-wait` of the command SHALL give `skip_wait`, and the command SHALL refuse it without `--confirm` or without one of `--item` and `--pull`. The row of the Service SHALL never pass `skip_wait`.

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

### Requirement: The command ends an attempt at the first SIGTERM
While `devops roadmap step fix-plan` runs, the first SIGTERM SHALL end the attempt as a kill, and the step SHALL write the marks of its class. The command SHALL exit 75 after an evicted attempt and 143 after a deadline kill.

#### Scenario: SIGTERM during the attempt
- **WHEN** SIGTERM reaches the command during a model run of the attempt, before the time budget is spent
- **THEN** the record holds the result `evicted`, and the command exits 75

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
