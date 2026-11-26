## MODIFIED Requirements

### Requirement: An issue read compares the answer with the request
`GitHubRoadmapStore` SHALL take the answer of a read of an issue or a pull request by its number as that issue only when the `number` of the answer is the requested number and the answer names the repository of the store. For an answer that names another issue, `issue`, `item` and `pull_title` SHALL return None, and `read_issue_body` SHALL raise `GitHubNotAnIssueError`, a `GitHubNotFoundError` with the error code `GITHUB_NOT_AN_ISSUE` and the message `#<number> is not an issue of <repository>.`

#### Scenario: An answer with another number and another repository
- **WHEN** the fake GitHub answers the read of `repos/acme/widgets/issues/7` with a payload whose `number` is 12 and whose `repository_url` names `acme/other`
- **THEN** `issue(7)` and `item(7)` of the store of `acme/widgets` return None, and `read_issue_body(7)` raises `GitHubNotAnIssueError` with the error code `GITHUB_NOT_AN_ISSUE` and the message `#7 is not an issue of acme/widgets.`

#### Scenario: An answer with another number of the same repository
- **WHEN** the fake GitHub answers the read of `repos/acme/widgets/issues/7` with a payload whose `number` is 12 and whose `repository_url` names `acme/widgets`
- **THEN** `issue(7)` and `item(7)` return None

#### Scenario: A pull request title read that answers with another pull request
- **WHEN** the fake GitHub answers the read of `repos/acme/widgets/issues/7` with a payload that holds `pull_request`, whose `number` is 12 and whose `repository_url` names `acme/other`
- **THEN** `pull_title(7)` returns None

#### Scenario: An answer for the requested number and repository reads as before
- **WHEN** the fake GitHub answers the read of `repos/acme/widgets/issues/7` with a payload whose `number` is 7 and whose `repository_url` names `acme/widgets`
- **THEN** `issue(7)` returns the record of the payload with the number 7, `item(7)` returns its item, and `read_issue_body(7)` returns its body

### Requirement: A write is refused when its read answers with another issue
A write of `GitHubRoadmapStore` that reads the issue first SHALL raise `GitHubNotAnIssueError` and SHALL send no write request when that read answers with another issue. These writes are `set_field`, `set_fields`, `set_marks`, `write_issue_body`, `set_title` and `close`, and `add_sub_issue` and `add_blocked_by` when they read the issue. `comment` SHALL do the same for a comment with a job marker, which reads the comments first.

#### Scenario: A mark write after the issue left the repository
- **WHEN** a store of `acme/widgets` read item 7, the fake GitHub then answers the read of `repos/acme/widgets/issues/7` with a payload whose `number` is 12 and whose `repository_url` names `acme/other`, and the store calls `set_marks` for the item
- **THEN** the call raises `GitHubNotAnIssueError` with the message `#7 is not an issue of acme/widgets.`, and the fake GitHub holds no request with `POST`, `PATCH` or `DELETE`

#### Scenario: A job comment after the issue left the repository
- **WHEN** the fake GitHub answers each request below `repos/acme/widgets/issues/7` with the status 404 and the read of issue 7 with issue 12 of `acme/other`, and the store calls `comment` for number 7 with a text that starts with the marker of the refine job
- **THEN** the call raises `GitHubNotAnIssueError`, and the fake GitHub holds no request with `POST`, `PATCH` or `DELETE`

### Requirement: A row sends no write for an item whose read answers with another issue
A round of the alternatives check and a Status sweep SHALL send no write request for an item of the listing whose issue read answers with another issue. Each SHALL leave the item out and go on with the other items, and SHALL record no failure for the item. The next round of the same lane SHALL NOT select the item.

#### Scenario: An alternatives round
- **WHEN** the snapshot of a lane holds the open items 7 and 8 of `acme/widgets`, whose type is a skip class, the fake GitHub answers the read of issue 7 with issue 12 of `acme/other`, and the lane runs two rounds of the alternatives check
- **THEN** the first round raises no error, writes the check of item 8 with one `PATCH` and holds no failure, the second round checks no item, and the fake GitHub holds no request with `POST`, `PATCH` or `DELETE` for issue 7

