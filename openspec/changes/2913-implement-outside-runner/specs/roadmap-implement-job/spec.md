# Spec Delta

## MODIFIED Requirements

### Requirement: The job runs steps only in a runner
The job SHALL run a step only when the setting `roadmap.implement.in_runner` is true. With it false, `--confirm` SHALL run no step. It SHALL start a runner Job for the Item that `--item` names (see "A workstation starts the runner Job for one Item"), or refuse before it reads a repository, writes to git or to GitHub, or calls a model, and name the supported command. `apply_implement` SHALL raise `RoadmapImplementError` that names the setting. `--plan` and `--dry-run` SHALL run a step in no case.

#### Scenario: A workstation or the Service pod
- **WHEN** `devops roadmap implement --confirm` runs with `roadmap.implement.in_runner` false and no `--item`
- **THEN** the command exits 1, the message names `roadmap.implement.in_runner` and `devops k8s run-job --template runner`, the model is not asked, and no git command, no GitHub request and no cluster request runs

#### Scenario: The library
- **WHEN** `apply_implement` runs with `roadmap.implement.in_runner` false
- **THEN** it raises `RoadmapImplementError` that names `roadmap.implement.in_runner`, the model is not asked, and no git command and no GitHub request runs

## ADDED Requirements

### Requirement: A workstation starts the runner Job for one Item
`devops roadmap implement --item <n> --confirm` with `roadmap.implement.in_runner` false SHALL start the runner Job through the code of `devops k8s run-job --template runner`, with the args `roadmap implement --repo <repo> --item <n> --confirm`. The repository SHALL be `--repo` or the origin of the checkout. The command SHALL follow the log and exit with the exit code of the container, or with `--no-wait` print the name of the Job.

#### Scenario: A Ready Item
- **WHEN** the command runs for a Ready Item of `example/project` with the cluster faked
- **THEN** one Job is created from CronJob `devops-cli-runner` with the args `roadmap implement --repo example/project --item 7 --confirm` and the token repository `example/project`, and the exit code of the container is the exit code of the command

#### Scenario: No wait
- **WHEN** the command runs with `--no-wait`
- **THEN** the Job is created, its name is printed, and the log is not followed

### Requirement: A start from a workstation is refused when it cannot succeed
Before it creates the Job, the command SHALL refuse an Item that an agent or a person claimed, an Item whose Status is neither Ready nor Planned, and a repository that has a runner Job that has not ended. It SHALL refuse `--source`, `--filter` and `--limit`, and a missing `--item`, and the refusal SHALL name the `run-job` command. The refusal of `--group` with `--confirm` SHALL name the command that starts the Job.

#### Scenario: A claimed Item
- **WHEN** the Item holds `owner/human` or `owner/agent`
- **THEN** the command exits 1, names the owner, and creates no Job

#### Scenario: An Item that is not ready to implement
- **WHEN** the Item is In Progress, In Review, Done or New
- **THEN** the command exits 1, names the Status, and creates no Job

#### Scenario: A running Job
- **WHEN** a Job of the repository carries the label `implement-repo` and has no Complete or Failed condition
- **THEN** the command exits 1, names the Job, and creates no Job

#### Scenario: An option that needs the runner
- **WHEN** the command runs with `--confirm` and `--source`, `--filter` or `--limit`
- **THEN** the command exits 1, names the option and the `run-job` command, and sends no request

#### Scenario: A step with confirm
- **WHEN** the command runs with `--group` and `--confirm`
- **THEN** the command exits 1, and the message names `devops roadmap implement --item <n> --confirm`

### Requirement: A dry run of the start prints the Job
`devops roadmap implement --item <n> --dry-run` with `roadmap.implement.in_runner` false SHALL make no request and SHALL print the requests of the start, the read of the Item and the Job included.

#### Scenario: A dry run
- **WHEN** the command runs with `--item 7 --dry-run`
- **THEN** no process starts, no GitHub request is made, and the output names CronJob `devops-cli-runner`, the args of the Job and the read of the Item
