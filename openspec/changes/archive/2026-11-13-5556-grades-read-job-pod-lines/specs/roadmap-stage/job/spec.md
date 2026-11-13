## MODIFIED Requirements

### Requirement: The grades and the counter read the stage Jobs
The job grade report and the panels of the job grades SHALL read the result lines of the Service, of the stage Job pods and of the fix-plan Job pods, and no runner pod. The Service SHALL count each stage Job in `devops_cli_service_stage_jobs_total` by `repo`, `result` and `class`.

#### Scenario: The selector of the grades
- **WHEN** the report plans its queries
- **THEN** each query selects the containers `service`, `stage` and `fix-plan` of the namespace `devops`

## ADDED Requirements

### Requirement: The stage Job writes one result line for its attempt after its check-in
`devops roadmap stage --job-item` SHALL write the result line of its attempt as plain text to stderr. The Job SHALL write the line after its check-in, and only when the check-in found the check-out of the Job, or when no check-out named the Job at its start. When the check-in of a Job that the check-out named at its start finds no check-out of the Job, or fails, the Job SHALL write no result line.

#### Scenario: A normal end
- **WHEN** the Job stages its item and the check-out names the Job
- **THEN** stderr holds one line `roadmap job result: job=stage` with `result=staged`, written after the check-in

#### Scenario: The Service ended the attempt
- **WHEN** the check-out names another Job at the end of the Job
- **THEN** the Job writes no result line

#### Scenario: A Job that a person starts
- **WHEN** no check-out names the Job at its start, and the Job stages its item or reaches its deadline
- **THEN** the Job writes one result line for its attempt

#### Scenario: The check-in fails
- **WHEN** the write of the check-in fails
- **THEN** the Job writes no result line, and the check-out stays, so the recovery of the Service checks in for the `failed` end and writes its line

### Requirement: The stage Job counts its item before its check-in
The stage Job SHALL count its item in `devops_cli_roadmap_stage_total` before its check-in, as a round does, also when it writes no result line.

#### Scenario: The Service ended the attempt
- **WHEN** the check-out names another Job at the end of the Job
- **THEN** `devops_cli_roadmap_stage_total` counts the item of the Job once
