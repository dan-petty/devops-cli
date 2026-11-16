## MODIFIED Requirements

### Requirement: Each paced GitHub request names its repository and job row
Each count of `devops_cli_github_requests_total` SHALL carry the labels `repo`, the repository of the roadmap Service worker whose round sent the request, and `row`, the job row that sent it. A round's own request SHALL name its loop: `poll`, or `webhook` when a trigger of the round or a scoped update is a webhook delivery. Each SHALL be `other` outside a worker. A request of the GitHub session SHALL count under the repository and the row of the thread that sent it.

#### Scenario: A comment of a job row
- **WHEN** `run_gh` sends `gh api -X POST repos/octo/repo/issues/7/comments` in the scope of the repository `octo/repo` and the row `refine`
- **THEN** `devops_cli_github_requests_total` has one point with `resource` `core`, `method` `POST`, `repo` `octo/repo` and `row` `refine`

#### Scenario: A request outside a worker
- **WHEN** `run_gh` sends the same comment outside any scope
- **THEN** the point has `repo` `other` and `row` `other`

#### Scenario: A request of the GitHub session
- **WHEN** the GitHub session sends `PATCH /repos/octo/repo/issues/7` in the scope of the repository `octo/repo` and the row `intake`
- **THEN** `devops_cli_github_requests_total` has one point with `method` `PATCH`, `repo` `octo/repo` and `row` `intake`

#### Scenario: A round of a Service worker
- **WHEN** a worker of the repository `example-org/repo1` runs a round for a webhook delivery with the rows `intake` and `refine`
- **THEN** the round's own requests name `example-org/repo1` and the row `webhook`, and each row's requests name `example-org/repo1` and that row

#### Scenario: A round of a poll
- **WHEN** the same worker runs a round for a poll
- **THEN** the round's own requests name the row `poll`

#### Scenario: A webhook joins a pending poll
- **WHEN** a webhook delivery arrives while a poll waits in the queue of the lane
- **THEN** the round of both triggers names the row `webhook`

#### Scenario: A scoped update
- **WHEN** a worker runs the scoped update of a webhook delivery
- **THEN** its requests outside the row of its job name the row `webhook`

## ADDED Requirements

### Requirement: No request of a Service round counts as other
Every request that a round of a Service lane sends SHALL name a row other than `other`. The read of the open work after a round SHALL name the row `idle_check`. The ast-grep rule `github-request-scope-row` SHALL fail on a call of `request_scope` in `src/` that names no `row`.

#### Scenario: Every lane runs a round
- **WHEN** every lane that `service_jobs` builds runs a round for a poll, each row of the table due and each row reading one issue
- **THEN** each request names a row of the table, `poll` or `idle_check`, and none names `other`

#### Scenario: A scope with no row
- **WHEN** ast-grep scans `with request_scope(repo=repo):` in a file under `src/`
- **THEN** the rule `github-request-scope-row` reports it
