# roadmap-implement-job/runner-job Specification

## Purpose
The runner Job of an implement item: how the Service submits it, the arguments and the token that it gets, its size and resources, its isolation, the start from a workstation, and how a round reports a Job that ended.

## Requirements

### Requirement: The job runs steps only in a runner
The job SHALL run a step only when the setting `roadmap.implement.in_runner` is true. With it false, `--confirm` SHALL run no step. It SHALL start a runner Job for the Item that `--item` names (see "A workstation starts the runner Job for one Item"), or refuse before it reads a repository, writes to git or to GitHub, or calls a model, and name the supported command. `apply_implement` SHALL raise `RoadmapImplementError` that names the setting. `--plan` and `--dry-run` SHALL run a step in no case.

#### Scenario: A workstation or the Service pod
- **WHEN** `devops roadmap implement --confirm` runs with `roadmap.implement.in_runner` false and no `--item`
- **THEN** the command exits 1, the message names `roadmap.implement.in_runner` and `devops k8s run-job --template runner`, the model is not asked, and no git command, no GitHub request and no cluster request runs

#### Scenario: The library
- **WHEN** `apply_implement` runs with `roadmap.implement.in_runner` false
- **THEN** it raises `RoadmapImplementError` that names `roadmap.implement.in_runner`, the model is not asked, and no git command and no GitHub request runs

### Requirement: The Service submits one implement Job per repository at a time
The status lane of the Service SHALL have a row `implement` after the row `metrics`, due every ten minutes and on a first run, that runs in the job clone of the lane. A round SHALL list the Jobs that carry the label of the repository, and SHALL create no Job while one of them has not ended. Else it SHALL plan the Staged and Planned items that the default filter names, and create one Job from CronJob `devops-cli-runner` for the first of them. The Service SHALL run no step itself.

#### Scenario: A Staged low-effort P1 bug
- **WHEN** the Kubernetes API is faked with CronJob `devops-cli-runner`, and a round of the row runs on a Staged Ready P1 bug of low effort
- **THEN** the API receives one Job create, and a second round with the Job still running creates no second Job

#### Scenario: A running Job of another item
- **WHEN** a Job of the repository has no Complete or Failed condition, and a second Staged item is ready
- **THEN** the round creates no Job

#### Scenario: The template is missing
- **WHEN** CronJob `devops-cli-runner` does not exist
- **THEN** the round raises an error that names the CronJob and the namespace, and creates no Job

#### Scenario: A Planned item
- **WHEN** the plan of a Ready P1 bug of low effort is on `origin/main` and its branch is gone
- **THEN** the round creates one Job with the args of that item

### Requirement: The Job gets the args of its item and a token for one repository
The Job SHALL have the args `roadmap implement --repo <repo> --item <number> --confirm` and the environment variable `DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY` set to the repository. The round SHALL record the name of the Job in `implement.job` and clear `implement.job_state` before it creates the Job.

#### Scenario: The Job is read
- **WHEN** a round created the Job for item 1 of `example/project`
- **THEN** the container args are those args, the variable holds `example/project`, and the record of item 1 holds the Job's name and no `implement.job_state`

### Requirement: A later round reports the Job that ended
A round SHALL read the Job of each item whose record holds `implement.job` and no `implement.job_state`. For a Job that ended (Complete or Failed), it SHALL comment on the item, with the marker of the implement job, the state and the last lines of the pod's log, decoded and masked of secrets, in a fenced block, and record `implement.job_state` as `succeeded` or `failed`. A Job that no longer exists SHALL be recorded as `gone`. A log that the API refuses SHALL not block the report.

#### Scenario: A Job that succeeded
- **WHEN** the Job of an item has the condition Complete and the item is In Review
- **THEN** the item gets a comment with the state `succeeded`, `implement.job_state` is `succeeded`, and the Status stays In Review

#### Scenario: A log with a check mark and several lines
- **WHEN** the log of the pod is the bytes of two lines, the first with a check mark and the second with a token
- **THEN** the comment holds a fenced block with the two lines on two lines, the check mark as the character, the token masked, and no `b'` prefix

