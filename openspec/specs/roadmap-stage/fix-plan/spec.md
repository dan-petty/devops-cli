# roadmap-stage/fix-plan Specification

## Purpose
How the step `fix-plan` repairs an open plan pull request that holds `plan/needs-fix`: its selection and bounds, the repair with the stage planner and the verification pass, the writes, the marks, the Service row and the command.

## Requirements

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

### Requirement: The step repairs the plan with the stage planner
The step SHALL read the plan of the head of the pull request with `read_change` and give it to the stage planner at the latest default branch. The planner SHALL get the plan as `previous` and each open finding of the review of the head and of the last plan comment as `problem`, and the revision SHALL pass the gates and the verification repair rounds of the stage job. The first review of the revision SHALL be a later review of the open findings of the review of the head.

#### Scenario: The open findings of the stage comment
- **WHEN** the stage comment of the item lists an open finding for the pull request, and the review of the head plan has another open finding
- **THEN** the first planner request holds the head plan as `previous` and both findings in `problem`

#### Scenario: The review of the revision gets the findings of the head
- **WHEN** the review of the head plan has one open finding, and the planner answers a revision that changes the `why` of the plan
- **THEN** the request of the review of the revision holds that finding in `earlier` and the new `why` in `answer`

### Requirement: The review of the head counts the open findings before the repair
In each attempt the verification pass SHALL review the plan that passed the checks at the latest default branch, with no screen of `stage.verify_screen`, and the step SHALL compare the last review of the revision with the open findings of that review. The step SHALL give the planner the open findings of the last trusted comment of the stage job or of the step that names the pull request, and SHALL NOT count them, because an earlier review wrote that comment.

#### Scenario: No comment lists an open finding
- **WHEN** no trusted comment of the item lists an open finding for the pull request, and the review of the head plan has one
- **THEN** the next planner request holds the head plan as `previous` and the finding of the review in `problem`

#### Scenario: A comment of an untrusted author
- **WHEN** the only comment that lists an open finding has an author with no write access, and the review of the head plan has an open finding
- **THEN** the next planner request holds the finding of the review in `problem` and no finding of that comment

#### Scenario: The comment lists fewer open findings than the review of the head
- **WHEN** the stage comment lists 1 open finding, the review of the head plan has 2 and the last review of the revision has 1
- **THEN** the step pushes the revision with the result `revised`, and its result line holds `comment=1`, `before=2` and `after=1`

#### Scenario: The review of the head finds no open finding that the comment lists
- **WHEN** the stage comment lists an open finding and the review of the head plan has none
- **THEN** the planner gets no request, the head of the branch does not change, the pull request loses `plan/needs-fix`, and the result is `dismissed`

#### Scenario: The screen does not decide the review of the head
- **WHEN** the screen of `stage.verify_screen` is in mode `on` and gives the band `continue`
- **THEN** the verification pass reviews the plan of the head, and its open findings are `before`

### Requirement: The step pushes a revision that fixes more findings of the head than it adds
When the revision of a repair is not the same plan as the plan that passed the checks, and its reviews fixed more open findings of the head than they added, the step SHALL write the change folder as one commit on the latest default branch, push it with `--force-with-lease` on the head that it read, and set the title and the body of the pull request to those of the revision. A finding of the head is fixed when the last review of the revision does not keep it open.

#### Scenario: A revision with fewer open findings
- **WHEN** the review of the head has two open findings, and the review of the revision marks one `gone` and the other `holds`
- **THEN** the branch holds one new commit whose parent is the latest default branch, the result is `revised`, and the pull request keeps `plan/needs-fix`

#### Scenario: A revision that fixes the finding of the head and opens a finding on unchanged text
- **WHEN** the review of the head has one open finding, and the review of the revision marks it `gone` and opens one finding whose quote is in text that the revision did not change
- **THEN** the new finding is advice, the step pushes the revision, the result is `cleared`, and the pull request loses `plan/needs-fix`

