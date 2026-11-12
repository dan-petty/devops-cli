# github-api-metrics Specification

## Purpose
The metrics that devops-cli sends about its requests to GitHub: the requests by rate-limit resource, the throttles and their wait, and the GraphQL points, and the row of the devops-cli dashboard that shows them.

## Requirements

### Requirement: Each paced GitHub request counts one request by its resource
The rate limiter SHALL add 1 to `devops_cli_github_requests_total`, with the label `resource`, for each attempt that it paces. A gh command of `run_gh` and a request of the GitHub session are both counted, and each retry is counted again. The label is the rate-limit resource that the request spends.

#### Scenario: A gh command that GitHub refuses one time
- **WHEN** `run_gh` sends `gh api repos/<owner>/<repo>`, GitHub refuses the first attempt with a rate limit and the second attempt succeeds
- **THEN** `devops_cli_github_requests_total` has one point with the `resource` `core` and the value 2

#### Scenario: A GraphQL command
- **WHEN** `run_gh` sends `gh api graphql` and the attempt succeeds
- **THEN** `devops_cli_github_requests_total` has one point with the `resource` `graphql` and the value 1

#### Scenario: A request of the GitHub session
- **WHEN** the GitHub session sends `GET /user` and GitHub answers it
- **THEN** `devops_cli_github_requests_total` has one point with the `resource` `core` and the value 1

### Requirement: Each throttle is one observation of its wait
Each time devops-cli waits before it sends a refused GitHub request again, it SHALL add one observation of the wait in seconds to `devops_cli_github_throttle_wait_seconds`, with the label `resource`.

#### Scenario: A gh command with a Retry-After
- **WHEN** GitHub refuses the first attempt of `gh api repos/<owner>/<repo>` with a rate limit and `Retry-After: 7`
- **THEN** `devops_cli_github_throttle_wait_seconds` has one observation of 7 with the `resource` `core`

#### Scenario: A request of the GitHub session with a Retry-After
- **WHEN** GitHub answers the first attempt of `GET /user` with 429 and `retry-after: 1`, and answers the second attempt
- **THEN** `devops_cli_github_throttle_wait_seconds` has one observation of 1 with the `resource` `core`

### Requirement: The GraphQL points that GitHub reports are counted
devops-cli SHALL add the cost that a GraphQL answer reports in `rateLimit.cost` to `devops_cli_github_graphql_points_total`.

#### Scenario: A GraphQL answer that costs 3 points
- **WHEN** `run_gh` sends `gh api graphql` and the answer holds `rateLimit` with `cost` 3
- **THEN** `devops_cli_github_graphql_points_total` has one point with the value 3

### Requirement: The devops-cli dashboard shows the GitHub requests
The dashboard `devops-cli.json` SHALL have the row "GitHub API" with a panel for each of these queries: the requests by resource, the throttles by resource, the throttle wait by resource, and the GraphQL points.

#### Scenario: The GitHub API row
- **WHEN** `k8s/monitoring/dashboards/devops-cli.json` is read
- **THEN** the row "GitHub API" holds the panels "GitHub Requests by Resource", "GitHub Throttles by Resource", "GitHub Throttle Wait by Resource" and "GitHub GraphQL Points"
- **AND** they query `sum by (resource) (increase(devops_cli_github_requests_total{job=~"$job"}[1h]))`, `histogram_count(sum by (resource) (increase(devops_cli_github_throttle_wait_seconds{job=~"$job"}[1h])))`, `histogram_sum(sum by (resource) (increase(devops_cli_github_throttle_wait_seconds{job=~"$job"}[1h])))` and `sum(increase(devops_cli_github_graphql_points_total{job=~"$job"}[1h])) or vector(0)`

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

### Requirement: Each paced GitHub request names the HTTP status of its answer

The request counter SHALL name the HTTP status of the answer to each paced GitHub request in its `status` label. A request that gets no answer, and a gh command, SHALL name the status `none`.

#### Scenario: A 304 answer counts with its status
- **WHEN** the GitHub session sends a conditional GET and GitHub answers 304.
- **THEN** the counter has one sample for that attempt with `status` `304`.

#### Scenario: A gh command counts with status none
- **WHEN** the rate limiter paces a gh command.
- **THEN** the counter has one sample for that attempt with `status` `none`.

### Requirement: The rate limiter logs its pace lines at DEBUG

The rate limiter SHALL log each mandatory pause and each quota window reset at DEBUG level.

#### Scenario: A mandatory pause is logged at DEBUG
- **WHEN** the rate limiter delays a request for its quota.
- **THEN** the pause record has level DEBUG, and no record of that pause has level INFO.

### Requirement: A paginated devops gh api read of a REST GET counts each page
`devops gh api --paginate` SHALL read a REST GET of a path through the GitHub session, so that each page adds 1 to `devops_cli_github_requests_total` with the status of its answer. gh SHALL keep a GraphQL read, a write, an endpoint with a gh placeholder, a full URL, `--template`, `--cache` and any other gh flag. `--jq` SHALL run on each page.

#### Scenario: A listing of 4 pages
- **WHEN** `devops gh api 'repos/<owner>/<repo>/issues?state=open&per_page=1' --paginate` reads 4 linked pages from the GitHub fake
- **THEN** `devops_cli_github_requests_total` has one point with the `resource` `core`, the `status` `200` and the value 4
- **AND** the output is one JSON array that holds the items of the 4 pages

#### Scenario: A jq filter on each page
- **WHEN** `devops gh api ... --paginate --jq 'length, .[].number'` reads a page of 2 items and a page of 1 item
- **THEN** the output is the lines `2`, `1`, `2`, `1` and `3`

#### Scenario: A read that gh keeps
- **WHEN** `devops gh api 'repos/:owner/:repo/issues' --paginate` runs
- **THEN** gh gets the argv with `--paginate`, and the GitHub session sends no request
