## MODIFIED Requirements

### Requirement: An issue read compares the answer with the request
`GitHubRoadmapStore` SHALL take the answer of a read of an issue or a pull request by its number as that issue only when the answer holds the requested number and names the repository of the store, by its name or by the name that GitHub gives it now. For another answer, `issue`, `item` and `pull_title` SHALL return None, and `read_issue_body` SHALL raise `GitHubNotAnIssueError` with the message `#<number> is not an issue of <repository>.`

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
For a number that is no issue of its repository, the store SHALL log one warning in its life when its listing held the record, when an answer of another issue came, when the read answered 301 or 410, or when the store read no listing. It SHALL log none for a 404 of a number that its listing does not hold. The warning SHALL hold the requested number, the repository of the store, and the place of an answer of another issue as `<owner>/<name>#<number>`, and no other field of the answer.

#### Scenario: The warning names the place of the answer one time
- **WHEN** a store that read no listing reads issue 7 three times, and the fake GitHub answers each read of `repos/acme/widgets/issues/7` with a payload whose `number` is 12, whose `repository_url` names `acme/other` and whose `title` is `A title that is no part of a log line`
- **THEN** the store logs the one warning `#7 is no issue of acme/widgets now: GitHub answers with acme/other#12. The store leaves it out.`

#### Scenario: A store that read no listing
- **WHEN** a store that read no listing reads issue 7 two times, and the fake GitHub answers each read with the status 301, 410 or 404
- **THEN** the store logs the one warning `#7 is no issue of acme/widgets now. The store leaves it out.`

#### Scenario: A store that read a new listing
- **WHEN** a store read a listing that holds the items 7 and 8, the read of number 9 answers 301 and the read of number 99 answers 404
- **THEN** the store logs one warning that names `#9`, and no line for number 99

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

### Requirement: A listing below a number that answers 404, 410 or 301 reads the issue
When the listing of `comments_on`, `label_changes` or `blocked_by` answers 404, 410 or 301, the store SHALL read the issue of that number. When that read gives no issue of the repository, the store SHALL drop the record of the number as an issue read does, and the call SHALL raise `GitHubNotAnIssueError`. When that read gives an issue or a pull request of the repository, the call SHALL raise the error of the listing.

#### Scenario: The number is no issue of the repository
- **WHEN** the fake GitHub answers each request below `repos/acme/widgets/issues/7` with the status 404, and the read of issue 7 with issue 12 of `acme/other`, with the status 301 or with the status 404
- **THEN** `comments_on(7)`, `label_changes(7)` and `blocked_by(7)` each raise `GitHubNotAnIssueError` with the message `#7 is not an issue of acme/widgets.`

#### Scenario: A deleted issue
- **WHEN** the fake GitHub answers each request below `repos/acme/widgets/issues/7` with the status 410 or 301, and the read of issue 7 with the status 410
- **THEN** `comments_on(7)`, `label_changes(7)` and `blocked_by(7)` each raise `GitHubNotAnIssueError`

#### Scenario: The record leaves the listing
- **WHEN** the snapshot of a lane holds the open items 7 and 8, issue 7 is moved to `acme/other` as issue 12 in `GitHubFake`, or is deleted there, and a round of the lane calls `comments_on(7)`
- **THEN** the call raises `GitHubNotAnIssueError`, and the store of that round and of the next round lists item 8 only

#### Scenario: The number is an issue of the repository
- **WHEN** the fake GitHub answers each request below `repos/acme/widgets/issues/7` with the status 404, or with the status 410, and the read of issue 7 with issue 7 of `acme/widgets`
- **THEN** `comments_on(7)` raises `GitHubNotFoundError` with the error code `GITHUB_NOT_FOUND` for the status 404, and a `GitHubOperationError` whose details hold the status 410 for the status 410

### Requirement: A row leaves out an item that is no issue of the repository
A row that gets `GitHubNotAnIssueError` for the number of one of its items SHALL leave that item out, SHALL record no failure for it, and SHALL go on with its other items in the same round. This holds for the alternatives round, for each pass that runs its writes through `write_each`, for the planner and for `prepare` of the stage job, and for the plan drift row, which leaves out a plan pull request whose issue is no issue of the repository.

