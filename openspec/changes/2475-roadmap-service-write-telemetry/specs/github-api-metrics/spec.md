# Spec Delta

## ADDED Requirements

### Requirement: Each paced GitHub request names its method
Each count of `devops_cli_github_requests_total` SHALL carry the label `method`, the HTTP method of the request. A GraphQL request SHALL count as a POST, and a gh command other than `gh api` SHALL count as a POST when it writes and a GET when it reads.

#### Scenario: A gh command other than gh api
- **WHEN** `run_gh` sends `gh issue comment 7 --body Hello`, and then `gh issue list`
- **THEN** the first counts with `method` `POST` and the second with `method` `GET`

### Requirement: Each paced GitHub request names its repository and job row
Each count of `devops_cli_github_requests_total` SHALL carry the labels `repo`, the repository of the roadmap Service worker whose round sent the request, and `row`, the job row that sent it. Each SHALL be `other` outside a worker or a row. A request of the GitHub session SHALL count under the repository and the row of the thread that sent it.

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
- **WHEN** a worker of the repository `example-org/repo1` runs a round with the rows `intake` and `refine`
- **THEN** the round's own requests name `example-org/repo1` and the row `other`, and each row's requests name `example-org/repo1` and that row
