## ADDED Requirements

### Requirement: The stage row runs on the status lane and plans no item
The row `stage` SHALL follow `stage_ready` on the status lane. It SHALL call no model, plan no item and read no model clone: a stage Job plans each item.

#### Scenario: The row makes no model call
- **WHEN** the row runs a round with a Ready item
- **THEN** it reads no model and no model clone, and it creates one stage Job with no owner reference

### Requirement: The Job list is the lock of the stage Jobs
A round SHALL list the stage Jobs of every repository by the component label and take the Jobs of its repository by the owner and repository labels. The selection SHALL leave out each item that a running stage Job or a check-out names. The round SHALL create a Job for each item that the selection takes, up to `roadmap.stage.jobs` (default 1, at least 1) less the stage Jobs that run in the cluster.

#### Scenario: Two items and one running Job
- **WHEN** `roadmap.stage.jobs` is 2, item A has a running stage Job of another body, and item B has none
- **THEN** the round creates one Job, for B, and none for A

#### Scenario: The limit is reached
- **WHEN** `roadmap.stage.jobs` is 1 and a stage Job runs
- **THEN** the round creates no Job

#### Scenario: A stage Job of another repository
- **WHEN** `roadmap.stage.jobs` is 1 and a stage Job of another repository runs
- **THEN** the round creates no Job and recovers nothing

### Requirement: The check-out comes before the create of a stage Job
For each item, the round SHALL write `stage.job`, `stage.job_at` and `stage.job_deadline` with the claim `owner/service` before the create, and SHALL name the Job from the item and the hash of its body. A create that gets 409 SHALL count as the existing Job. A create that fails SHALL take the check-out and the claim back.

#### Scenario: The check-out comes first
- **WHEN** the round creates a Job
- **THEN** the record of the item holds the check-out and the claim `owner/service` at the time of the create

#### Scenario: A second create of the same item and body
- **WHEN** a Job of the same name exists and the list did not show it
- **THEN** the create gets 409, no second Job exists, and the check-out names the Job

#### Scenario: A create that the API refuses
- **WHEN** the API refuses the create
- **THEN** the round fails, and the item holds no check-out and no claim

### Requirement: The cleanup of a stage round comes before any create
Before any create, the round SHALL remove the orphans and the staged branches of closed items, and write the rejections of the items that it does not submit. The selection SHALL read the heads without the branches of the orphans that the round removes.

#### Scenario: An old orphan
- **WHEN** a Ready item holds an intent mark of 2 hours and a pushed branch with no pull request
- **THEN** the round removes the branch and creates the Job of the item in the same round

### Requirement: The stage row checks in for a Job that ended with no check-in
Each round SHALL compare each check-out with the Job list and check in for its Job: `evicted` when the Job is gone, `deadline` when it failed with `DeadlineExceeded` or runs 600 s after the deadline of the check-out, `failed` when it failed otherwise, and `succeeded` when it completed or the item holds its draft. A `deadline` or `failed` end SHALL record the failure marks.

#### Scenario: The deadline
- **WHEN** the Job failed with `DeadlineExceeded`, or runs past the deadline of the check-out, and its pod has a log
- **THEN** the item holds the result `deadline` and the failure class `timeout`, and the round deletes a Job that still runs

#### Scenario: A pod that never ran
- **WHEN** the Job failed with `DeadlineExceeded` and its pod has no log
- **THEN** the item holds the result `deadline` and the failure class `ci_infra`, and the end does not count toward the split

#### Scenario: A Job that ended after its publish
- **WHEN** the Job failed with exit code 143 and the item holds its draft
- **THEN** the item holds the result `succeeded` and no failure mark

#### Scenario: A failure by the exit code
- **WHEN** the Job failed by its pod failure policy with exit code 137 and no check-in
- **THEN** the item holds the result `failed` and the failure class `oom`, from the message of the condition

#### Scenario: A lost check-in
- **WHEN** the Job completed and the check-out still names it
- **THEN** the item is free with no failure mark

### Requirement: The recovery trusts the labels of the Service and the item as it reads now
The round SHALL act on a listed Job only when the item label of the Job, which the Service sets, names the item of the check-out. It SHALL count, log and free an item only when `check_in` wrote, from the item as it reads now.

#### Scenario: A check-out that names the Job of another item
- **WHEN** the check-out of item 2 names the running Job of item 1 with a past deadline
- **THEN** the round deletes no Job and writes nothing on either item

#### Scenario: A check-in after the round read its items
- **WHEN** the round read the item with its check-out and intent mark, and the Job published the draft and checked in before the round listed it
- **THEN** the round recovers nothing, frees nothing and keeps the branch of the draft

### Requirement: An evicted stage Job is free 3 times on one body
A Job that is gone SHALL leave its item due at once with no failure mark, 3 times on one body, and the round SHALL judge the orphan of the item at any age. A later eviction on the same body SHALL record the failure class `ci_infra`.