#### Scenario: A log with a run of backticks
- **WHEN** a line of the log holds a run of three backticks
- **THEN** the fence of the block is longer than that run

#### Scenario: A log the API refuses
- **WHEN** the API refuses to read the log of the pod of a Job that failed
- **THEN** the item gets the comment without a log, `implement.job_state` is `failed`, and the next round raises no error

#### Scenario: A Job that is gone
- **WHEN** the record of an item names a Job that the API does not list
- **THEN** `implement.job_state` is `gone`

### Requirement: A Job that leaves its item eligible stops the item
When a reported Job leaves its item neither In Review nor stopped, and the record holds no `implement.result` of `ready`, `yielded` or `returned`, the round SHALL set the item Blocked and record `implement.stopped` as `job`. No Job SHALL be created for the item before a clear rule runs.

#### Scenario: A Job that failed
- **WHEN** the Job of an item has the condition Failed, the item is In Progress, the record holds no `implement.result`, and no continuation applies to it
- **THEN** the item gets a comment with the state `failed` and the tail of the log
- **AND** `implement.job_state` is `failed`, the Status is Blocked, and `implement.stopped` is `job`
- **AND** the next round creates no Job for the item

### Requirement: A runner process cannot be read by its own shell
Before the first step, the job in a runner SHALL clear the dumpable flag of its own process with `prctl(PR_SET_DUMPABLE, 0)`, so that no child reads `/proc/<pid>/environ` of the job. A call that the kernel refuses SHALL make `apply_implement` raise `RoadmapImplementError`, and no step SHALL run. The step of the agent SHALL get none of the variables of the job, except `UV_CACHE_DIR`, `UV_PYTHON` and `PYTEST_XDIST_AUTO_NUM_WORKERS`.

#### Scenario: A child reads the environment of its parent
- **WHEN** a process sets the flag, holds a variable in its starting environment, and starts a child that opens `/proc/<parent pid>/environ`
- **THEN** the child gets `PermissionError`

#### Scenario: The refusal
- **WHEN** `prctl` returns -1 and `apply_implement` runs a plan
- **THEN** `apply_implement` raises `RoadmapImplementError` that names `PR_SET_DUMPABLE`, and no step, no model request and no program runs

### Requirement: The job runs no step without a token for its repository
Before any step, `devops roadmap implement --confirm` and `apply_implement` SHALL raise `RoadmapImplementError` unless the process acts as the GitHub App and `service.github_app.token_repository` equals the repository of the plan. The message SHALL name the setting. A Job made by `devops k8s run-job` SHALL get that setting from `--repo`, and `run-job` SHALL refuse the runner template without `--repo`.

#### Scenario: A token for every repository
- **WHEN** `service.github_app.token_repository` is empty or names another repository
- **THEN** `apply_implement` raises `RoadmapImplementError` that names the setting, the model is not asked, and no git command and no GitHub request runs

#### Scenario: A process that is not the App
- **WHEN** the process does not hold the private key of the GitHub App
- **THEN** `apply_implement` raises `RoadmapImplementError` before any step

#### Scenario: run-job
- **WHEN** `devops k8s run-job --template runner -- roadmap implement --item 7` runs with no `--repo`
- **THEN** the command exits 1, names `--repo`, and sends no request

### Requirement: No process of a step lives when the job runs git or gh
A `git` or `gh` child of the job holds the session token in its environment, which a process of the same user can read, and a pod cannot hide it (see design.md). So the job SHALL adopt orphans (`PR_SET_CHILD_SUBREAPER`) and, when a step ends, kill every descendant, also one in a session of its own, before it runs any program. A descendant that survives SHALL raise `RoadmapImplementError` and stop the item.

#### Scenario: A daemon of the shell
- **WHEN** a step leaves a process in a session of its own and the step ends
- **THEN** the process is dead before the first `git` of the job runs after the step

#### Scenario: A process that does not die
- **WHEN** a descendant is still alive after the timeout
- **THEN** `RoadmapImplementError` names it

