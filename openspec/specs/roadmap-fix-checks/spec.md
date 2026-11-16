# roadmap-fix-checks Specification

## Purpose
How the roadmap step `fix-checks` repairs failed checks on pull requests: bounds enforcement, tier 1 deterministic repair with zero model calls, tier 2 model repair, plan scope confinement, and runner Job integration.

## Requirements

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

### Requirement: Tier 1 resolves deterministic check failures with zero model calls
When a check failure is classified as `lint`, the step SHALL run `ruff check --fix` and `ruff format` on the changed files. When the log shows a docs failure, the step SHALL run `devops docs generate`, and when it shows a lockfile failure, `uv lock`, whatever the class of the check. The step SHALL run the check again locally, and when it passes, push the repair with zero model requests.

#### Scenario: Tier 1 fixes a lint failure with 0 model requests
- **WHEN** a pull request check fails on code formatting or lint errors
- **THEN** the step runs the lint fixers and pushes the repair with 0 model requests

#### Scenario: Tier 1 fixes a docs failure
- **WHEN** a pull request check fails because documentation is out of sync
- **THEN** the step regenerates the documentation and pushes the repair

#### Scenario: Tier 1 fixes a lockfile failure
- **WHEN** a pull request check fails because uv.lock is not updated
- **THEN** the step updates the lockfile and pushes the repair

#### Scenario: A lockfile failure in a test check gets uv lock
- **WHEN** `uv sync --locked` fails in the check `Tests & Coverage`, whose class is test
- **THEN** tier 1 runs `uv lock` and `uv lock --check`, commits `uv.lock`, and makes no model request

### Requirement: Tier 2 repairs failures within plan scope using a model
When Tier 1 does not resolve the failure, the step SHALL inspect the failed log against the repair scope of the item. When the log names no path within the repair scope, the step SHALL stop with zero model calls. When the log names a path in scope, the step SHALL invoke `run_fix_step`.

#### Scenario: A log outside the plan scope stops with 0 model requests
- **WHEN** the failed check log names only paths outside the plan scope
- **THEN** the step stops with 0 model requests

#### Scenario: A log within plan scope runs a fix step
- **WHEN** the failed check log names a path within the plan scope
- **THEN** the step invokes `run_fix_step`

### Requirement: CI infrastructure failures post a comment and wait
When the failure is classified as `ci_infra` and its log shows no docs or lockfile failure, the step SHALL post one comment explaining the infrastructure failure and return status `wait`.

#### Scenario: A CI infrastructure failure waits
- **WHEN** a check fails due to CI infrastructure issues
- **THEN** the step posts a comment, records result wait, and stops

#### Scenario: A lockfile failure in a check of the class ci_infra goes to tier 1
- **WHEN** a stale `uv.lock` fails a check whose name the class reads as infrastructure
- **THEN** the step posts no comment and runs tier 1

### Requirement: The dry run makes zero requests
`devops roadmap step fix-checks --dry-run` SHALL make zero requests and mutate no state.

#### Scenario: Dry run
- **WHEN** `devops roadmap step fix-checks --pull 42 --dry-run` runs
- **THEN** the command exits 0 and makes zero requests

### Requirement: The command repairs a failed check in a runner Job
With `--confirm`, `devops roadmap step fix-checks` SHALL refuse to run outside a runner Job. In a runner Job it SHALL give the step a worktree on the head branch of the pull request, the tier 1 fixers, and the model fix on the task `ai.tasks.fix_checks`. The step SHALL push the commit of a fixer to the head branch with a lease on the judged head, and SHALL return `repaired` with the new head.

#### Scenario: A failed check whose log names a file of the plan ends repaired
- **WHEN** the command runs with `--confirm` on a bot pull request whose `Static Analysis` check failed with a log that names a file of the plan, and the model fix commits a change
- **THEN** the step returns `repaired`, and the head branch on `origin` has one new commit

#### Scenario: The command refuses to repair outside a runner Job
- **WHEN** the command runs with `--confirm` in a process that is not a runner Job
- **THEN** the command exits 1 and reads no pull request

