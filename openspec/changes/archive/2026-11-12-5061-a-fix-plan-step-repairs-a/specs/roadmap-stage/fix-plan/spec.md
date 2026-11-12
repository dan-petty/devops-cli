## Purpose
How the step `fix-plan` repairs an open plan pull request that holds `plan/needs-fix`: its selection and bounds, the repair with the stage planner and the verification pass, the writes, the marks, the Service row and the command.

## ADDED Requirements

### Requirement: The step selects one plan pull request that holds the label plan/needs-fix
The step `fix-plan` SHALL select, for one call, at most one item of the repository: an open item with the Status Ready whose record holds `stage.pr`, with no `implement.job` and no claim of an agent or a person. Its pull request SHALL be an open draft that holds `plan/needs-fix`. The item SHALL have fewer than 2 attempts on the head of the pull request, no attempt in the last 6 hours, and fewer than 3 revisions on the pull request. The highest priority SHALL go first.

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

### Requirement: The step repairs the plan with the stage planner
The step SHALL read the plan of the head of the pull request with `read_change` and give it to the stage planner at the latest default branch. The planner SHALL get the plan as `previous` and each open finding as `problem`, and the revision SHALL pass the gates and the verification repair rounds of the stage job.

#### Scenario: The open findings of the stage comment
- **WHEN** the stage comment of the item lists an open finding for the pull request
- **THEN** the first planner request holds the head plan as `previous` and that finding in `problem`, and the verification pass reviews only the revision

### Requirement: The open findings come from the last plan comment
The open findings SHALL come from the last comment of the stage job or of the step on the item that names the pull request and that a trusted author made. When no such comment lists an open finding, the verification pass SHALL review the plan of the head and give them.

#### Scenario: No comment lists an open finding
- **WHEN** no trusted comment of the item lists an open finding for the pull request, and the review of the head plan has one
- **THEN** the next planner request holds the head plan as `previous` and the finding of the review in `problem`

#### Scenario: A comment of an untrusted author
- **WHEN** the only comment that lists an open finding has an author with no write access
- **THEN** the step does not read it and reviews the plan of the head

### Requirement: The step pushes a revision with fewer open findings
When the last review of the revision has fewer open findings than the review of the head plan, the step SHALL write the change folder as one commit on the latest default branch, push it to the branch of the pull request with `--force-with-lease` on the head that it read, and set the title and the body of the pull request to those of the revision.

#### Scenario: A revision with fewer open findings
- **WHEN** the review of the head has two open findings and the review of the revision has one
- **THEN** the branch holds one new commit whose parent is the latest default branch, and the pull request keeps `plan/needs-fix`

### Requirement: The label goes when no open finding remains
The step SHALL remove `plan/needs-fix` when the last review has no open finding: the review of a revision that it pushed, or the review of the head plan. It SHALL keep the label while an open finding remains.

#### Scenario: A revision with no open finding
- **WHEN** the review of the head has an open finding and the review of the revision has none
- **THEN** the branch holds the new commit, and the pull request loses `plan/needs-fix`

#### Scenario: A head plan with no open finding
- **WHEN** the review of the head plan has no open finding
- **THEN** the planner gets no request, the head of the branch does not change, and the pull request loses `plan/needs-fix`

### Requirement: A revision that is not better writes only the record
When the revision has as many open findings as the head plan or more, or the plan run fails, the step SHALL write nothing to GitHub except the record of the item.

#### Scenario: A revision that is not better
- **WHEN** the review of the revision has as many open findings as the review of the head
- **THEN** the head of the branch does not change, the label stays, no comment is posted, and the record holds the attempt with the result `unchanged`

### Requirement: The step records each attempt before the model call
The step SHALL write `fix_plan.key` (`<pull>:<head>`), `fix_plan.attempts` and `fix_plan.at` before its first model call, and `fix_plan.result` and `fix_plan.revisions` after the attempt. It SHALL post one comment with the marker `<!-- devops roadmap fix-plan -->` on the issue for each attempt that changes the plan or the label. No new attempt SHALL start once the Service stops.

#### Scenario: The attempt marks
- **WHEN** an attempt pushes a revision
- **THEN** the record holds `fix_plan.key` with the new head and `fix_plan.attempts` 0, `fix_plan.revisions` 1 and `fix_plan.result` `revised` or `cleared`

#### Scenario: The Service stops
- **WHEN** the Service stops before the attempt starts
- **THEN** the step makes no model call and writes no mark

### Requirement: Each attempt logs one result line and counts its result
Each attempt SHALL log one result line with the job `fix_plan`, its result, the counts of the plan runs and the open findings before and after. It SHALL add 1 to `devops_cli_roadmap_fix_plan_total` with the labels `repo` and `result`.

#### Scenario: A counted attempt
- **WHEN** an attempt ends with the result `cleared`
- **THEN** the log holds one line `roadmap job result: job=fix_plan` with `result=cleared`, and the counter holds 1 for that result

### Requirement: The Service runs the step as the row fix_plan in its mode
The model lane SHALL hold the row `fix_plan` after `stage`. The row SHALL need a clone and be due on a first run. The setting `roadmap.fix_plan.mode` SHALL be `off`, `plan` or `on`, with `plan` as the default. Mode `off` SHALL send no request. Mode `plan` SHALL select and log the pull request, and SHALL make no model call and no write. Mode `on` SHALL run the attempt.

#### Scenario: The place of the row
- **WHEN** a test reads the rows of the model lane
- **THEN** `fix_plan` follows `stage`, needs a clone and is due on a first run

#### Scenario: Mode plan
- **WHEN** the row runs in mode `plan` and a plan pull request qualifies
- **THEN** the row makes no model call and no write

### Requirement: The command devops roadmap step fix-plan
`devops roadmap step fix-plan` SHALL print the plan pull request that the step selects, and SHALL make no model call and no write without `--confirm`. With `--confirm` it SHALL run the attempt. `--item` SHALL name the one item to judge. `--dry-run` SHALL make no request and SHALL list the requests and the writes of a run.

#### Scenario: The dry run
- **WHEN** a person runs `devops roadmap step fix-plan --dry-run`
- **THEN** the command sends no request to GitHub or a model, starts no git command, and lists the reads and the writes
