## MODIFIED Requirements

### Requirement: The default budget ends before the deadline of a Job
The default of `roadmap.fix_plan.time_budget_seconds` SHALL be 3600. The default plus a margin of 1200 seconds, for one more model run, the push and the comment, SHALL be less than the deadline of each CronJob template of `devops k8s run-job`.

#### Scenario: The default against the Job templates
- **WHEN** a person runs `kubectl -n devops get cronjob devops-cli devops-cli-runner -o jsonpath='{..activeDeadlineSeconds}'` on the cluster
- **THEN** the default budget plus 1200 seconds is less than each