#### Scenario: A push whose lease breaks is refused
- **WHEN** another writer moves the head branch on `origin` after the judgment and before the push
- **THEN** the push fails, the commit of the other writer stays, the step records no repair, and the worktree goes

#### Scenario: The checkout refuses another branch or another head
- **WHEN** the branch of the item is not the head branch of the pull request, or its tip is not the judged head
- **THEN** the checkout raises an error before any fixer runs, and its worktree and local branch go

### Requirement: The step writes nothing without --confirm
Without `--confirm`, the step SHALL return `planned` with the action that it would take. It SHALL post no comment, write no mark, make no checkout, run no fixer and push nothing.

#### Scenario: A run without --confirm writes nothing
- **WHEN** the step runs without `--confirm` on a bot pull request with a failed check
- **THEN** the step returns `planned`, and GitHub, the store and the branch are unchanged

### Requirement: The model fix of one run has a cap of new tokens
The model fix of one `fix-checks` run SHALL stop before a model request when its new tokens (input that the provider did not read from its cache, and output) reach `roadmap.fix_checks.token_budget`. The default SHALL be 16,000,000. The stop SHALL name the setting, and the cap SHALL get no extension.

#### Scenario: A fix step at its cap stops and names the setting
- **WHEN** the new tokens of the step reach the cap
- **THEN** the step stops before the next request, and the reason names `roadmap.fix_checks.token_budget`

### Requirement: The step marks a repaired draft ready only by the readiness rule
When the step finds an implement draft that it repaired, with every check passing on the head, it SHALL ask `draft_readiness`. It SHALL mark the draft ready with the expected head only when the answer is ready, and SHALL return `ready`. Otherwise it SHALL leave the draft as it is.

#### Scenario: A repaired draft whose checks pass is marked ready
- **WHEN** the step runs with `--confirm` on a repaired implement draft whose checks pass and that `draft_readiness` calls ready
- **THEN** the step marks the draft ready with the expected head and returns `ready`

### Requirement: The step leaves an item to its live implement Job
When the record of the item names an implement Job with no recorded state (`implement.job` set and `implement.job_state` empty), the step SHALL return `skipped` with no checkout, no comment and no mark. A Job with a recorded state has ended and SHALL NOT stop the step.

#### Scenario: An item that a live implement Job holds is skipped
- **WHEN** the step runs with `--confirm` on a bot pull request whose item records `implement.job` and no `implement.job_state`
- **THEN** the step returns `skipped` with a reason that names the Job, and makes no checkout, no comment and no mark

#### Scenario: An item whose implement Job ended is judged
- **WHEN** the step runs on a bot pull request whose item records `implement.job` and `implement.job_state`
- **THEN** the step judges the failed check

### Requirement: The step does not repeat a round that ended with no repair
When `fix_checks.key` equals `<head>:<check>` of the check of the round (the check that `--check` names, else the first failed check) and `fix_checks.result` is `failed`, `stopped` or `wait`, the step SHALL return `skipped` before it reads the log, with no model request, no comment and no new mark. A new head or another failed check SHALL start a round.

#### Scenario: The same head and check get no second round
- **WHEN** the step runs with `--confirm` on a head and check whose last round ended `failed`, `stopped` or `wait`
- **THEN** the step returns `skipped`, makes no checkout and no model request, posts no comment, and leaves the record as it is

#### Scenario: A new head or a new failed check starts a round
- **WHEN** the record holds a failed round of another head, or of another check on the same head
- **THEN** the step runs the round on the head and check of now

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
The implement, stage and fix-checks Jobs SHALL run at most `roadmap.model_jobs` at once (default 2), for every repository together. A fix Job with no free place SHALL be created suspended, and the watch row SHALL resume it first. A waiting fix Job SHALL hold its place against a new implement or stage Job only while the mode is not `off`, its repository is in `service.repos`, and it waited at most `roadmap.fix_checks.max_wait_minutes`.