#### Scenario: A Status sweep
- **WHEN** the snapshot of a lane holds the open item 7 of `acme/widgets` with the Status Ready that a job recorded, its plan is on the default branch, the fake GitHub answers the read of issue 7 with issue 12 of `acme/other`, and the lane runs two Status sweeps
- **THEN** each sweep writes no item and reports no failure, the store of the second sweep does not list item 7, and the fake GitHub holds no request with `POST`, `PATCH` or `DELETE`

## ADDED Requirements

### Requirement: A number that is no issue is logged one time
For a number that is no issue of its repository, the store SHALL log one warning in its life, when its listing held the record of the number or when an answer that names another issue came for it. The warning SHALL hold the requested number and the name of the repository of the store. When an answer names another issue, the warning SHALL also hold the repository and the number of that answer as `<owner>/<name>#<number>`. No log line of the store SHALL hold another field of the answer.

#### Scenario: The warning names the place of the answer one time
- **WHEN** a store that read no listing reads issue 7 three times, and the fake GitHub answers each read of `repos/acme/widgets/issues/7` with a payload whose `number` is 12, whose `repository_url` names `acme/other` and whose `title` is `A title that is no part of a log line`
- **THEN** the store logs the one warning `#7 is no issue of acme/widgets now: GitHub answers with acme/other#12. The store leaves it out.`

#### Scenario: A redirect that names no place
- **WHEN** the listing of a store holds item 7, and the fake GitHub answers the read of issue 7 with the status 301
- **THEN** the store logs the one warning `#7 is no issue of acme/widgets now. The store leaves it out.`

### Requirement: A read that answers 301 or 410 gives no issue
`GitHubRoadmapStore` SHALL take the statuses 301 and 410 of a read of one issue by its number as it takes the status 404: the plain read and the conditional read with `If-None-Match` SHALL give no issue, and the store SHALL drop what it holds of the number. A listing and each other route that answers 301 or 410 SHALL raise as before.

#### Scenario: A plain read
- **WHEN** the fake GitHub answers the read of `repos/acme/widgets/issues/7` with exit status 1 and `gh: HTTP 301`, or with `gh: This issue was deleted (HTTP 410)`
- **THEN** `issue(7)`, `item(7)` and `pull_title(7)` return None, and `read_issue_body(7)` raises `GitHubNotAnIssueError`

#### Scenario: A conditional read
- **WHEN** the brain entry of issue 7 is older than one hour, and the fake GitHub answers the read with `If-None-Match` with exit status 1 and `gh: HTTP 301`, or with exit status 0 and the status line `HTTP/2 301 Moved Permanently`
- **THEN** `issue(7)` returns None, and the brain holds no entry of issue 7

#### Scenario: Another route that answers 301
- **WHEN** the fake GitHub answers the listing of the issues and the read of a commit with exit status 1 and `gh: HTTP 301`
- **THEN** `items()` and `evidence_holds` of a regression commit each raise `GitHubOperationError` whose message holds `HTTP 301`

### Requirement: A 404 below a number reads the issue
When the listing of `comments_on`, `label_changes` or `blocked_by` answers 404, the store SHALL read the issue of that number. When that read gives no issue of the repository, the store SHALL drop the record of the number as an issue read does, and the call SHALL raise `GitHubNotAnIssueError`. When that read gives an issue or a pull request of the repository, the call SHALL raise the `GitHubNotFoundError` of the listing.

#### Scenario: The number is no issue of the repository
- **WHEN** the fake GitHub answers each request below `repos/acme/widgets/issues/7` with the status 404, and the read of issue 7 with issue 12 of `acme/other`, with the status 301 or with the status 404
- **THEN** `comments_on(7)`, `label_changes(7)` and `blocked_by(7)` each raise `GitHubNotAnIssueError` with the message `#7 is not an issue of acme/widgets.`

#### Scenario: The record leaves the listing
- **WHEN** the snapshot of a lane holds the open items 7 and 8, issue 7 is moved to `acme/other` as issue 12 in `GitHubFake`, and a round of the lane calls `comments_on(7)` two times
- **THEN** each call raises `GitHubNotAnIssueError`, the store of that round and of the next round lists item 8 only, and the store logs one warning that holds `acme/other#12`

#### Scenario: The number is an issue of the repository
- **WHEN** the fake GitHub answers each request below `repos/acme/widgets/issues/7` with the status 404 and the read of issue 7 with issue 7 of `acme/widgets`
- **THEN** `comments_on(7)` raises `GitHubNotFoundError` with the error code `GITHUB_NOT_FOUND`

