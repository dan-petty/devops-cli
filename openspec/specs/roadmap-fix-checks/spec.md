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
When a check failure is classified as `lint`, the step SHALL run `ruff check --fix` and `ruff format` on the changed files. Whatever the class of the check, a docs failure SHALL get `devops docs generate`, a lockfile failure `uv lock`, and a failed snapshot test the snapshot update of the toolchain and `devops docs generate`. The step SHALL run the check again locally, and when it passes, push the repair with zero model requests.

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

#### Scenario: Tier 1 writes a snapshot and the documents again
- **WHEN** the log of `Tests & Coverage (shard 3 of 4)` holds `FAILED tests/ai/mcp/test_mcp_tool_listing.py::test_the_tool_listing_matches_the_snapshot - assert [+ received] == [- snapshot]`
- **THEN** tier 1 runs `uv run pytest -n 0 --snapshot-update tests/ai/mcp/test_mcp_tool_listing.py` and `uv run devops docs generate`, then `uv run devops ci test tests/ai/mcp/test_mcp_tool_listing.py` and `uv run devops ci docs`, commits the snapshot and the document, and makes no model request

### Requirement: Tier 2 repairs failures within plan scope using a model
When Tier 1 does not resolve the failure, the step SHALL inspect the failed log against the repair scope of the item: the paths of the plan, and the failed files that the change of the branch causes. When the log names no path within the scope, the step SHALL stop with zero model calls, with a reason that names each failed file and why. When the log names a path in scope, the step SHALL invoke `run_fix_step`, which MAY change the failed files that the change causes.

#### Scenario: A log outside the plan scope stops with 0 model requests
- **WHEN** the failed check log names only files outside the plan scope that the change of the branch does not cause
- **THEN** the step stops with 0 model requests, and the reason names each file

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
With `--confirm`, `devops roadmap step fix-checks` SHALL refuse to run outside a runner Job. In a runner Job it SHALL give the step a plain clone on the head branch, the rebase onto main, the tier 1 fixers and the model fix of `ai.tasks.fix_checks`. The fix SHALL be one commit on the judged head, or, for a branch that the agent rebased, on the work, archive and later commits that replace the branch. `publish` SHALL push with a lease on the judged head, and return `repaired` with the new head.

#### Scenario: A failed check whose log names a file of the plan ends repaired
- **WHEN** the command runs with `--confirm` on a bot pull request whose `Static Analysis` check failed with a log that names a file of the plan, and the model fix commits a change
- **THEN** the step returns `repaired`, and the head branch on `origin` has one new commit

#### Scenario: The command refuses to repair outside a runner Job
- **WHEN** the command runs with `--confirm` in a process that is not a runner Job
- **THEN** the command exits 1 and reads no pull request

#### Scenario: A push whose lease breaks is refused
- **WHEN** another writer moves the head branch on `origin` after the judgment and before the push
- **THEN** the push fails, the commit of the other writer stays, and the step records no repair

#### Scenario: The checkout refuses another branch or another head
- **WHEN** `origin` holds no head branch of the pull request, or its tip is not the judged head
- **THEN** the checkout raises an error before any fixer runs

#### Scenario: A branch behind main is rebased and repaired
- **WHEN** main gets a new commit after the branch point, and the model fix commits a change
- **THEN** the step returns `repaired`, the new head holds the tip of main and not the judged head, and two commits follow the tip of main: the work of the branch and the fix

#### Scenario: The archive stays its own commit
- **WHEN** the branch ends with the archive commit of the item, and main gets a new commit after the branch point
- **THEN** three commits follow the tip of main: the work of the branch, the archive commit and the fix

#### Scenario: A rebase conflict that no rule settles
- **WHEN** main changes a source file that the branch also changes
- **THEN** the step returns `stopped` with a reason that starts with `Conflict: ` and names the file, sends no model request and pushes nothing

#### Scenario: A lease that moved after a rebase
- **WHEN** another writer moves the head branch after the rebase and before the push, and GitHub then gives the moved head
- **THEN** the step returns `skipped` with the reason `Head has moved: the lease refused the push`, and the commit of the other writer stays

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

### Requirement: A comment names the files of a pushed repair
After the push of a repair, the step SHALL upsert its marked comment for the check. The comment SHALL name each file of the commit of tier 1, or each failed file outside the plan that the model fix could change, with its reason, masked and in a fenced block.