#### Scenario: A repair that gives the same plan
- **WHEN** the review of the head has one open finding, the planner answers the plan of the head, and the review of that plan marks the finding `gone`
- **THEN** the two plans are the same plan, because `render_change` gives the same files for both with one change name and one date, so the head of the branch does not change, the result is `unchanged`, the result line holds `success=false`, and the pull request keeps `plan/needs-fix`

### Requirement: The label goes when no open finding remains
The step SHALL remove `plan/needs-fix` for the result `cleared` (a pushed revision whose last review has no open finding), for `dismissed` (a review of the head with no open finding), and for `regated` only when the review of the gated plan has no open finding and no step failed. It SHALL keep the label for each other result.

#### Scenario: A revision with no open finding
- **WHEN** the review of the head has an open finding and the review of the revision has none
- **THEN** the branch holds the new commit, the result is `cleared`, and the pull request loses `plan/needs-fix`

#### Scenario: A head plan with no open finding
- **WHEN** the checks pass the plan of the head, the review of it has no open finding, and the last plan comment lists an open finding
- **THEN** the planner gets no request, the head of the branch does not change, the pull request loses `plan/needs-fix`, the result is `dismissed`, and the comment lists the finding of the last plan comment as dismissed

### Requirement: A revision that is not better writes only the record
When no rule of a push or of a label holds, the step SHALL write nothing to GitHub except the record of the item, with the result `unchanged`. A failure before a gated plan exists, or a failure after the checks when the plan that passed them is the plan of the head, SHALL write only the record with the result `failed`.

#### Scenario: A revision that is not better
- **WHEN** the review of the revision marks the open finding of the head `holds`
- **THEN** the head of the branch does not change, the label stays, no comment is posted, and the record holds the attempt with the result `unchanged`

#### Scenario: The returns of the checks run out before the review
- **WHEN** the checks refuse the plan of the head and each new plan until the returns run out
- **THEN** the result is `failed`, the result line holds `step=gate`, the class of the failure and no `before` and no `after`, and the head of the branch does not change

#### Scenario: A failed repair
- **WHEN** the review of the head has one open finding and the checks refuse each revision of the repair until the returns run out
- **THEN** the result is `failed`, and the result line holds `before=1`, `step=plan` and the class `plan_defect`

### Requirement: The step records each attempt before the model call
The step SHALL read the plan of the head before it writes a mark. For a plan that it reads, it SHALL write `fix_plan.key` (`<pull>:<head>`), `fix_plan.attempts` and `fix_plan.at` before its first model call, and `fix_plan.result` and `fix_plan.revisions` after the attempt. It SHALL post one comment with the marker `<!-- devops roadmap fix-plan -->` on the issue for each attempt that ends `revised`, `cleared`, `regated`, `dismissed` or `stopped`. No new attempt SHALL start once the Service stops.

#### Scenario: The attempt marks
- **WHEN** an attempt pushes a revision
- **THEN** the record holds `fix_plan.key` with the new head and `fix_plan.attempts` 0, `fix_plan.revisions` 1 and `fix_plan.result` `revised` or `cleared`

#### Scenario: The Service stops
- **WHEN** the Service stops before the attempt starts
- **THEN** the step makes no model call and writes no mark

### Requirement: Each attempt logs one result line and counts its result
Each attempt on a plan that the reader reads SHALL log one result line with the job `fix_plan`, its result, the counts of the plan runs and `comment`, the open findings of the last plan comment. It SHALL hold `before` (the review of the head) only when that review ran, and `after` (the last review of the revision) only when such a review ran. Each attempt SHALL add 1 to `devops_cli_roadmap_fix_plan_total` by `repo` and `result`. Only `revised` and `cleared` SHALL be a success.

#### Scenario: A counted attempt
- **WHEN** an attempt ends with the result `cleared`
- **THEN** the log holds one line `roadmap job result: job=fix_plan` with `result=cleared`, `success=true` and the counts `comment`, `before` and `after`, and the counter holds 1 for that result

