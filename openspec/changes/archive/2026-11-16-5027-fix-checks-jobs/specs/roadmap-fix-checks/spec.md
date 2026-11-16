## ADDED Requirements

### Requirement: One launcher seam builds the Job of a row
The Service SHALL build the implement and the fix-checks Jobs from the suspended CronJob `devops-cli-runner` through one seam that takes the args, the size, the name, the deadline and the labels of the row. Only the implement Job SHALL carry the label `implement-repo`, and a Job of another row SHALL send its telemetry as `roadmap-<row>`.

#### Scenario: The admission policy admits a fix Job
- **WHEN** the seam builds the fix-checks Job of pull request 7 of `example/project` with or without `--confirm`, suspended or not
- **THEN** the Job has the runner image, the args only, 4 CPU with 6Gi, the component `roadmap-fix-checks`, no `implement-repo` label, and the gate check `tests/gate/k8s_checks/job_admission_policy.py` admits it

#### Scenario: A running fix Job holds no implement lock
- **WHEN** a fix-checks Job runs and a new implement unit is due with a free place
- **THEN** the implement row creates the implement Job

### Requirement: The watch row starts one fix-checks Job for a due unit
In mode `plan` or `on` of `roadmap.fix_checks.mode`, the watch row SHALL create one Job for each due unit, named `RepoRef.unit_name(fix-checks, "<pr>:<head>:<check>", item)`, that runs `devops roadmap step fix-checks` with `--repo`, `--pull`, `--head` and `--check`, and with `--confirm` only in mode `on`. A second create of the name SHALL get 409. Mode `off` SHALL send no request.

#### Scenario: Plan mode starts a Job and writes nothing to GitHub
- **WHEN** the watch row finds a finished bot delivery pull request with a failed `Tests & Coverage` check in mode `plan`
- **THEN** the cluster holds one fix-checks Job with no `--confirm`, and the row sends GitHub only its GraphQL read

#### Scenario: A second create of the same unit gets 409
- **WHEN** the seam creates the Job of the same head and check twice
- **THEN** the second create raises the 409 error and the cluster holds one Job

#### Scenario: Mode on runs the step with confirm
- **WHEN** the mode is `on` and a unit is due
- **THEN** the args of the Job end with `--confirm`

### Requirement: A fix Job goes first under the shared model limit
The implement, stage and fix-checks Jobs SHALL run at most `roadmap.model_jobs` at once (default 2), for every repository together. A fix Job with no free place SHALL be created suspended and SHALL hold its place against a new implement or stage Job, and the watch row SHALL resume it first. In mode `off` a suspended fix Job SHALL hold no place.

#### Scenario: A waiting fix Job holds the place of a new implement Job
- **WHEN** `roadmap.model_jobs` is 1, a fix Job waits suspended, and an implement unit is due
- **THEN** the implement row creates no Job and waits

#### Scenario: A waiting fix Job holds the place of a new stage Job
- **WHEN** `roadmap.model_jobs` is 1, a fix Job waits suspended, and a Ready item is due for stage
- **THEN** the stage row creates no Job

#### Scenario: The watch row resumes the waiting fix Job
- **WHEN** a model Job ends while a fix Job of the repository waits suspended
- **THEN** the next round of the watch row resumes the fix Job and creates no other Job for its unit

### Requirement: The limits of a fix Job nest under the cap
The deadline of a fix Job SHALL be `roadmap.implement.step_time_limit_seconds` plus 1800 s. The Service SHALL refuse to build the Job when the order request < command < step < deadline <= 14400 s breaks, or when the deadline is less than 300 s above the step.

#### Scenario: The defaults and the cluster values nest
- **WHEN** the deadline is computed from the code defaults or from the values of `k8s/devops/configmap.example.yaml`
- **THEN** request < command < step < deadline <= 14400, and the deadline is at least 300 s above the step

#### Scenario: A deadline above the cap is refused
- **WHEN** the step limit gives a deadline above 14400 s, or the command limit is not below the step limit
- **THEN** the Service raises a configuration error that names the setting, and the admission policy refuses a Job with a deadline of 14401

### Requirement: The watch row reports each ended fix Job once
The watch row SHALL read the result line of each ended fix Job once, log it as the result line of the job `fix_checks`, count it in `devops_cli_service_fix_checks_jobs_total`, and write it in the Job annotation `roadmap.devops-cli/outcome`. A Job with no result line SHALL have the outcome `none`, and the alert `RoadmapFixChecksJobWithoutResult` SHALL fire.

#### Scenario: An ended Job is reported once
- **WHEN** a fix Job ends with the result line `planned` and the watch row runs twice
- **THEN** the first round logs and counts `planned` and writes the annotation, and the second round reports nothing

#### Scenario: A Job with no result line fires the alert
- **WHEN** the counter of the result `none` grows in the last hour
- **THEN** `RoadmapFixChecksJobWithoutResult` fires for the repository