### Requirement: The Job is recorded before it is created
The round SHALL record the name of the Job in `implement.job` and the digest of the runner image in the template of CronJob `devops-cli-runner` in `implement.job_digest`, and clear `implement.job_state`, before it creates the Job. The round SHALL read the CronJob one time for each create, and take the digest and the Job from that read. A create that fails SHALL remove the record of the Job. So a Job that no record names does not exist, and an item whose Job dies early is reported and stopped.

#### Scenario: The order
- **WHEN** a round creates the Job for item 1
- **THEN** the record of item 1 holds the name and the digest when the API receives the create

#### Scenario: A refused create
- **WHEN** the API refuses the create
- **THEN** the round raises `ClusterJobError` and the record of the item holds no Job

### Requirement: A model-lane round that has not ended does not delay the implement row
The row `implement` SHALL NOT be a row of the model lane. A poll SHALL make it due on the status lane by its interval, whether or not a round of the model lane of the same repository is running. A suspended `implement` row in the ledger of failed rounds SHALL stay suspended on the status lane until the hour ends, and a ledger record that holds an entry of the row SHALL load.

#### Scenario: The model lane is in a long refine round
- **WHEN** the model lane runs a refine round that has not ended, and a poll reaches both lanes of the repository
- **THEN** the status lane runs `metrics` and `implement` while the refine round is still running

#### Scenario: The rows of each lane
- **WHEN** the due table is read
- **THEN** the status lane holds `metrics`, `implement`, `stage_ready`, `release_comments`, `github_status`, `cloudflare_status` and `pr_conflicts` in this order, the triage lane holds `intake`, and the model lane holds `refine`, `retitle`, `stage` and `alternatives`

#### Scenario: A suspended row keeps its suspension
- **WHEN** the record of failed rounds holds an entry of the row `implement` at the limit of rounds, and the status lane runs a round on the same input
- **THEN** the record loads, the row does not run, and the gauge `devops_cli_service_job_suspended` for the row is 1

#### Scenario: A suspended row runs again in a later hour
- **WHEN** the row `implement` failed its limit of rounds in a row, its fault is fixed, and a poll round of a later hour runs on the status lane
- **THEN** the row runs, with no webhook

### Requirement: A workstation starts the runner Job for one Item
`devops roadmap implement --item <n> --confirm` with `roadmap.implement.in_runner` false SHALL start the runner Job through the code of `devops k8s run-job --template runner`, with the args `roadmap implement --repo <repo> --item <n> --confirm`. The repository SHALL be `--repo` or the origin of the checkout. The command SHALL follow the log and exit with the exit code of the container, or with `--no-wait` print the name of the Job.

#### Scenario: A Ready Item
- **WHEN** the command runs for a Ready Item of `example/project` with the cluster faked
- **THEN** one Job is created from CronJob `devops-cli-runner` with the args `roadmap implement --repo example/project --item 7 --confirm` and the token repository `example/project`, and the exit code of the container is the exit code of the command

#### Scenario: No wait
- **WHEN** the command runs with `--no-wait`
- **THEN** the Job is created, its name is printed, and the log is not followed

### Requirement: A start from a workstation is refused when it cannot succeed
Before it creates the Job, the command SHALL refuse an Item that an agent or a person claimed, an Item whose Status is neither Ready nor Planned, a closed issue or an issue that is no Item, a repository that is not `owner/name`, and a repository that has a runner Job that has not ended. With `--confirm` it SHALL also refuse `--source`, `--filter`, `--limit` and a missing `--item`, and name the `run-job` command.

#### Scenario: A claimed Item
- **WHEN** the Item holds `owner/human` or `owner/agent`
- **THEN** the command exits 1, names the owner, and creates no Job

#### Scenario: An Item that is not ready to implement
- **WHEN** the Item is New, In Progress, In Review or Blocked, or the issue is closed or is no Item of the roadmap
- **THEN** the command exits 1, names the Status or the cause, and creates no Job

#### Scenario: A running Job
- **WHEN** a Job of the repository carries the label `implement-repo` and has no Complete or Failed condition
- **THEN** the command exits 1, names the Job, and creates no Job

#### Scenario: An option that needs the runner
- **WHEN** the command runs with `--confirm` and `--source`, `--filter` or `--limit`
- **THEN** the command exits 1, names the option and the `run-job` command, and sends no request

