## MODIFIED Requirements

### Requirement: One launcher seam builds the Job of a row
The Service SHALL build the implement and the fix-checks Jobs from the suspended CronJob `devops-cli-runner` through one seam that takes the args, the size, the name, the deadline and the labels of the row. Only the implement Job SHALL carry the label `implement-repo`, and a Job of another row SHALL send its telemetry as `roadmap-<row>`.

#### Scenario: The admission policy admits a fix Job
- **WHEN** the seam builds the fix-checks Job of pull request 7 of `example/project` with or without `--confirm`, suspended or not
- **THEN** the Job has the runner image, the args only, 4 CPU with 11Gi as request and limit, the component `roadmap-fix-checks`, no `implement-repo` label, and the gate check `tests/gate/k8s_checks/job_admission_policy.py` admits it

#### Scenario: A running fix Job holds no implement lock
- **WHEN** a fix-checks Job runs and a new implement unit is due with a free place
- **THEN** the implement row creates the implement Job
