## ADDED Requirements

### Requirement: The budget counts the requests that GitHub counts
The hourly budget SHALL leave out a request that GitHub answers with status 304, because GitHub does not count such an answer against its primary rate limit. The request SHALL leave the window, the budget file and the cost of a round when its answer comes. A request with no answer SHALL stay in the budget. `devops_cli_service_budget_spent_requests` SHALL show the requests that the budget counts. `devops_cli_github_requests_total` SHALL still count every request with its `status`.

#### Scenario: A conditional request that gets a 304 answer
- **WHEN** the Service reads a URL twice through the GitHub session, and GitHub answers the second read with 304
- **THEN** the budget has spent 1 request, and `devops_cli_github_requests_total` holds one request with status 200 and one with status 304

#### Scenario: A request that gets no answer
- **WHEN** the connection of a request is refused
- **THEN** the request stays in the budget

#### Scenario: A refund reaches the file and the cadence
- **WHEN** a budget of 360 admits 40 requests, 20 of them get a 304 answer, and one round ends
- **THEN** the window and the budget file hold 20 requests, and the poll interval is the one that a cost of 20 requests gives