#### Scenario: A waiting fix Job holds the place of a new implement Job
- **WHEN** `roadmap.model_jobs` is 1, a fix Job waits suspended, and an implement unit is due
- **THEN** the implement row creates no Job and waits

#### Scenario: A waiting fix Job holds the place of a new stage Job
- **WHEN** `roadmap.model_jobs` is 1, a fix Job waits suspended, and a Ready item is due for stage
- **THEN** the stage row creates no Job

#### Scenario: The watch row resumes the waiting fix Job
- **WHEN** a model Job ends while a fix Job of the repository waits suspended
- **THEN** the next round of the watch row resumes the fix Job and creates no other Job for its unit

#### Scenario: A waiting fix Job of a repository outside service.repos holds no place
- **WHEN** `service.repos` holds `example/project` and a fix Job of `example/other` waits suspended
- **THEN** `model_slots` counts no waiting Job, and a fix Job of `example/project` counts one

### Requirement: The limits of a fix Job nest under the cap
The deadline of a fix Job SHALL be `roadmap.implement.step_time_limit_seconds` plus 1800 s. The Service SHALL refuse to build the Job when the order request < command < step < deadline <= 14400 s breaks, or when the deadline is less than 300 s above the step.

#### Scenario: The defaults and the cluster values nest
- **WHEN** the deadline is computed from the code defaults or from the values of `k8s/devops/configmap.example.yaml`
- **THEN** request < command < step < deadline <= 14400, and the deadline is at least 300 s above the step

#### Scenario: A deadline above the cap is refused
- **WHEN** the step limit gives a deadline above 14400 s, or the command limit is not below the step limit
- **THEN** the Service raises a configuration error that names the setting, and the admission policy refuses a Job with a deadline of 14401

### Requirement: The watch row reports each ended fix Job once
The watch row SHALL read the result line of each ended fix Job once, log it as the result line of the job `fix_checks`, count it in `devops_cli_service_fix_checks_jobs_total`, and write it in the Job annotation `roadmap.devops-cli/outcome`. A Job with no result line SHALL have the outcome `deadline` when its deadline ended it, `error` when its command exited 1, and else `none`. The alert `RoadmapFixChecksJobWithoutResult` SHALL fire for each of the three.

#### Scenario: An ended Job is reported once
- **WHEN** a fix Job ends with the result line `planned` and the watch row runs twice
- **THEN** the first round logs and counts `planned` and writes the annotation, and the second round reports nothing

#### Scenario: A Job with no result line fires the alert
- **WHEN** the counter of the result `none`, `error` or `deadline` grows in the last hour
- **THEN** `RoadmapFixChecksJobWithoutResult` fires for the repository

#### Scenario: A Job that its deadline ended is deadline
- **WHEN** a fix Job ends with the condition reason `DeadlineExceeded` and no result line
- **THEN** the round reports and counts the outcome `deadline`

### Requirement: A fix Job with no result line gets the next attempt
When the last attempt of a unit has the outcome `none`, the watch row SHALL create the next attempt, named from `<pr>:<head>:<check>#<n>`, after a wait of 30 minutes doubled at each attempt up to 2 hours, and at most `roadmap.implement.continuations_per_item` attempts after the first. A Job with a result line, or with the outcome `error` or `deadline`, SHALL end its unit.

#### Scenario: The next attempt waits
- **WHEN** a fix Job ended with no result line
- **THEN** no Job is created before 30 minutes, and attempt 2 is created after them

#### Scenario: The attempts stop at the cap
- **WHEN** `roadmap.implement.continuations_per_item` is 1 and each attempt ends with no result line
- **THEN** the unit has 2 Jobs and no third

#### Scenario: A result line ends the unit
- **WHEN** the Job of a unit ended with a result line
- **THEN** the watch row creates no other Job for that head and check

#### Scenario: A Job that its deadline ended gets no next attempt
- **WHEN** the Job of a unit has the outcome `deadline`, and the watch row runs a day later
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