#### Scenario: A Job that is gone
- **WHEN** the check-out names a Job that the list does not hold
- **THEN** the item holds the result `evicted`, no failure mark and an eviction count of 1, and the round creates its Job again

#### Scenario: The fourth eviction on one body
- **WHEN** the Job of the item is gone for the fourth time on one body
- **THEN** the item holds the failure class `ci_infra`, waits, and holds no count toward the split

#### Scenario: An orphan of a recovered item
- **WHEN** the round removes the orphan of an item that it freed
- **THEN** the item keeps its failure marks, its count and `stage.evictions`, and a later round inside the wait leaves it out as `failed_lately`

### Requirement: A failed stage Job is created again only after its wait
The round SHALL delete an ended Job of the name of a new create first. A failed item SHALL get no new Job until the wait of its failure class ends.

#### Scenario: A failed Job and the wait
- **WHEN** a round recovered a failed Job, and later rounds run inside and after the wait of its class
- **THEN** the Job stays inside the wait, and after it the round deletes the Job and creates it again

### Requirement: Stage Job ends that keep failing return the item for a split
An end of a stage Job with the class `timeout` or `plan_defect` SHALL count toward `roadmap.stage.plan_defect_limit` on the body of the item, as a refused plan does. An end of another class SHALL record the failure marks and SHALL NOT count. The end that reaches the limit SHALL post a comment that asks refine to split the item, set the Status New with no count, and release the claim `owner/service`.

#### Scenario: The third counted end
- **WHEN** the count on the body is 2 and the Job of the item ends with `deadline`
- **THEN** the item is New, its comment asks for a split, and the round creates no Job

#### Scenario: An outage
- **WHEN** a Job fails by exit code 1 and its log names a provider error
- **THEN** the item holds the failure class `provider` and no count toward the split

### Requirement: The rules read the series of the stage Jobs
Each rule of the roadmap Service that reads the model requests, the GitHub writes, the GitHub throttles, the web searches or the tool calls SHALL select `job=~"roadmap-service|roadmap-stage"`. `RoadmapServiceGitHubRequestsHigh` SHALL read the Service alone, and `RoadmapStageGitHubRequestsHigh` SHALL compare the requests of the stage Jobs with the budget that a stage pod reports.

#### Scenario: A rule reads the series of a stage Job
- **WHEN** the Service sends 300 GitHub requests and a stage Job 300 in an hour, with a Service budget of 500 and a stage budget of 1000
- **THEN** neither request alert fires

#### Scenario: A stage Job near its own budget
- **WHEN** a stage Job sends 960 GitHub requests in an hour with a budget of 1000
- **THEN** `RoadmapStageGitHubRequestsHigh` fires

### Requirement: The grades and the counter read the stage Jobs
The job grade report and the panels of the job grades SHALL read the result lines of the Service and of the stage Job pods, and no runner pod. The Service SHALL count each stage Job in `devops_cli_service_stage_jobs_total` by `repo`, `result` and `class`.

#### Scenario: The selector of the grades
- **WHEN** the report plans its queries
- **THEN** each query selects the containers `service` and `stage` of the pods `roadmap-service` and `devops-cli-job`

## MODIFIED Requirements

### Requirement: The stage Job ends with the exit code of its end and checks in
The entry point SHALL exit 0 for a result, 1 for a failure of the item, 75 for a SIGTERM before the time budget ends, and 143 for a SIGTERM after it or a time budget that ends before a model call. Except after a SIGTERM before the time budget ends, it SHALL write `stage.job_result`, clear `stage.job`, `stage.job_at` and `stage.job_deadline`, and release the claim `owner/service` in one write, only when `stage.job` names the Job of the pod. A `deadline` end SHALL record the failure with the class `timeout` and count toward `roadmap.stage.plan_defect_limit` on the body of the item.

#### Scenario: A normal end
- **WHEN** the Job stages its item and the check-out names the Job.
- **THEN** it exits 0, the record holds `stage.job_result` with the result `staged`, and the check-out is clear.

#### Scenario: The check-out of another Job
- **WHEN** the check-out names another Job.
- **THEN** the Job writes no `stage.job_result` and the check-out stays.

#### Scenario: An eviction
- **WHEN** SIGTERM comes before the time budget ends.
- **THEN** the command exits 75 and the check-out stays.

#### Scenario: The deadline
- **WHEN** SIGTERM comes after the time budget ends.
- **THEN** the command exits 143, the record holds the result `deadline`, the failure class `timeout` and a count of 1 on the body, and the check-out is clear.

#### Scenario: A kill after a GitHub write
- **WHEN** the Job is killed after the push, after the draft or after the record write, and its pod runs again
- **THEN** the item ends with one open draft, the full stage record, no intent mark and the check-in of the Job