### Requirement: A fix Job with no result line gets the next attempt
When the last Job of a unit has the outcome `none`, the watch row SHALL create the next attempt, named from `<pr>:<head>:<check>#<n>`, after a wait of 30 minutes doubled at each attempt up to 2 hours, and at most `roadmap.implement.continuations_per_item` attempts after the first. A Job with a result line SHALL end its unit.

#### Scenario: The next attempt waits
- **WHEN** a fix Job ended with no result line
- **THEN** no Job is created before 30 minutes, and attempt 2 is created after them

#### Scenario: The attempts stop at the cap
- **WHEN** `roadmap.implement.continuations_per_item` is 1 and each attempt ends with no result line
- **THEN** the unit has 2 Jobs and no third

#### Scenario: A result line ends the unit
- **WHEN** the Job of a unit ended with a result line
- **THEN** the watch row creates no other Job for that head and check

### Requirement: The step repairs the check that its caller names
With `--check`, the step SHALL take that failed check of the head, and SHALL return `skipped` when the check does not fail on the head. With no `--check` it SHALL take the first failed check.

#### Scenario: The named check is the check of the round
- **WHEN** two checks fail and the step runs with `--check` on the second
- **THEN** the planned action names the second check

#### Scenario: A named check that does not fail is skipped
- **WHEN** the step runs with `--check` on a check that does not fail on the head
- **THEN** the step returns `skipped`

### Requirement: A push that the lease refuses after a move of the head is a skip
When the push of a repair fails and the head of the pull request moved after the judgment, the step SHALL return `skipped` and write no mark. A refused push on a head that did not move SHALL stay an error.

#### Scenario: A moved head refuses the push
- **WHEN** another writer moves the head after the judgment and the lease refuses the push
- **THEN** the step returns `skipped` and the `fix_checks.*` marks stay unset

#### Scenario: A refusal on an unmoved head raises
- **WHEN** the push fails and the head did not move
- **THEN** the step raises the git error

### Requirement: A kill of the step exits 75
When SIGTERM ends `devops roadmap step fix-checks` while the step runs, the command SHALL exit 75 and write no result line.

#### Scenario: SIGTERM during the step
- **WHEN** an eviction sends SIGTERM to the pod while the step runs
- **THEN** the command exits 75 with no result line

### Requirement: The implement repair loop keeps its own counts
The repair loop of the implement Job SHALL NOT write the `fix_checks.*` marks. It SHALL count its rounds in `implement.repair_rounds` only, so the fix-checks unit after the Job has its own caps.

#### Scenario: A repair round of the implement Job
- **WHEN** the implement Job repairs a failed check and its checks then pass
- **THEN** the record of the item holds no `fix_checks.*` mark

## MODIFIED Requirements

### Requirement: The step admits only bot pull requests and enforces bounds
The step `fix-checks` SHALL judge only open bot pull requests. It SHALL stop on an `owner/*` label of the pull request or the item, but not on the Service's own `owner/service`. When an expected head is given, the step SHALL skip when the remote head differs. It SHALL enforce a soft cap of 3 rounds (more while the errors fall), a hard cap of 5 rounds, and at most 3 heads with a failed check per pull request.

#### Scenario: A pull request with an owner label stops
- **WHEN** `fix-checks` runs on a pull request with an `owner/human` or `owner/agent` label
- **THEN** the step stops and makes no changes

#### Scenario: The claim of the Service does not stop the step
- **WHEN** `fix-checks` runs on a pull request and an item that hold `owner/service`
- **THEN** the step judges the failed check

#### Scenario: A moved head returns skipped
- **WHEN** the head of the pull request differs from the expected head
- **THEN** the step returns skipped

#### Scenario: Caps enforce round limits
- **WHEN** a pull request reaches 5 rounds or reaches the soft cap without error reduction
- **THEN** the step halts further attempts

#### Scenario: Head cap stops after 3 heads
- **WHEN** a pull request already has 3 distinct heads recorded and a new head arrives with a failed check
- **THEN** the step halts further attempts

#### Scenario: A draft whose checks pass after the third repair is marked ready
- **WHEN** the step runs with `--confirm` on the head that its third repair pushed, every check passes, and `draft_readiness` answers ready
- **THEN** the step marks the draft ready and returns `ready`

### Requirement: The step does not repeat a round that ended with no repair
When `fix_checks.key` equals `<head>:<check>` of the check of the round (the check that `--check` names, else the first failed check) and `fix_checks.result` is `failed`, `stopped` or `wait`, the step SHALL return `skipped` before it reads the log, with no model request, no comment and no new mark. A new head or another failed check SHALL start a round.

#### Scenario: The same head and check get no second round
- **WHEN** the step runs with `--confirm` on a head and check whose last round ended `failed`, `stopped` or `wait`
- **THEN** the step returns `skipped`, makes no checkout and no model request, posts no comment, and leaves the record as it is

#### Scenario: A new head or a new failed check starts a round
- **WHEN** the record holds a failed round of another head, or of another check on the same head
- **THEN** the step runs the round on the head and check of now