#### Scenario: An alternatives round whose first read of the item is its comments
- **WHEN** the snapshot of a lane holds the open item 7, whose type is a skip class, and the open item 9, whose type is no skip class, issue 9 is moved to `acme/other` in `GitHubFake`, and the lane runs two rounds of the alternatives check
- **THEN** the first round checks item 7 and holds no failure, the model gets no request, the fake GitHub holds no request with `POST`, `PATCH` or `DELETE` for issue 9, and the second round selects no item

#### Scenario: Ten items leave the repository at one time
- **WHEN** the snapshot of a lane holds the open items 1 to 11, five of them of a skip class, the items 1 to 10 are moved to `acme/other` in `GitHubFake`, and the lane runs one round of the alternatives check
- **THEN** the round raises no error, checks item 11, holds no failure, and the store of the next round lists item 11 only

#### Scenario: The Status passes of the row implement
- **WHEN** the snapshot of a lane holds the items 6, 7 and 8, each Blocked by a stop of the Service, and the Ready item 9 whose plan is on the default branch, issue 7 is moved to `acme/other` as issue 12 in `GitHubFake`, so its issue route answers with issue 12 and its comments route answers 404, and the lane runs `sync_statuses`, `clear_closed_issues` and `clear_stops`
- **THEN** the three results hold no failure, the sweep sets the Status of item 9, the stop pass lists the comments of the items 6, 7 and 8, the store lists the items 6, 8 and 9, and the log holds one line that names `#7`, with `acme/other#12`

#### Scenario: A round of the stage planner
- **WHEN** the listing of a store holds the Ready items 1 and 2, the read of the comments of item 1 and a mark write for item 1 raise `GitHubNotAnIssueError` for number 1, and a round of `devops roadmap stage --confirm` runs
- **THEN** the round raises no error, stages item 2, reports no failure, and the job record of item 1 holds no `stage.failed_at`, no `stage.failed_error`, no `stage.failed_class` and no `stage.failed_step`

#### Scenario: The item of a stage Job left after its selection
- **WHEN** `prepare_stage_job` runs for a Ready item, and the read of the comments of that item raises `GitHubNotAnIssueError` for its number
- **THEN** `prepare_stage_job` ends the run, the job record of the item holds no key that starts with `stage.failed`, and the run folder holds no inputs of the agent

#### Scenario: A write that fails for another number
- **WHEN** `write_each` runs a write of item 8 that raises `GitHubNotAnIssueError` for number 7
- **THEN** `write_each` records one failure of item 8 with the error `GitHubNotAnIssueError`

#### Scenario: A plan pull request whose issue left
- **WHEN** the open plan pull request 7 plans issue 1, and the read of issue 1 raises `GitHubNotFoundError`
- **THEN** `run_plan_drift` raises no error, checks no pull request, writes no label and no comment, and logs one warning that names pull request 7 and issue 1

### Requirement: Other readers of one issue number compare the answer
A reader of `repos/<owner>/<name>/issues/<number>` outside the store SHALL NOT take an answer that names another issue as the issue that it asked for. `GitHubReleaseFeed.closed_issues` SHALL leave out a number whose read answers with another issue or with the status 404, 301 or 410. `GitHubClient.get_issue` SHALL raise `GitHubNotAnIssueError` for an answer that names another issue, for the status 410, and for a 301 that the session does not follow.

#### Scenario: The closed issue of a release left the repository
- **WHEN** a pull request of a release closes the issues 104 and 105, issue 104 is moved to `example/other` in `GitHubFake`, and the read of issue 104 answers with the closed issue at its new place, or with the status 301
- **THEN** `closed_issues` of the release gives `(105,)`

