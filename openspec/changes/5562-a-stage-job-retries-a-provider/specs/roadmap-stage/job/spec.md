## MODIFIED Requirements

### Requirement: The stage Job ends with the exit code of its end and checks in
The entry point SHALL exit 0 for a result, 1 for a failure whose class a retry cannot help or for a refused provider key, 75 for a failure whose class a retry can help or for a SIGTERM before the time budget ends, and 143 for a SIGTERM after it or a budget that ends before a model call. Except for an end that exits 75, it SHALL write `stage.job_result`, clear the check-out and release the claim `owner/service` in one write, only when `stage.job` names the Job of the pod.

#### Scenario: A normal end
- **WHEN** The Job stages its item and the check-out names the Job.
- **THEN** It exits 0, the record holds `stage.job_result` with the result `staged`, and the check-out is clear.

#### Scenario: The check-out of another Job
- **WHEN** The check-out names another Job.
- **THEN** The Job writes no `stage.job_result` and the check-out stays.

#### Scenario: An eviction
- **WHEN** SIGTERM comes before the time budget ends.
- **THEN** The command exits 75 and the check-out stays.

#### Scenario: A kill after a GitHub write
- **WHEN** The Job is killed after the push, after the draft or after the record write, and its pod runs again.
- **THEN** The item ends with one open draft, the full stage record, no intent mark and the check-in of the Job.

#### Scenario: The provider timeout of an attempt
- **WHEN** The model call of the item fails with an `AIClientError` whose HTTP status is 504, and the check-out names the Job of the pod.
- **THEN** The command exits 75, the record keeps `stage.job` with the name of the Job and holds no `stage.job_result`, and the claim `owner/service` stays.

#### Scenario: A plan defect
- **WHEN** The plan of the item ends with the class `plan_defect`.
- **THEN** The command exits 1, the record holds `stage.job_result` with the result `failed`, and the check-out is clear.

#### Scenario: A refused key of the provider
- **WHEN** The model call fails with an error that says the provider refused the key, and the check-out names the Job of the pod.
- **THEN** The command exits 1 and the check-out stays.

### Requirement: The stage Job writes one result line for its attempt after its check-in
`devops roadmap stage --job-item` SHALL write the result line of its attempt as plain text to stderr. The Job SHALL write the line after its check-in, when the check-in found the check-out of the Job or no check-out named the Job at its start. An attempt that exits 75 SHALL write its line, when the check-out still names the Job or named none at its start. When the check-in of a Job that the check-out named at its start finds no check-out or fails, the Job SHALL write no result line.

#### Scenario: A normal end
- **WHEN** The Job stages its item and the check-out names the Job.
- **THEN** stderr holds one line `roadmap job result: job=stage` with `result=staged`, written after the check-in.

#### Scenario: The Service ended the attempt
- **WHEN** The check-out names another Job at the end of the Job.
- **THEN** The Job writes no result line.

#### Scenario: A Job that a person starts
- **WHEN** No check-out names the Job at its start, and the Job stages its item or reaches its deadline.
- **THEN** The Job writes one result line for its attempt.

#### Scenario: The check-in fails
- **WHEN** The write of the check-in fails.
- **THEN** The Job writes no result line, and the check-out stays, so the recovery of the Service checks in for the `failed` end and writes its line.

#### Scenario: The provider timeout of an attempt
- **WHEN** The model call of the item fails with an `AIClientError` whose HTTP status is 504, and the check-out names the Job of the pod.
- **THEN** stderr holds one line with `result=failed`, `class=provider` and `infra=true`, and the Job writes no check-in.