#### Scenario: A repository that is no owner and name
- **WHEN** `--repo` is `../..`, `owner/..` or has no slash
- **THEN** the command exits non-zero, reads no Item, and creates no Job

#### Scenario: A step with confirm
- **WHEN** the command runs with `--group` and `--confirm`
- **THEN** the command exits 1, and the message names `devops roadmap implement --item <n> --confirm`

### Requirement: A dry run of the start prints the Job
`devops roadmap implement --item <n> --dry-run` with `roadmap.implement.in_runner` false SHALL make no request and SHALL print the requests of the start, the read of the Item and the Job included. It SHALL ignore `--source`, `--filter` and `--limit`.

#### Scenario: A dry run
- **WHEN** the command runs with `--item 7 --dry-run`
- **THEN** no process starts, no GitHub request is made, and the output names CronJob `devops-cli-runner`, the args of the Job and the read of the Item

#### Scenario: A dry run with an option that needs the runner
- **WHEN** the command runs with `--item 7 --dry-run --limit 2`
- **THEN** the output is the same plan and the command exits 0

### Requirement: The report of a Job names its image digest
The comment that reports a Job that ended SHALL name `implement.job_digest` when the record holds it.

#### Scenario: A Job that failed
- **WHEN** the round reports a Job whose record holds a digest
- **THEN** the comment names that digest

### Requirement: The memory limit of a runner Job stays 8 Gi
The runner Job that the Service creates SHALL have the memory limit of the setting `roadmap.implement.max_memory_limit`, whose default is 8Gi, whatever the deadline settings and the size of the plan are.

#### Scenario: The memory limit
- **WHEN** a round creates a Job and the setting is not set
- **THEN** the memory limit of its container is 8Gi

#### Scenario: A raised limit
- **WHEN** the setting is 12Gi and a round creates a Job
- **THEN** the memory limit of its container is 12Gi

### Requirement: The job runs a project step only where the target declares it
The job SHALL run the docs step and the archive step only when the default branch of the target repository declares the step in `.devops/roadmap.toml` under `[implement.steps]`. The job SHALL read the file from the default branch and SHALL NOT read the checkout. A default branch with no file SHALL declare no step. A file that is not valid SHALL stop the item and run no step.

#### Scenario: A target with no declaration skips the docs step
- **WHEN** the default branch of the target holds no `.devops/roadmap.toml` and the job reaches `_finish_change` or `_scoped_rounds`
- **THEN** the job runs no docs command and the job ends with a pull request

#### Scenario: A target with no declaration skips the archive step
- **WHEN** the default branch of the target holds no `.devops/roadmap.toml` and the job reaches `_finish_change`
- **THEN** the job archives no change folder and does not fail, and the pull request is ready with the change not archived

#### Scenario: An agent edit of the declaration changes no step
- **WHEN** an agent adds or removes the declaration in the checkout and the default branch is unchanged
- **THEN** the job runs the steps that the default branch declares and no other

#### Scenario: A target that declares the steps runs them
- **WHEN** the default branch declares `docs = true` and `archive = true`
- **THEN** the job runs the docs command and archives the change folder

#### Scenario: A declaration that is not valid
- **WHEN** the file on the default branch names a step that does not exist
- **THEN** the job stops the item with the path of the file in the reason and runs no step

### Requirement: The comment of the job names each skipped step
The comment of the job on the pull request SHALL name each step that the job skipped and the file that did not declare it.

#### Scenario: Steps skipped
- **WHEN** the job skips the docs step and the archive step
- **THEN** the comment lists `step docs` and `step archive` as skipped

#### Scenario: Steps run
- **WHEN** the job runs both steps
- **THEN** the comment names no skipped step

### Requirement: The Service sizes the runner Job from the plan
The Service SHALL choose the CPU request, the CPU limit and the memory request of a runner Job from the table `RUNNER_SIZES` by the number of files that the plan names: the small row (CPU 1, memory 2Gi) for at most 10 files, and the large row (CPU 4, memory 6Gi) for more. The other values of the template SHALL stay.