#### Scenario: The client reads a transferred issue
- **WHEN** the fake GitHub API answers `GET /repos/<repository>/issues/7` with an issue whose `number` is 12, or whose `repository_url` or `html_url` names another repository than the one that `GET /repos/<repository>` names
- **THEN** `get_issue(<repository>, 7)` raises `GitHubNotAnIssueError` with the error code `GITHUB_NOT_AN_ISSUE`

#### Scenario: The client reads a deleted issue or a redirect that is not followed
- **WHEN** the fake GitHub API answers `GET /repos/<repository>/issues/7` with the status 410, or with the status 301 and no `Location`
- **THEN** `get_issue(<repository>, 7)` raises `GitHubNotAnIssueError` with the message `#7 is not an issue of <repository>.`

### Requirement: An answer under the old name of a renamed repository is the requested issue
For an answer with the requested number and another repository name, `GitHubRoadmapStore`, `GitHubReleaseFeed` and `GitHubClient.get_issue` SHALL read `repos/<their repository>` at most one time in their life. When its `full_name` is the repository of the issue answer, the reader SHALL take the answer as the requested issue and SHALL log one warning that its repository name is old. Else the reader SHALL refuse the answer.

#### Scenario: A renamed repository
- **WHEN** the fake GitHub answers the reads of the issues 7 and 12 of `acme/widgets` with payloads that hold the numbers 7 and 12 and name `acme/gadgets`, and answers `repos/acme/widgets` with the `full_name` `acme/gadgets`
- **THEN** `issue(7)`, `issue(12)` and `item(7, fresh=True)` give the records of the numbers 7, 12 and 7, `read_issue_body(7)` gives the body, the store sends one read of `repos/acme/widgets`, and the log holds the one warning `GitHub names the repository acme/widgets as acme/gadgets now. The configured name is old: give the new name.`

#### Scenario: A renamed repository drops no record
- **WHEN** the snapshot of a lane holds the open items 7 and 8, the repository is renamed in `GitHubFake`, and a round of the lane reads item 7 and item 8 by their numbers
- **THEN** each read gives its item, and the store of that round and of the next round lists the items 7 and 8

#### Scenario: A transferred issue that kept its number
- **WHEN** the fake GitHub answers the reads of the issues 7 and 12 of `acme/widgets` with payloads that hold the numbers 7 and 12 and name `acme/other`, and answers `repos/acme/widgets` with the `full_name` `acme/widgets`, with the `full_name` `acme/gadgets`, with the status 404 or with the status 301
- **THEN** `issue(7)`, `issue(12)` and `item(7, fresh=True)` return None, and the store sends one read of `repos/acme/widgets`

#### Scenario: The client and the release feed under an old name
- **WHEN** the repository of the client, or of the release feed, is renamed, and each issue answer holds the requested number and the new name
- **THEN** `get_issue` gives the issue two times with one read of `repos/<repository>`, and `closed_issues` of a release gives its two closed issues with one read of `repos/<repository>`

### Requirement: The stage Job goes on when the issue of an active change folder left
`prepare` of the stage Job SHALL take an active change folder of the default branch whose issue is no issue of the repository as no open plan: the folder SHALL name no blocker of the item and SHALL give no record in the issue listing of the agent, and `prepare` SHALL go on with its item.

#### Scenario: The issue of an active change folder was transferred
- **WHEN** the default branch holds the active change folders of the issues 4 and 5, issue 5 is moved to `example/other` in `GitHubFake`, the read of issue 5 answers with the status 301 or with the issue at its new place, and `prepare_stage_job` runs for the Ready item 6
- **THEN** `prepare_stage_job` returns None, the state file names item 6 and is not ended, the issue listing holds the records of the issues 6 and 4 only, and the log holds one line that names `#5`, with `example/other#9` when the answer is the issue at its new place

## REMOVED Requirements

### Requirement: A refused answer logs the requested number
**Reason**: The acceptance criteria of #7337 ask for one log line for an item that a row leaves out, with the new repository and the new number when the answer names them. The requirement refused each field of the answer in a log line.
**Migration**: The requirement "A number that is no issue is logged one time" of this capability gives the one line and the two fields of the answer that it holds.
