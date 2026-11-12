## MODIFIED Requirements

### Requirement: A paginated devops gh api read of a REST GET counts each page
`devops gh api --paginate` SHALL read a REST GET of a path through the GitHub session, so that each page adds 1 to `devops_cli_github_requests_total` with the status of its answer. The session SHALL add `per_page=100` when the endpoint sets no `per_page`, as gh does. gh SHALL keep a GraphQL read, a write, an endpoint with a gh placeholder, a full URL, `--template`, `--cache` and any other gh flag. `--jq` SHALL run on each page.

#### Scenario: A listing of 4 pages
- **WHEN** `devops gh api 'repos/<owner>/<repo>/issues?state=open&per_page=1' --paginate` reads 4 linked pages from the GitHub fake
- **THEN** `devops_cli_github_requests_total` has one point with the `resource` `core`, the `status` `200` and the value 4
- **AND** the output is one JSON array that holds the items of the 4 pages

#### Scenario: A jq filter on each page
- **WHEN** `devops gh api ... --paginate --jq 'length, .[].number'` reads a page of 2 items and a page of 1 item
- **THEN** the output is the lines `2`, `1`, `2`, `1` and `3`

#### Scenario: An endpoint with no per_page
- **WHEN** `devops gh api 'repos/<owner>/<repo>/labels' --paginate --jq length` reads a listing of 150 labels from the GitHub fake
- **THEN** the first request URL holds `per_page=100`
- **AND** the session sends 2 requests, and the output is the lines `100` and `50`

#### Scenario: An endpoint that sets per_page
- **WHEN** `devops gh api 'repos/<owner>/<repo>/labels?per_page=50' --paginate` runs
- **THEN** the request URL holds `per_page=50` and no other `per_page`

#### Scenario: A read that gh keeps
- **WHEN** `devops gh api 'repos/:owner/:repo/issues' --paginate` runs
- **THEN** gh gets the argv with `--paginate`, and the GitHub session sends no request
