## RENAMED Requirements

- FROM: `### Requirement: The open findings come from the last plan comment`
- TO: `### Requirement: The review of the head counts the open findings before the repair`

## MODIFIED Requirements

### Requirement: The step repairs the plan with the stage planner
The step SHALL read the plan of the head of the pull request with `read_change` and give it to the stage planner at the latest default branch. The planner SHALL get the plan as `previous` and each open finding of the review of the head and of the last plan comment as `problem`, and the revision SHALL pass the gates and the verification repair rounds of the stage job.

#### Scenario: The open findings of the stage comment
- **WHEN** the stage comment of the item lists an open finding for the pull request, and the review of the head plan has another open finding
- **THEN** the first planner request holds the head plan as `previous` and both findings in `problem`

### Requirement: The review of the head counts the open findings before the repair
In each attempt the verification pass SHALL review the plan of the head at the latest default branch, and the open findings of that review SHALL be the findings before the repair that the step compares with the last review of the revision. The step SHALL also read the open findings of the last comment of the stage job or of the step on the item that names the pull request and that a trusted author made, and give them to the planner. It SHALL NOT count them: an earlier review wrote the comment, at an earlier commit.

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
- **THEN** the planner gets no request, the head of the branch does not change, and the pull request loses `plan/needs-fix`

### Requirement: Each attempt logs one result line and counts its result
Each attempt SHALL log one result line with the job `fix_plan`, its result, the counts of the plan runs, the open findings that the last plan comment lists (`comment`), the open findings of the review of the head (`before`) and those of the last review of the revision (`after`). It SHALL add 1 to `devops_cli_roadmap_fix_plan_total` with the labels `repo` and `result`.

#### Scenario: A counted attempt
- **WHEN** an attempt ends with the result `cleared`
- **THEN** the log holds one line `roadmap job result: job=fix_plan` with `result=cleared` and the counts `comment`, `before` and `after`, and the counter holds 1 for that result