#### Scenario: Tier 1 names the files that it wrote
- **WHEN** tier 1 writes `docs/MCP_TOOLS.md` and a snapshot again and pushes the repair
- **THEN** the comment of the step names both files

#### Scenario: Tier 2 names the files that the change causes
- **WHEN** the model fix repairs a caller outside the plan and the step pushes the repair
- **THEN** the comment of the step names the file and the changed name that it uses

### Requirement: The Job makes its process unreadable before the repair
With `--confirm` in a runner Job, each phase of `devops roadmap step fix-checks` SHALL clear the dumpable flag of its own process and adopt the orphans of a step first, before the runner check and before it reads a file of the run. A kernel that refuses either call SHALL stop the command before the step.

#### Scenario: A confirmed round hardens its process first
- **WHEN** the command runs with `--confirm` in a runner Job, with each value of `--phase`
- **THEN** it calls `deny_environment_reads`, then `adopt_orphans`, then the runner check, or the check of the agent phase for `--phase agent`, and only then the phase

### Requirement: The step marks an implement draft ready only by the readiness rule
When the step finds an implement draft that it repaired (`fix_checks.result` equal to `repaired`), or whose implement Job ended at the draft (`implement.result` equal to `drafted`), whose item holds no stop, with every check passing on the head, it SHALL ask `draft_readiness`. It SHALL mark the draft ready with the expected head only when the answer is ready, and SHALL return `ready`. Otherwise it SHALL leave the draft as it is.

#### Scenario: A repaired draft whose checks pass is marked ready
- **WHEN** the step runs with `--confirm` on a repaired implement draft whose checks pass and that `draft_readiness` calls ready
- **THEN** the step marks the draft ready with the expected head and returns `ready`

#### Scenario: A drafted implement draft whose checks pass is marked ready
- **WHEN** the step runs with `--confirm` and `ready_only` on an implement draft whose item records `implement.result` equal to `drafted`, whose checks pass and that `draft_readiness` calls ready
- **THEN** the step marks the draft ready with the expected head and returns `ready`

### Requirement: The repair runs as the phases prepare, agent and publish
With `--confirm`, `devops roadmap step fix-checks` SHALL take `--phase prepare|agent|publish|all`, with `all` by default and `--work` for each other phase. `prepare` SHALL judge the round and clone with git and GitHub calls only, and leave no credential in `work/`. The agent phase SHALL make no GitHub call. `publish` SHALL check the claim, publish the patch, and write the record and the comment of the round.

#### Scenario: The three phases on a run folder
- **WHEN** `prepare`, `agent` and `publish` run one after the other on one run folder for a failed check
- **THEN** the agent phase sends no request, and `publish` returns `repaired` with the new head and records the repair

#### Scenario: A round that prepare ends
- **WHEN** the item holds an owner label
- **THEN** `prepare` gives the report `stopped` and writes no inputs, the agent phase writes nothing, and `publish` gives no second report

#### Scenario: A wait or a ready mark that prepare ends
- **WHEN** `prepare` waits on a CI infrastructure failure, or marks a green draft ready, in separate phases
- **THEN** `prepare` gives the report `wait` or `ready`, and `publish` gives no second report, posts no second comment and marks nothing again

#### Scenario: A state that says ended while a step is due
- **WHEN** the state file says that the round ended, and the round has a repair or a ready mark due
- **THEN** `publish` raises `PhaseOutputError` and pushes nothing

#### Scenario: Prepare on a hostile branch
- **WHEN** `prepare` runs on a head branch with a build hook
- **THEN** it starts only git, and gh for the log of the failed run, and its clone holds no token, no credential helper and no extra header

#### Scenario: The workflow files of the plan
- **WHEN** the merged plan of the item names `.github/workflows/ci.yml`
- **THEN** `publish` reads that file from the merged plan on the default branch, and lets the patch change it and no other workflow file

#### Scenario: A phase with no run folder
- **WHEN** the command runs `--phase agent` with no `--confirm`, or `--phase publish` with no `--work`
- **THEN** the command exits 1

### Requirement: Publish checks the claim before the push
`publish` SHALL run `check_preconditions` on the pull request and the item as GitHub holds them at its start and again right before the push. A round that the check stops SHALL push nothing and write no record.

