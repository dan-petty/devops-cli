## MODIFIED Requirements

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

### Requirement: The step pushes a revision with fewer open findings
When the revision of a repair is not the same plan as the plan that passed the checks, and its last review has fewer open findings than the review of the head, the step SHALL write the change folder as one commit on the latest default branch, push it to the branch of the pull request with `--force-with-lease` on the head that it read, and set the title and the body of the pull request to those of the revision. Two plans SHALL be the same plan when `render_change` gives the same files for both with one change name and one date.

#### Scenario: A revision with fewer open findings
- **WHEN** the review of the head has two open findings and the review of the revision has one
- **THEN** the branch holds one new commit whose parent is the latest default branch, the result is `revised`, and the pull request keeps `plan/needs-fix`

#### Scenario: A repair that gives the same plan
- **WHEN** the review of the head has one open finding, the planner answers the plan of the head, and the review of that plan has none
- **THEN** the head of the branch does not change, the result is `unchanged`, the result line holds `success=false`, and the pull request keeps `plan/needs-fix`

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
- **WHEN** the review of the revision has as many open findings as the review of the head
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
Each attempt on a plan that the reader reads SHALL log one result line with the job `fix_plan`, its result, the counts of the plan runs and the open findings that the last plan comment lists (`comment`). The line SHALL hold the open findings of the review of the head (`before`) only when that review ran, and those of the last review of the revision (`after`) only when a review of a revision ran. A stop of the planner SHALL add `stop`, and a failure SHALL add `step` and its class. Each attempt SHALL add 1 to `devops_cli_roadmap_fix_plan_total` with the labels `repo` and `result`. Only `revised` and `cleared` SHALL be a success.

#### Scenario: A counted attempt
- **WHEN** an attempt ends with the result `cleared`
- **THEN** the log holds one line `roadmap job result: job=fix_plan` with `result=cleared`, `success=true` and the counts `comment`, `before` and `after`, and the counter holds 1 for that result

### Requirement: The command devops roadmap step fix-plan
`devops roadmap step fix-plan` SHALL print the plan pull request that the step selects, and SHALL make no model call and no write without `--confirm`. With `--confirm` it SHALL run the attempt. `--item` SHALL name the one item to judge. `--dry-run` SHALL make no request and SHALL list the requests and the writes of a run, with the read of the plan of the head before the attempt marks, the marks of a plan that the reader refuses, and the conditions of the push, of the label and of the comment.

#### Scenario: The dry run
- **WHEN** a person runs `devops roadmap step fix-plan --dry-run`
- **THEN** the command sends no request to GitHub or a model, starts no git command, and lists the reads and the writes, with the read of the head before the attempt marks

## ADDED Requirements

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
