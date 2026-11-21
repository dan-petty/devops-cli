## ADDED Requirements

### Requirement: The Job builder sets each container of the phases
When the pod template holds the init containers `prepare` and `agent` and the container `publish`, `build_job` SHALL give each container the args with its own `--phase` and `--work /run/roadmap`, and the same environment. Only `agent` SHALL get the resources of the unit. A template with one container SHALL keep the args, the environment and the resources on its container.

#### Scenario: A template on the phases
- **WHEN** `build_job` builds a runner Job with a `TRACEPARENT` and a memory limit of `4Gi` from a template on the phases
- **THEN** each container runs the args with its `--phase`, all three get the same `TRACEPARENT`, and only `agent` gets the limit `4Gi`

#### Scenario: The template with one container
- **WHEN** `build_job` builds the same Job from the template with the container `runner`
- **THEN** `runner` gets the args with no `--phase`, the `TRACEPARENT` and the limit `4Gi`

### Requirement: The Service reads each runner container by name
`log_tail` SHALL read the container that the reader names, else the container that runs, else the container that ended the pod, and SHALL read a pod with one container whatever the name. `pod_end` SHALL read the init containers first and SHALL give the first container that failed, else the last one that ended. The fix-checks row SHALL read the result line from `publish`, then from `prepare`.

#### Scenario: The deadline reads the agent
- **WHEN** `prepare` ended, `agent` runs and its log changed
- **THEN** the Service extends the deadline from the log of `agent`

#### Scenario: An OOM kill of the agent
- **WHEN** `agent` ended with exit status 137 and the reason `OOMKilled`, and `publish` waits
- **THEN** the report of the Job records the failure class `oom`

### Requirement: run-job follows each container of the phases in turn
For a Job on the phases, `devops k8s run-job` SHALL follow `prepare`, `agent` and `publish` in turn, SHALL read the exit code of each by its name, and SHALL end with the first exit code that is not 0.

#### Scenario: The agent fails
- **WHEN** `prepare` exits with 0 and `agent` exits with 137
- **THEN** run-job follows `prepare` and `agent`, follows no more containers, and exits with 137

#### Scenario: A dry run of the runner template
- **WHEN** run-job prints the dry run of the runner template, which reads no CronJob
- **THEN** it lists the reads of one container under the condition that the CronJob holds one container, and the reads of each phase container under the condition that the CronJob holds the init containers `prepare` and `agent`
