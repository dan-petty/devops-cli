## ADDED Requirements

### Requirement: The step ends at its time budget
The setting `roadmap.fix_plan.time_budget_seconds` SHALL start with each call of the step. The step SHALL start no plan run and no review run once the budget is spent. Such an attempt SHALL end with the result `timeout`, SHALL push nothing, SHALL keep the label `plan/needs-fix` and SHALL keep its attempt marks.

#### Scenario: The budget ends during the review of the head
- **WHEN** the budget is 600 seconds and the review of the head ends at 600 seconds with one open finding
- **THEN** the planner gets no request, the head of the branch does not change, the pull request keeps `plan/needs-fix`, and `fix_plan.result` is `timeout`

### Requirement: An attempt that ends at the budget comments and logs its result
An attempt that ends `timeout` SHALL post one comment with the marker `<!-- devops roadmap fix-plan -->` on the issue. The comment SHALL name the budget, the step in which it ended and the counts of the attempt, and SHALL list the open findings that keep the label. The result line SHALL hold `result=timeout`, `success=false`, `class=timeout` and the step.

#### Scenario: The comment and the result line of a timeout
- **WHEN** the budget of 600 seconds ends after the review of the head found one open finding
- **THEN** the comment names 600 seconds and lists the open finding, and the result line holds `result=timeout`, `class=timeout`, `step=plan` and `before=1` and no `after`

### Requirement: The default budget ends before the deadline of a Job
The default of `roadmap.fix_plan.time_budget_seconds` SHALL be 3600. The default plus a margin of 1200 seconds, for one more model run, the push and the comment, SHALL be less than the deadline of each CronJob template of `devops k8s run-job`.

#### Scenario: The default against the Job templates
- **WHEN** a test reads `activeDeadlineSeconds` of `k8s/devops/cronjob.yaml` and `k8s/devops/cronjob-runner.yaml`
- **THEN** the default budget plus 1200 seconds is less than each

### Requirement: Each review of an attempt logs one progress line
Each review of an attempt SHALL log one line `fix-plan progress:` with the repository, the item, the round (0 for the review of the head, then 1 more for each review), the open findings of the review, the tokens and the seconds of the attempt so far, the budget and the version. With `--confirm`, `devops roadmap step fix-plan` SHALL write these lines, the other round lines and the result line to stderr while it runs.

#### Scenario: Two reviews
- **WHEN** an attempt reviews the head with one open finding and the revision with none
- **THEN** the log holds two progress lines with `round=0 open=1` and `round=1 open=0`, each with `tokens`, `seconds` and `budget`

#### Scenario: The log of a Job
- **WHEN** a person runs `devops roadmap step fix-plan --confirm --item <n>` and the attempt ends `dismissed`
- **THEN** stderr holds one `fix-plan progress:` line and one `roadmap job result: job=fix_plan` line