### Requirement: The cluster template lets six model Jobs run
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set `roadmap.model_jobs` to 6, the owner choice for all repositories together. The code default of the setting SHALL stay 2.

#### Scenario: The rendered template and the code default
- **WHEN** the settings model reads the `roadmap` section of the template, and when no value sets `roadmap.model_jobs`
- **THEN** the template gives 6, and the code default is 2

### Requirement: The item record keeps the attempts of a fix unit
In mode `on`, the watch row SHALL write the attempt, the outcome and the next allowed time of each fix Job that it reports in the item record `fix_checks.units`, keyed by `<pr>:<head>:<check>`, and a unit with no Job SHALL take its last attempt from that record, so the TTL of a Job resets nothing. Mode `plan` SHALL write no record.

#### Scenario: The attempt after the TTL is the next attempt
- **WHEN** in mode `on` attempt 1 of a unit ended with no result line, the TTL deleted it, and the unit is due a day later
- **THEN** the watch row creates attempt 2

#### Scenario: An error in the record ends the unit after the TTL
- **WHEN** in mode `on` the Job of a unit ended with the outcome `error` and the TTL deleted it
- **THEN** the watch row creates no Job for that unit

#### Scenario: Mode plan writes no unit record
- **WHEN** in mode `plan` the watch row reports an ended fix Job
- **THEN** the item record holds no `fix_checks.units`

### Requirement: One pull request has at most one live fix Job
The watch row SHALL create no Job for a unit of a pull request while a fix Job of that pull request runs or waits suspended. A unit of another check or another head of that pull request SHALL get its Job after that Job ends.

#### Scenario: A second failed check waits for the live Job
- **WHEN** the fix Job of the lint check of a head runs and a test shard of the same head fails
- **THEN** the round creates no Job, and it creates the Job of the shard after the lint Job ends with no repair

#### Scenario: A new head is a new unit
- **WHEN** the fix Job of the old head ended and the new head of the pull request fails a check
- **THEN** the round creates one Job for the new head

### Requirement: The watch row deletes a fix Job that waited too long
The watch row of any repository SHALL delete a fix Job that waited suspended longer than `roadmap.fix_checks.max_wait_minutes` (default 360), also a Job of a repository outside `service.repos`, and SHALL write a log line that names it. The policy `roadmap-service-job-deletes` SHALL admit the delete of a suspended fix-checks Job by the Service, and SHALL refuse the delete of a runner Job that runs.

#### Scenario: A fix Job past the wait limit is deleted
- **WHEN** a fix Job of `example/other` waited suspended one second longer than the limit, and the round of `example/project` runs
- **THEN** the round deletes it, logs one line that names it, and counts `expired`

#### Scenario: A fix Job within the wait limit stays
- **WHEN** a fix Job waited suspended exactly the limit
- **THEN** the round deletes nothing

#### Scenario: The policy admits only the delete of a waiting fix Job
- **WHEN** the Service deletes a stage Job, a suspended fix-checks Job, a fix-checks Job that runs, and a runner Job
- **THEN** the policy admits the first two and refuses the last two

### Requirement: The ready path of the step needs no repair
With `ready_only`, the step `fix-checks` SHALL run only its ready path: a head with a failed check SHALL give `skipped`, with no repair, no comment, no ready mark and no record.

#### Scenario: A check that fails after the read of the watch row
- **WHEN** the step runs with `ready_only` and `--confirm` on a repaired draft whose head has a failed check, of the class lint or `ci_infra`
- **THEN** the step gives `skipped`, posts no comment and marks nothing ready

### Requirement: The fix-checks panel draws 3 series and Other
The panel `Service Fix-Checks Jobs by Result` SHALL draw one series for each of Started (created, resumed), Repaired (repaired, ready) and No result line (none, error, deadline), and one series Other for each other result, each with a fixed legend.

#### Scenario: The panel has 4 fixed series
- **WHEN** the dashboard `roadmap-service-telemetry` is read
- **THEN** the panel has the targets Started, Repaired, No result line and Other, and no legend that names a label
