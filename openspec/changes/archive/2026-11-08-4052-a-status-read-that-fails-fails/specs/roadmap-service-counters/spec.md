## ADDED Requirements

### Requirement: A status read fails its own row
The status lane SHALL read the GitHub status page in the row `github_status` and the Cloudflare status page in the row `cloudflare_status`. The row `metrics` SHALL read the project metrics only. A row SHALL catch no error of its read, and each row SHALL have its own entry in `schedule.json`, in the record of failed rounds and in the label `row`. A failed read SHALL NOT change the result, the stamp or the suspension of another row.

#### Scenario: One status read fails
- **WHEN** the GitHub status page does not answer and the Cloudflare status page answers in the same round
- **THEN** the job counter of the row `github_status` with `result` `error` grows by 1, the rows `metrics` and `cloudflare_status` count `success` and write their stamp to `schedule.json`, and `github_status` writes none

#### Scenario: A status page answers with text that is no status
- **WHEN** the Cloudflare status page answers with a body that is no JSON
- **THEN** the row `cloudflare_status` ends with a `ServiceStatusError` and no other row fails

#### Scenario: A status read fails the limit of rounds
- **WHEN** the Cloudflare status page does not answer in 3 rounds in a row on the same input
- **THEN** the record of failed rounds holds one entry, for `cloudflare_status`, the gauge `devops_cli_service_job_suspended` is 1 for that row only, and a restart loads the entry

#### Scenario: The metrics row fails to collect
- **WHEN** the collection of the project metrics raises
- **THEN** the row `metrics` ends with that error and reads no status page
