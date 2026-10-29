# Spec Delta

## ADDED Requirements

### Requirement: The Service submits one implement Job per repository at a time
The model lane of the Service SHALL have a row `implement`, due every ten minutes and on a first run, that runs in the job clone. A round SHALL list the Jobs that carry the label of the repository, and SHALL create no Job while one of them has not ended. Else it SHALL plan the Staged items that the default filter names, and create one Job from CronJob `devops-cli-runner` for the first of them. The Service SHALL run no step itself.

#### Scenario: A Staged low-effort P1 bug
- **WHEN** the Kubernetes API is faked with CronJob `devops-cli-runner`, and a round of the row runs on a Staged Ready P1 bug of low effort
- **THEN** the API receives one Job create, and a second round with the Job still running creates no second Job

#### Scenario: A running Job of another item
- **WHEN** a Job of the repository has no Complete or Failed condition, and a second Staged item is ready
- **THEN** the round creates no Job

#### Scenario: The template is missing
- **WHEN** CronJob `devops-cli-runner` does not exist
- **THEN** the round raises an error that names the CronJob and the namespace, and creates no Job

### Requirement: The Job gets the args of its item and a token for one repository
The Job SHALL have the args `roadmap implement --repo <repo> --item <number> --confirm` and the environment variable `DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY` set to the repository. The round SHALL record the name of the Job in `implement.job` and clear `implement.job_state` before it creates the Job.

#### Scenario: The Job is read
- **WHEN** a round created the Job for item 1 of `example/project`
- **THEN** the container args are those args, the variable holds `example/project`, and the record of item 1 holds the Job's name and no `implement.job_state`

### Requirement: A later round reports the Job that ended
A round SHALL read the Job of each item whose record holds `implement.job` and no `implement.job_state`. For a Job that ended (Complete or Failed), it SHALL comment on the item, with the marker of the implement job, the state and the last lines of the pod's log, masked of secrets, and record `implement.job_state` as `succeeded` or `failed`. A Job that no longer exists SHALL be recorded as `gone`. A log that the API refuses SHALL not block the report.

#### Scenario: A Job that succeeded
- **WHEN** the Job of an item has the condition Complete and the item is In Review
- **THEN** the item gets a comment with the state `succeeded`, `implement.job_state` is `succeeded`, and the Status stays In Review

#### Scenario: A log the API refuses
- **WHEN** the API refuses to read the log of the pod of a Job that failed
- **THEN** the item gets the comment without a log, `implement.job_state` is `failed`, and the next round raises no error

#### Scenario: A Job that is gone
- **WHEN** the record of an item names a Job that the API does not list
- **THEN** `implement.job_state` is `gone`

### Requirement: A Job that leaves its item eligible stops the item
When a reported Job leaves its item neither In Review nor stopped, the round SHALL set the Status of the item to Ready and record `implement.stopped` as `job`, so that no Job is created for the item before a person comments `implement: retry`.

#### Scenario: A Job that failed
- **WHEN** the Job of an item has the condition Failed and the item is In Progress
- **THEN** the item gets a comment with the state `failed` and the tail of the log, `implement.job_state` is `failed`, the Status is Ready, `implement.stopped` is `job`, and the next round creates no Job for the item

### Requirement: A runner process cannot be read by its own shell
Before the first step, the job in a runner SHALL clear the dumpable flag of its own process with `prctl(PR_SET_DUMPABLE, 0)`. A child of the job SHALL then not read `/proc/<pid>/environ` of the job. A call that the kernel refuses SHALL make `apply_implement` raise `RoadmapImplementError`, and no step SHALL run. The step of the agent SHALL get none of the variables of the job, except the paths `UV_CACHE_DIR` and `UV_PYTHON` of uv.

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
The round SHALL record the name of the Job in `implement.job` and clear `implement.job_state` before it creates the Job. A create that fails SHALL remove the record. So a Job that no record names does not exist, and an item whose Job dies early is reported and stopped.

#### Scenario: The order
- **WHEN** a round creates the Job for item 1
- **THEN** the record of item 1 holds the name when the API receives the create

#### Scenario: A refused create
- **WHEN** the API refuses the create
- **THEN** the round raises `ClusterJobError` and the record of the item holds no Job