#### Scenario: A claim after the agent phase
- **WHEN** an owner label appears on the pull request after the agent phase, before `publish` starts or before its push
- **THEN** `publish` returns `stopped` with the reason, pushes nothing and writes no record

### Requirement: Publish builds the target of its push from GitHub
`publish` SHALL check the state of `prepare` against the live pull request: the repository, the pull request, the head branch, the item and the judged head. It SHALL push to the live head branch of the repository on GitHub with a lease on the judged head, as the bot, with the workflow files that it reads from the merged plan. The state file SHALL name no URL. A separate `publish` SHALL take the check from the failed checks of the judged head.

#### Scenario: A fixer that rewrites the state file in one process
- **WHEN** a fixer of `--phase all` writes another branch, author and workflow rule over the state file of its run
- **THEN** `publish` pushes to the head branch of the pull request as the bot, with the workflow files of the merged plan

#### Scenario: A state file with another branch between separate phases
- **WHEN** the state file names a head branch other than the head branch of the pull request
- **THEN** `publish` returns `stopped` and pushes nothing

#### Scenario: A fixer that rewrites the origin of the clone
- **WHEN** a fixer sets `remote.origin.url` of the clone to another repository, with `--phase all` or with separate phases
- **THEN** `publish` fetches from and pushes to the repository on GitHub, and no git call names the other repository

#### Scenario: A clone with another origin
- **WHEN** `prepare` makes its clone
- **THEN** it clones the repository on GitHub into the run folder, and the step reads the origin of no other clone

#### Scenario: A separate publish with another origin
- **WHEN** the state file names a URL
- **THEN** `publish` raises `PhaseOutputError` and pushes nothing

#### Scenario: A check that the state file forges
- **WHEN** the state file names a check that is no failed check of the judged head
- **THEN** `publish` returns `skipped` and pushes nothing

#### Scenario: A hostile name of a check
- **WHEN** the failed check has a name with a newline, a handle and a link
- **THEN** the commit message holds the name on one line, and the comment shows the handle and the link in code spans

#### Scenario: A state file that is not the state of prepare
- **WHEN** the state file is a link to `/proc/self/environ`, holds a key outside its model or text that is not JSON, or names another pull request
- **THEN** `publish` raises `PhaseOutputError`, pushes nothing, and its message holds no text of the file

### Requirement: The agent phase holds no App key
With `--confirm`, `--phase agent` SHALL run only when `roadmap.implement.in_runner` is true and the environment holds no App private key, `GH_TOKEN` or `GITHUB_TOKEN`. It SHALL not ask for the runner check of the App.

#### Scenario: The agent phase with an App key
- **WHEN** `--phase agent` starts with the App private key or a GitHub token in its environment
- **THEN** it raises an error that names the variable and runs no step

### Requirement: Publish takes only the enums of the outcome
`publish` SHALL take the result and the tier of `outcome.json` from the enums of the step only: `repaired` with a tier, or `failed` or `stopped` with none. Each other outcome SHALL raise `PhaseOutputError` and push nothing. The reason of the agent SHALL reach the report masked and on one line.

#### Scenario: An outcome outside the enums
- **WHEN** `outcome.json` names the result `ready`, names `repaired` with no tier, or holds a key outside the model
- **THEN** `publish` raises `PhaseOutputError` and pushes nothing

### Requirement: The repair scope takes the failed files that the rebased change causes
After the rebase, a failed file outside the plan SHALL be in the repair scope when the branch changes it, when it uses a function, class or method whose definition the branch changes, when it is a test that imports a module that the branch changes, or when it is a snapshot test whose snapshot differs while the branch changes a source module.

#### Scenario: A caller of a changed function outside the plan is repaired
- **WHEN** the plan adds the keyword-only argument `in_runner` to `_run_pr_review_workflow`, and the log names `FAILED tests/git/test_review_worktree_regression.py::test_run_pr_review_workflow_partial_context - TypeError: _run_pr_review_workflow() missing 1 required keyword-only argument: 'in_runner'`, a file that the plan does not list and that calls the function
- **THEN** the step gives the file to `run_fix_step`, which may change it, and pushes the repair

#### Scenario: A log that names no file of the checkout stops
- **WHEN** the log names no failed file that the checkout tracks, such as the end of an ignore of a scanner
- **THEN** the step stops with 0 model requests, and the reason says that the log names no path of the plan and no file that the change causes
