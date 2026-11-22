## MODIFIED Requirements

### Requirement: A workstation starts the runner Job for one Item
`devops roadmap implement --item <n> --confirm` with `roadmap.implement.in_runner` false SHALL start the runner Job through the code of `devops k8s run-job --template runner`, with the args `roadmap implement --repo <repo> --item <n> --confirm`. The repository SHALL be `--repo` or the origin of the checkout. The command SHALL follow the log and exit with the exit code of the container, or with `--no-wait` print the name of the Job.

#### Scenario: A Ready Item
- **WHEN** the command runs for a Ready Item of `example/project` with the cluster faked
- **THEN** one Job is created from CronJob `devops-cli-runner` with the args `roadmap implement --repo example/project --item 7 --confirm` and the token repository `example/project`, and the first exit code that is not 0 of its containers is the exit code of the command

#### Scenario: No wait
- **WHEN** the command runs with `--no-wait`
- **THEN** the Job is created, its name is printed, and the log is not followed

### Requirement: The memory limit of a runner Job stays 8 Gi
The container `agent` of the runner Job that the Service creates SHALL have the memory limit of the setting `roadmap.implement.max_memory_limit`, whose default is 8Gi, whatever the deadline settings and the size of the plan are. `prepare` and `publish` SHALL keep their own limit of the template.

#### Scenario: The memory limit
- **WHEN** a round creates a Job and the setting is not set
- **THEN** the memory limit of its container `agent` is 8Gi

#### Scenario: A raised limit
- **WHEN** the setting is 12Gi and a round creates a Job
- **THEN** the memory limit of its container `agent` is 12Gi
