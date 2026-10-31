# Spec Delta

## MODIFIED Requirements

### Requirement: run-job creates a Job from the runner template
`devops k8s run-job --template runner --repo owner/name -- ARGS` SHALL create a Job from CronJob `devops-cli-runner`, changing only the args of container `runner`, the name, the labels and the variable `DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY`, which `--repo` sets. `--template default` SHALL be the default and use CronJob `devops-cli`. The name SHALL start with the name of its CronJob. `--dry-run` SHALL make no request and name the CronJob.

#### Scenario: A Job from the runner template
- **WHEN** the Job builder gets CronJob `devops-cli-runner` with the args `roadmap implement --item 7 --confirm`
- **THEN** the Job has a name that starts with `devops-cli-runner-`, the container `runner` has those args, every other field of the pod template equals the CronJob's, and the Job and its pod carry the label `app.kubernetes.io/name=devops-cli-job`

#### Scenario: A repository that does not fit the template
- **WHEN** `run-job` gets the runner template with no `--repo`, or `--repo` with the default template
- **THEN** the command exits 1, names the option, and sends no request

#### Scenario: A dry run
- **WHEN** `devops k8s run-job --template runner --repo example/project --dry-run -- roadmap implement --item 7` runs
- **THEN** no process starts, and the plan names CronJob `devops-cli-runner`, the token repository and the lookup of the running Jobs

## ADDED Requirements

### Requirement: A runner Job carries the label of its repository and is the only one
The Job and its pod of `run-job --template runner` SHALL carry the label `implement-repo` with the digest of `--repo`, the label that the Service lists its Jobs by. `run-job` SHALL create no Job while a Job with that label has not ended, whoever made it.

#### Scenario: The label of the repository
- **WHEN** `run-job --template runner --repo example/project` creates a Job
- **THEN** the Job and its pod carry `implement-repo` with the label value that the Service computes for `example/project`

#### Scenario: A running Job of the repository
- **WHEN** `run-job --template runner --repo example/project` runs and a Job with that label has no Complete or Failed condition
- **THEN** the command exits 1, names the running Job, and creates no Job