### Requirement: The Service runs the step as the row fix_plan in its mode
The model lane SHALL hold the row `fix_plan` after `retitle`. The row SHALL need a clone and be due on a first run. The setting `roadmap.fix_plan.mode` SHALL be `off`, `plan` or `on`, with `plan` as the default. Mode `off` SHALL send no request. Mode `plan` SHALL select and log the pull request, and SHALL make no model call and no write. Mode `on` SHALL run the attempt.

#### Scenario: The place of the row
- **WHEN** a test reads the rows of the model lane
- **THEN** `fix_plan` follows `retitle`, needs a clone and is due on a first run

#### Scenario: Mode plan
- **WHEN** the row runs in mode `plan` and a plan pull request qualifies
- **THEN** the row makes no model call and no write

### Requirement: The command devops roadmap step fix-plan
`devops roadmap step fix-plan` SHALL print the plan pull request that the step selects, and SHALL make no model call and no write without `--confirm`. With `--confirm` it SHALL run the attempt. `--item` SHALL name the one item to judge. `--dry-run` SHALL make no request and SHALL list the requests and the writes of a run, with the read of the plan of the head before the attempt marks, the marks of a plan that the reader refuses, and the conditions of the push, of the label and of the comment.

#### Scenario: The dry run
- **WHEN** a person runs `devops roadmap step fix-plan --dry-run`
- **THEN** the command sends no request to GitHub or a model, starts no git command, and lists the reads and the writes, with the read of the head before the attempt marks

### Requirement: A plan that the reader refuses uses no attempt
When the plan reader refuses the plan of the head, the step SHALL end the attempt with the result `unreadable`, write only `fix_plan.at` and `fix_plan.result`, make no model call, log one warning with the file and the reason masked and cut to 500 characters, add 1 to `devops_cli_roadmap_fix_plan_total` with `result=unreadable`, and write no result line.

#### Scenario: An unreadable head
- **WHEN** the plan reader refuses `tasks.md` of the head
- **THEN** the warning names `tasks.md` and the reason, the log holds no `roadmap job result:` line, `fix_plan.attempts` does not change, `fix_plan.at` holds the time, and the planner and the review get no request

#### Scenario: The next read waits
- **WHEN** a selection runs less than 6 hours after an unreadable head
- **THEN** the step leaves the item out

### Requirement: The step pushes the plan that passed the checks
When the checks refuse the plan of the head and pass a new plan of the planner that is not the same plan as the head, and no revision is pushed, the step SHALL push that gated plan as one commit on the latest default branch with the result `regated`, also when a step after the checks fails. A failure after the checks SHALL keep its class on the result line.

#### Scenario: A gated plan with a clean review
- **WHEN** the checks refuse the plan of the head, the planner answers a plan that they pass, and the review of that plan has no open finding
- **THEN** the branch holds one new commit on the latest default branch, the result is `regated`, the pull request loses `plan/needs-fix`, and the comment says that the checks refused the old head

#### Scenario: A gated plan with a failed repair
- **WHEN** the checks refuse the plan of the head, the planner answers a plan that they pass, its review has one open finding, and the model call of the repair fails
- **THEN** the branch holds one new commit, the result line holds `result=regated` and `class=provider`, and the pull request keeps `plan/needs-fix`

### Requirement: A stop of the planner before the review is stopped
When a false premise, an open item whose plan on the default branch creates a path that the premise cites, or a head over the budget stops the planner before a gated plan exists, the step SHALL end the attempt with the result `stopped`, keep `plan/needs-fix` and the Status of the item, post one fix-plan comment with the evidence, and log `stop=premise`, `stop=blocked` or `stop=over_budget`, with the class `premise_false` for a false premise.

#### Scenario: Each stop
- **WHEN** the planner stops on a false premise, an open blocker or a head over the budget
- **THEN** the result is `stopped`, the result line names the stop and holds no `before`, the label and the Status stay, and one fix-plan comment holds the evidence