### Requirement: A row leaves out an item that is no issue of the repository
A row that gets `GitHubNotAnIssueError` for the number of one of its items SHALL leave that item out, SHALL record no failure for it, and SHALL go on with its other items in the same round. This holds for the alternatives round, for each pass that runs its writes through `write_each`, and for the plan drift row, which leaves out a plan pull request whose issue is no issue of the repository.

#### Scenario: An alternatives round whose first read of the item is its comments
- **WHEN** the snapshot of a lane holds the open item 7, whose type is a skip class, and the open item 9, whose type is no skip class, issue 9 is moved to `acme/other` in `GitHubFake`, and the lane runs two rounds of the alternatives check
- **THEN** the first round checks item 7 and holds no failure, the model gets no request, the fake GitHub holds no request with `POST`, `PATCH` or `DELETE` for issue 9, and the second round selects no item

#### Scenario: Ten items leave the repository at one time
- **WHEN** the snapshot of a lane holds the open items 1 to 11, five of them of a skip class, the items 1 to 10 are moved to `acme/other` in `GitHubFake`, and the lane runs one round of the alternatives check
- **THEN** the round raises no error, checks item 11, holds no failure, and the store of the next round lists item 11 only

#### Scenario: The Status passes of the row implement
- **WHEN** the snapshot of a lane holds the items 6, 7 and 8, each Blocked by a stop of the Service, and the Ready item 9 whose plan is on the default branch, issue 7 is moved to `acme/other` as issue 12 in `GitHubFake`, so its issue route answers with issue 12 and its comments route answers 404, and the lane runs `sync_statuses`, `clear_closed_issues` and `clear_stops`
- **THEN** the three results hold no failure, the sweep sets the Status of item 9, the stop pass lists the comments of the items 6, 7 and 8, the store lists the items 6, 8 and 9, and the log holds one line that names `#7`, with `acme/other#12`

#### Scenario: A plan pull request whose issue left
- **WHEN** the open plan pull request 7 plans issue 1, and the read of issue 1 raises `GitHubNotFoundError`
- **THEN** `run_plan_drift` raises no error, checks no pull request, writes no label and no comment, and logs one warning that names pull request 7 and issue 1

### Requirement: Other readers of one issue number compare the answer
A reader of `repos/<owner>/<name>/issues/<number>` outside the store SHALL NOT take an answer that names another issue as the issue that it asked for. `GitHubReleaseFeed.closed_issues` SHALL leave out a number whose read answers with another issue or with the status 404, 301 or 410. `GitHubClient.get_issue` SHALL raise `GitHubNotAnIssueError` for an answer that names another number or another repository.

#### Scenario: The closed issue of a release left the repository
- **WHEN** a pull request of a release closes the issues 104 and 105, issue 104 is moved to `example/other` in `GitHubFake`, and the read of issue 104 answers with the closed issue at its new place, or with the status 301
- **THEN** `closed_issues` of the release gives `(105,)`

#### Scenario: The client reads a transferred issue
- **WHEN** the fake GitHub API answers `GET /repos/<repository>/issues/7` with an issue whose `number` is 12, or whose `repository_url` or `html_url` names `example/other`
- **THEN** `get_issue(<repository>, 7)` raises `GitHubNotAnIssueError` with the error code `GITHUB_NOT_AN_ISSUE`

### Requirement: The stage Job goes on when the issue of an active change folder left
`prepare` of the stage Job SHALL take an active change folder of the default branch whose issue is no issue of the repository as no open plan: the folder SHALL name no blocker of the item and SHALL give no record in the issue listing of the agent, and `prepare` SHALL go on with its item.

#### Scenario: The issue of an active change folder was transferred
- **WHEN** the default branch holds the active change folders of the issues 4 and 5, issue 5 is moved to `example/other` in `GitHubFake`, the read of issue 5 answers with the status 301 or with the issue at its new place, and `prepare_stage_job` runs for the Ready item 6
- **THEN** `prepare_stage_job` returns None, the state file names item 6 and is not ended, and the issue listing holds the records of the issues 6 and 4 only

## REMOVED Requirements

### Requirement: A refused answer logs the requested number
**Reason**: The acceptance criteria of #7337 ask for one log line for an item that a row leaves out, with the new repository and the new number when the answer names them. The requirement refused each field of the answer in a log line.
**Migration**: The requirement "A number that is no issue is logged one time" of this capability gives the one line and the two fields of the answer that it holds.
