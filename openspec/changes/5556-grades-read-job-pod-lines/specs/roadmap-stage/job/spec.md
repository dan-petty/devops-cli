## MODIFIED Requirements

### Requirement: The grades and the counter read the stage Jobs
The job grade report and the panels of the job grades SHALL read the result lines of the Service, of the stage Job pods and of the fix-plan Job pods, and no runner pod. The Service SHALL count each stage Job in `devops_cli_service_stage_jobs_total` by `repo`, `result` and `class`.

#### Scenario: The selector of the grades
- **WHEN** the report plans its queries
- **THEN** each query selects the containers `service`, `stage` and `fix-plan` of the namespace `devops`

## ADDED Requirements

### Requirement: The stage Job writes one result line for its attempt after its check-in
`devops roadmap stage --job-item` SHALL write the result line of its attempt as plain text to stderr. The Job SHALL write the line after its check-in, and only when the check-in found the check-out of the Job, or when the pod has no Job name. When the check-in finds no check-out of the Job, or fails, the Job SHALL write no result line.

#### Scenario: A normal end
- **WHEN** the Job stages its item and the check-out names the Job
- **THEN** stderr holds one line `roadmap job result: job=stage` with `result=staged`, written after the check-in

#### Scenario: The Service ended the attempt
- **WHEN** the check-out names another Job at the end of the Job
- **THEN** the Job writes no result line

#### Scenario: The check-in fails
- **WHEN** the write of the check-in fails
- **THEN** the Job writes no result line, and the recovery of the Service writes the line of the `failed` end