### Requirement: The step ends at its time budget
The setting `roadmap.fix_plan.time_budget_seconds` SHALL start with each call of the step. The step SHALL start no plan run and no review run once the budget is spent. Such an attempt SHALL end with the result `timeout`, SHALL push nothing, SHALL keep the label `plan/needs-fix` and SHALL keep its attempt marks.

#### Scenario: The budget ends during the review of the head
- **WHEN** the budget is 600 seconds and the review of the head ends at 600 seconds with one open finding
- **THEN** the planner gets no request, the head of the branch does not change, the pull request keeps `plan/needs-fix`, and `fix_plan.result` is `timeout`

#### Scenario: The budget ends after a plan run
- **WHEN** the budget of 600 seconds ends while the planner writes a revision of the plan
- **THEN** no review of the revision starts, the step pushes no revision, the head of the branch does not change, and the result line holds `result=timeout`, `class=timeout` and `step=plan`

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

### Requirement: The trace gate of a repair judges only the sentences that the repair adds or changes
The trace gate of a fix-plan attempt SHALL NOT judge a Feasibility sentence that the plan of the head holds word for word, because the trace gate of the run that wrote the head passed it. It SHALL judge each sentence that a reply of the planner adds or changes with the reads of the plan runs of the attempt, and SHALL refuse such a sentence that cites a file that those runs did not read.

#### Scenario: A citation that only the run of the head read
- **WHEN** the checks refuse the plan of the head, whose Feasibility section says that `src/devops_cli/sample.py` was read, and the planner answers a plan that keeps that sentence and reads no file
- **THEN** the plan passes the checks, and the result is `regated`

#### Scenario: A new citation of a file that the attempt did not read
- **WHEN** the planner answers a plan that keeps the sentences of the head and adds `` `read_file openspec/config.yaml 1 20` gives the rules of a plan. ``, and reads no file
- **THEN** the result is `failed`, and the reason says that `openspec/config.yaml` was read but the run did not read it

#### Scenario: A sentence that the repair changes
- **WHEN** the planner answers a plan that changes the line number of a citation in a sentence of the head that says `read_file` of `src/devops_cli/roadmap/decision_step.py`, and the attempt read no file
- **THEN** the trace gate refuses the changed sentence and names `src/devops_cli/roadmap/decision_step.py`

### Requirement: The step records the release of each attempt
For a plan that it reads, the step SHALL write `fix_plan.version`, the release of devops-cli that runs the attempt, with the attempt marks before its first model call.

#### Scenario: The release of the attempt
- **WHEN** an attempt ends
- **THEN** the record holds `fix_plan.version` with the release that ran it

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

### Requirement: The decisions of the step count only blocker and major findings
The step SHALL take `before`, the fixed and added findings of a revision and the open findings of its last review from the open findings of the verification pass, so only a blocker or a major finding counts. A head whose review has only minor or nit findings SHALL be `dismissed` when no other rule applies. The comment of a pushed revision, or of a plan that loses the label, SHALL list the other findings of its reviews as advice. A failed or a worse revision SHALL list none.

#### Scenario: A head with only a minor finding
- **WHEN** the last plan comment lists an open finding, and the review of the head has only a quoted `spec_delta_wrong` finding with the severity `minor`
- **THEN** the planner gets no request, the head of the branch does not change, the result is `dismissed` with `before` 0, the pull request loses `plan/needs-fix`, and the comment lists the finding of the plan comment as dismissed and the minor finding as advice

### Requirement: A comment line with no severity reads as a major finding
The step SHALL read the severity at the start of a finding line of a plan comment. A line with no severity, which a release before #5411 wrote, SHALL read as a major finding, because each open finding of that release kept the draft.

#### Scenario: A real stage comment of the old form
- **WHEN** the step reads the open findings of a real stage comment whose lines have no severity
- **THEN** it reads the finding as a major finding

#### Scenario: A line with a severity
- **WHEN** the step reads a comment that the stage job wrote for a blocker finding
- **THEN** it reads the finding back with the severity `blocker`
