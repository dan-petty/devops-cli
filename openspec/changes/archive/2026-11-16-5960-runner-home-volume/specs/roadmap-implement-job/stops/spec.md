## MODIFIED Requirements

### Requirement: The report reads the exit status of the pod before it classifies a failure
The report of an ended Job SHALL read the terminated exit status of the container of the Job's pod and the reason of that termination, from `state` and then from `lastState`, and SHALL pass them to `classify_failure`. A stall SHALL keep the exit status 143. A pod with no terminated state SHALL leave the class to the log. The exit status 137 SHALL give `oom` only when the reason of the container is `OOMKilled` or when the status has no container reason.

#### Scenario: A killed container with an empty log
- **WHEN** the pod of the Job holds a terminated container with exit status 137 and the reason `OOMKilled`, and the log is empty
- **THEN** the class is `oom`, the item stops as `job`, and the Service makes no continuation Job

#### Scenario: A restarted container whose last state terminated
- **WHEN** the state of the container holds no terminated state and its last state holds exit status 137 and the reason `OOMKilled`
- **THEN** the class is `oom`

#### Scenario: A pod with no terminated state
- **WHEN** the pod status holds no terminated state and the log holds the text of another failure
- **THEN** the class comes from the log

#### Scenario: A container killed with no reason of memory
- **WHEN** the pod has no reason, and its container terminated with exit status 137 and the reason `Error`
- **THEN** the class is not `oom`, and it comes from the log

## ADDED Requirements

### Requirement: The report gives an evicted pod the class of its cause
The report of an ended Job SHALL read the reason and the message of the Job's pod and SHALL pass them to `classify_failure`. A pod with the reason `Evicted` whose message names a volume, a container or a pod over its own storage limit SHALL give `limit_reached`, and the report SHALL quote the message. A pod with the reason `Evicted` for a node low on a resource SHALL give `ci_infra`.

#### Scenario: A pod evicted for its home volume
- **WHEN** the pod has the reason `Evicted` and the message `Usage of EmptyDir volume "home" exceeds the limit "4Gi".`, its container terminated with exit status 137 and the reason `Error`, and the log is empty
- **THEN** the class is `limit_reached`, the item stops as `job`, the Service makes no continuation Job, and the report holds the message

#### Scenario: A pod evicted for a node low on a resource
- **WHEN** the pod has the reason `Evicted` and the message `The node was low on resource: ephemeral-storage.`
- **THEN** the class is `ci_infra`
