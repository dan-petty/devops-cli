## MODIFIED Requirements

### Requirement: The report reads the item again
`_report` of the Service SHALL read the live item (`fresh=True`) after it reads the log of the Job and before it decides whether the Job left a stop, and SHALL evaluate `_settles_as_stop` against the refreshed item passed to `write_status` before writing `StatusFacts(stopped=True)`. A stop or non-stop outcome (`drafted`, `yielded`, `returned`) that the runner wrote in that time SHALL keep its class and Status, and the Service SHALL write no second class or overwrite `Status: In Review` with `status/blocked`.

#### Scenario: The runner stops while the report reads the log
- **WHEN** the item is In Progress in the listing of the round, and the runner writes its stop with the class `timeout` while the report reads the log of the Job
- **THEN** the record keeps the class `timeout`, the report names `timeout`, and the counter for `timeout` grows by 1

#### Scenario: A runner Job that drafted without Valkey keeps In Review even with stale brain cache
- **WHEN** `valkey-devops` holds a fresh `brain-issue` cache entry with `Status: In Progress` and no `implement.result`, while GitHub holds `Status: In Review` and `implement.result="drafted"` written by a runner Job without Valkey credentials, and `_report` runs
- **THEN** `_report` reads the live issue from GitHub, posts no stop comment, leaves `Status: In Review` and `implement.stopped` unset, records `implement.job_state="succeeded"`, and releases `owner/service`
