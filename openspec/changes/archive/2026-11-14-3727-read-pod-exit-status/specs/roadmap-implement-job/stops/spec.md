## ADDED Requirements

### Requirement: The report reads the exit status of the pod before it classifies a failure
The report of an ended Job SHALL read the terminated exit status of the container of the Job's pod, from `state` and then from `lastState`, and SHALL pass it to `classify_failure`. A stall SHALL keep the exit status 143. A pod with no terminated state SHALL leave the class to the log.

#### Scenario: A killed container with an empty log
- **WHEN** the pod of the Job holds a terminated container with exit status 137 and the log is empty
- **THEN** the class is `oom`, the item stops as `job`, and the Service makes no continuation Job

#### Scenario: A restarted container whose last state terminated
- **WHEN** the state of the container holds no terminated state and its last state holds exit status 137
- **THEN** the class is `oom`

#### Scenario: A pod with no terminated state
- **WHEN** the pod status holds no terminated state and the log holds the text of another failure
- **THEN** the class comes from the log