#### Scenario: A plan with few files and a plan with many
- **WHEN** a round creates a Job for a plan whose tasks name 3 files, and another round creates a Job for a plan whose tasks name 12 files
- **THEN** the first Job requests 1 CPU and 2Gi, the second requests 4 CPU and 6Gi, and each keeps the `ephemeral-storage` of the template

### Requirement: The files of a plan are the paths in its tasks
The Service SHALL count the distinct file paths in the code spans of `tasks.md`, read at the revision that holds the plan: `origin/<default branch>` for a Planned item and `origin/<branch>` for a Staged item. A change that is archived at that revision SHALL count zero files.

#### Scenario: Paths are counted once
- **WHEN** the tasks name the same file in several tasks, and name commands and settings in code spans
- **THEN** the count holds each file path once and holds no command and no setting

#### Scenario: A Planned item
- **WHEN** the plan of a Planned item is on the default branch and names 11 files
- **THEN** the Job of the item has the large row

### Requirement: The worker count of a runner Job equals its CPU limit
The Service SHALL set `PYTEST_XDIST_AUTO_NUM_WORKERS` of the Job to the CPU limit of the same Job, and the CPU request SHALL equal the CPU limit.

#### Scenario: Every row
- **WHEN** a test reads each row of the table and the Job that the Service creates for it
- **THEN** the CPU request, the CPU limit and the value of `PYTEST_XDIST_AUTO_NUM_WORKERS` are equal

### Requirement: The size table cites its measurements
Each row of `RUNNER_SIZES` SHALL name the measured Job sample and its peak memory, and the memory request of the row SHALL be above that peak.

#### Scenario: The rows
- **WHEN** a test reads the table
- **THEN** each row has a sample name and a peak, and its memory request is above the peak

### Requirement: The memory limit is a setting that holds the largest request
The setting `roadmap.implement.max_memory_limit` SHALL have the default 8Gi and the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_MEMORY_LIMIT`. It SHALL be a whole number of Gi, and the configuration SHALL refuse a value below the largest memory request of the table.

#### Scenario: The default
- **WHEN** the configuration is loaded with no value
- **THEN** the setting is 8Gi

#### Scenario: A value below the largest request or in another form
- **WHEN** the setting is 5Gi, 8G or 8192Mi
- **THEN** the configuration is refused

### Requirement: The Service clears the result when it records a Job
The Service SHALL clear `implement.result` in the write that records a new Job of an item.

#### Scenario: A Job that dies before its first write
- **WHEN** the record of an item holds `implement.result` equal to `yielded` and a round creates a Job for the item
- **THEN** the record holds `implement.job` and no `implement.result`

### Requirement: The report reads the result of a Job
The round SHALL read `implement.result` when it reports a Job that ended. A Job with the result `ready`, `yielded` or `returned` SHALL cause no stop of the item. A Job with no result SHALL get its stop and its class from the Status of the item and the tail of its log, with `classify_failure`.

#### Scenario: A yielded Job
- **WHEN** the Job of an item ended, the item is In Progress, and the record holds `implement.result` equal to `yielded`
- **THEN** the round records `implement.job_state`, sets no Status, and records no `implement.stopped`

#### Scenario: A Job with no result
- **WHEN** the Job of an item failed, the item is In Progress, the record holds no result, and the log holds an out-of-memory line
- **THEN** the round records the class `oom` and sets the item Blocked

### Requirement: A round reports the Job of a closed item that the cluster holds
A round SHALL report the Job of a closed item whose record holds `implement.job` and no `implement.job_state` while the cluster lists that Job, and SHALL NOT stop a closed item. A round SHALL NOT report the Job of a closed item that the cluster no longer lists.

#### Scenario: The pull request merged before the report
- **WHEN** the item of a Job closes and the Job then ends Complete
- **THEN** the next round reports the Job once, `implement.job_state` is `succeeded`, `implement.stopped` is not set, and the series with `result` `succeeded` increases by one

#### Scenario: A closed item whose Job is gone
- **WHEN** a closed item records a Job that the cluster does not list
- **THEN** the round records no state and no counter changes
