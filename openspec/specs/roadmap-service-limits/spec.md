# roadmap-service-limits Specification

## Purpose
Defines when the roadmap Service stops, holds or skips its GitHub work, so a refused identity, a spent hourly budget or a job that fails at each round never makes the Service send requests without bound.

## Requirements

### Requirement: A refused identity stops the Service
When a round fails because GitHub refused the Service's identity, the Service SHALL start no round for any repository or lane, also after a restart, until a person removes its halt record and restarts it, SHALL send no later job of the failed round, and SHALL report the refusal once with one error log line and one count of `devops_cli_service_identity_refused_total` that name the identity.

#### Scenario: A suspended account
- **WHEN** a job fails with `gh: Sorry. Your account was suspended. (HTTP 403)` and triggers keep arriving for every repository
- **THEN** no other job starts, and exactly one error line and one metric count name the account

#### Scenario: Another failure
- **WHEN** a round fails for a reason that is not a refused identity
- **THEN** the Service starts later rounds as usual

### Requirement: Requests stay under an hourly budget
The Service SHALL check `service.github_requests_per_hour` for each GitHub request where the request is sent, SHALL make a request that the last hour has no room for wait until the window has room, SHALL start no round while the window is full, SHALL run the held triggers as one round for each lane of each repository when the window has room, and SHALL poll no faster than the budget pays for at the measured cost of a round.

#### Scenario: A spent budget
- **WHEN** the requests of the last hour are as many as the budget
- **THEN** a trigger that arrives starts no round until an hour has passed since the oldest of those requests

#### Scenario: A round that would pass the budget
- **WHEN** a round has sent requests up to the budget and sends one more
- **THEN** the request waits until the window has room, and the Service sends no more than the budget in any hour

#### Scenario: A costly round
- **WHEN** the rounds of one poll cost more than the budget pays for at the configured interval
- **THEN** the next poll comes after the longer interval that the budget gives

### Requirement: A job that fails each round is suspended
A roadmap job that failed `DEFAULT_SERVICE_MAX_FAILED_ROUNDS` rounds in a row on the same input SHALL NOT run again until its input changes, and a success SHALL clear its count. The log line that suspends a job SHALL name the cause of each of those rounds. The ledger record SHALL hold the causes, so a restart keeps them. A record in the format without causes SHALL load, and its causes SHALL read as `unknown`.

#### Scenario: Polls after the limit
- **WHEN** a job has failed its limit of rounds and only polls follow
- **THEN** the job does not run and the round succeeds

#### Scenario: A webhook after the limit
- **WHEN** a webhook trigger follows
- **THEN** the job runs again

#### Scenario: The cause of the suspension
- **WHEN** a job fails three rounds in a row, with the errors `GitHubOperationError`, `RoadmapRefineError` and `GitHubOperationError`
- **THEN** the log line that suspends the job names those three causes in that order

#### Scenario: A file written by the running version
- **WHEN** the ledger file holds records in the format that the running version writes, and a new process starts over it
- **THEN** the start succeeds and the ledger holds those records, with their causes

#### Scenario: A restart keeps the causes
- **WHEN** a ledger with the recorded causes `AIClientError` and `RoadmapStageError` is written, and a new process loads the record
- **THEN** the new ledger holds those two causes in that order

#### Scenario: A record from before the causes
- **WHEN** the ledger file holds an entry of a job at the limit, with no causes, and a new process starts over it
- **THEN** the start succeeds, the job is suspended, and its causes read as `unknown`

### Requirement: A round that the stop of the Service ends is not a failed round
A round that ends with the error that the request budget raises when the Service is stopping, or with an error that has it as its cause, SHALL leave the count of failed rounds of its job as it was. A group of errors SHALL be a stop only when each member is. The stage job SHALL end with that error and SHALL make no failed item of it. Such a round SHALL count as `result="stopped"` and log no error line.

#### Scenario: Rounds that a stop ends
- **WHEN** three rounds of a job end with the stop error of the budget, and a normal round follows
- **THEN** the count of the job did not change, the job is not suspended, and the normal round runs the job

#### Scenario: A stop in the cause chain
- **WHEN** a round of a job ends with an error whose cause is the stop error of the budget
- **THEN** the round does not count as a failed round

#### Scenario: A stop does not clear a count
- **WHEN** a job has failed one round for a real reason, a stop ends the next round, and a real failure follows, with the same input each time
- **THEN** the count of the job is 2 after the last round

#### Scenario: A stop in the stage job
- **WHEN** a write of the stage job meets the stop error of the budget
- **THEN** the stage job ends with that error, and it makes no failed item of it

#### Scenario: A scoped update that a stop ends
- **WHEN** a scoped update ends with the stop error of the budget
- **THEN** its result is `stopped`, the count of `result="error"` does not change, and the Service logs no error line

### Requirement: A stop of the Service does not hide a failed item
When an item failed for a real reason before the stop, in the plan or in an earlier write, the stage job SHALL record the failure in the job record of the item and then end with the stop. The refine job SHALL end with the failure of those items, so the round counts.

#### Scenario: A stop after a failed item
- **WHEN** an item of the stage job failed for a real reason, in the plan or in an earlier write, and a later write meets the stop error of the budget
- **THEN** the job record of that item holds the failure, and the stage job ends with the stop

#### Scenario: A stop in the refine job after a failed item
- **WHEN** the model call failed for an item of the refine job, and a write meets the stop error of the budget
- **THEN** the refine job ends with the failure of that item, and the round counts as a failed round

### Requirement: A suspended installation and a header-less 403 to a write are refusals
The Service SHALL read as a refused identity a reply that says the App installation is suspended, and a 403 to a write whose answer has no `x-ratelimit-*` header.

#### Scenario: A suspended installation
- **WHEN** a job's write through gh fails with `gh: This installation has been suspended (HTTP 403)`
- **THEN** the Service halts, and one metric count names the identity

#### Scenario: A write refused with no rate-limit header
- **WHEN** a job's write through the GitHub session gets a 403 whose answer has no `x-ratelimit-*` header
- **THEN** the Service halts, and one metric count names the identity

### Requirement: A restart keeps what stops the Service
The Service SHALL keep its halt, the GitHub requests of its budget window and its ledger of failed rounds in files in the `roadmap` directory of its data directory, and a Service that starts SHALL read them back. It SHALL write each request to the budget file when it sends the request. A Service that starts halted SHALL count the refusal once. A file that cannot be read SHALL stop the start with an error that names it.

#### Scenario: A pod stops in the middle of a round
- **WHEN** the Service sends 3 requests of a round and the pod stops before the round ends
- **THEN** the budget file holds 3 requests, and the Service that starts next has spent 3 requests

#### Scenario: A restart over the same volume
- **WHEN** a Service halts after 60 requests in the window, a job fails its limit of rounds, and a new Service starts over the same directory with its request count and its metrics at zero
- **THEN** the new Service is halted, its refusal counter is 1, its budget has spent 60 requests, and the job does not run at the next poll

#### Scenario: A record that cannot be read
- **WHEN** the budget record or the ledger record holds text that is not a record
- **THEN** the start fails with an error whose details name the file

### Requirement: A rate limit holds every worker
When a GitHub request of one worker meets a rate limit, no worker SHALL send a GitHub request of the identity before the wait that the rate limit asks for ends, also when the request is not sent again because its retries are spent.

#### Scenario: A secondary limit with retry-after
- **WHEN** one worker's request gets a 403 with `retry-after: 60` and another worker then sends a request
- **THEN** the first worker waits 60 s before its retry, and the other worker's request waits until those 60 s end

#### Scenario: The last rate limit of a request
- **WHEN** one worker's request meets a secondary limit at each attempt, through the session with `retry-after: 60` or through gh, its round fails when its retries are spent, and another worker then sends a request
- **THEN** the other worker's request waits at least 60 s after the last refusal

### Requirement: The Service shows its budget and each hold
The Service's `/metrics` SHALL hold `devops_cli_service_budget_limit_requests`, the hourly budget, and `devops_cli_service_budget_spent_requests`, the GitHub requests of the last hour as of the last request or check. The Service SHALL add 1 to `devops_cli_service_budget_holds_total` each time a hold begins.

#### Scenario: A hold that begins, ends and begins again
- **WHEN** a budget of 100 sees 100 requests and two checks, then the window slides past those requests, then 100 more requests and a check
- **THEN** the gauges and the counter read (limit 100, spent 0, holds 0), then (100, 100, 1), then (100, 0, 1), then (100, 100, 2)

### Requirement: The Service shows each suspended job
`devops_cli_service_job_suspended` SHALL be 1, with the labels `repo` and `row`, while a job has failed its limit of rounds in a row, and 0 after it fails on new input or succeeds. A ledger and a budget read back at start SHALL show what they hold.

#### Scenario: A job that fails its limit of rounds
- **WHEN** a ledger with a limit of 2 counts failures of one job on input a, a, b and b, then a success
- **THEN** the job's gauge reads 0, 1, 0, 1, then 0

#### Scenario: A restart over the same volume
- **WHEN** a new Service starts over a volume whose records hold 60 requests of the window and a suspended job
- **THEN** its budget gauge reads 60 and the job's gauge reads 1

### Requirement: The Service limits its model calls to a configured count in flight
The Service SHALL keep at most `service.model_call_concurrency` model calls in flight at once, default 1, and a lane that cannot take a slot SHALL wait in the Service's process, where no stall timer runs, until it takes one. The Service SHALL set the limit from its setting at start.

#### Scenario: Two lanes send a model call at the same time
- **WHEN** the Service has a limit of 1, two lanes each send a slow model call at the same time, and each call holds its slot while it sends
- **THEN** at most one call is in flight at once, and both calls finish

#### Scenario: A lane waits for a held slot
- **WHEN** the Service has a limit of 1, one call holds the slot, and a lane sends a model call
- **THEN** the lane waits in the process and sends its call once the other call releases the slot

#### Scenario: The limit is raised
- **WHEN** the Service has a limit of 2, four lanes each send a slow model call at the same time, and each call holds its slot while it sends
- **THEN** at most two calls are in flight at once, and all four calls finish

### Requirement: The hourly budget has a variable and a description
`DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR` SHALL set `service.github_requests_per_hour`, and `devops config show` and `devops config env` SHALL list the setting and the variable, each with a description.

#### Scenario: The variable sets the budget
- **WHEN** `DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR` is `2000` and the settings load
- **THEN** `service.github_requests_per_hour` is 2000

#### Scenario: A budget of zero
- **WHEN** `DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR` is `0` and the settings load
- **THEN** the load stops with an error that names the variable

#### Scenario: The setting is listed
- **WHEN** `devops config show --json` runs
- **THEN** a row has the key `service.github_requests_per_hour`

### Requirement: A comment of a person starts a suspended job again
The input of a job that failed a round SHALL hold the creation time of the newest comment of a person on an issue. The comment SHALL NOT be older than the last success of the job. A new comment of a person SHALL make the input differ from the input of the failed rounds. So a suspended job runs again and counts its failed rounds from one. A comment made before the last success, and a poll with no new comment, SHALL leave the input as it was.

#### Scenario: A person comments on a suspended job
- **WHEN** a job has failed its limit of rounds, a person with the association OWNER comments on an issue, and a poll follows
- **THEN** the job runs again in that round

#### Scenario: A restarted job counts from one
- **WHEN** a job runs again after a comment of a person and keeps failing with no further comment
- **THEN** the job runs for its limit of rounds and then does not run

#### Scenario: A poll with no new comment
- **WHEN** a job failed its limit of rounds with a person's comment in its input, and two polls follow with no new one
- **THEN** the job does not run at either poll

#### Scenario: A comment made before the last success
- **WHEN** a person comments, the job then succeeds once, and the job then fails its limit of rounds
- **THEN** the job does not run at the next poll

#### Scenario: A comment that a page of newer comments follows
- **WHEN** a job failed its limit of rounds with a person's comment in its input, and a bot then makes 100 comments
- **THEN** the job runs at the next poll, and counts its failed rounds from one

### Requirement: Only a person with write access is a person
A person SHALL be an author whose association is OWNER, MEMBER or COLLABORATOR. The login of a person SHALL NOT end in `[bot]`. A person SHALL NOT be the account that the process acts as. A comment of any other author, and a comment on a pull request, SHALL leave the input of a suspended job as it was.

#### Scenario: The App bot comments
- **WHEN** a job has failed its limit of rounds and `devops-cli-service[bot]` with the association CONTRIBUTOR comments on an issue of its repository
- **THEN** the job does not run at the next poll

#### Scenario: A bot with write access comments
- **WHEN** a job has failed its limit of rounds and `dependabot[bot]` with the association COLLABORATOR comments
- **THEN** the job does not run at the next poll

#### Scenario: The account of the process comments
- **WHEN** a job has failed its limit of rounds and the account that the process acts as comments with the association OWNER
- **THEN** the job does not run at the next poll

#### Scenario: An account with no write access comments
- **WHEN** a job has failed its limit of rounds and an account with the association NONE comments
- **THEN** the job does not run at the next poll

#### Scenario: A person comments on a pull request
- **WHEN** a job has failed its limit of rounds and a person with the association OWNER comments on a pull request
- **THEN** the job does not run at the next poll

### Requirement: A round reads at most one page of comments
A round SHALL read one listing of the comments of its repository for all the jobs of the lane that need it. The listing is newest first. It starts at the oldest last success among those jobs, or at the first comment when one of them never succeeded. The round SHALL stop at the first comment of a person or after the newest 100 comments, whichever comes first.

#### Scenario: Three failed jobs in one lane
- **WHEN** three jobs of a lane have each failed a round, and a poll follows
- **THEN** the round asks the store for the comments once, and takes no more comment than the first of a person

#### Scenario: Only comments of a bot
- **WHEN** a job has failed its limit of rounds, a bot made 250 comments after its last success, and a poll follows
- **THEN** the round takes 100 comments, and the job does not run

#### Scenario: A failed read
- **WHEN** a job has failed a round, and the read of the comments fails in the next round
- **THEN** the round ends with the error of the read, and the job does not run. Its count of failed rounds stays as it was

### Requirement: A round reads comments only for a job that failed
A round SHALL read the comments only when it only polls and a job that may run in it holds a failed round. A round that a webhook started, a round with no failed job and a dry run SHALL read no comment. A read that fails SHALL count as no failed round of a job.

#### Scenario: No failed job
- **WHEN** no job of the lane has failed a round, and a poll follows
- **THEN** the round does not read the comments

#### Scenario: A round that a webhook started
- **WHEN** a job has failed its limit of rounds, a person comments, and a round that a webhook delivery started follows
- **THEN** the job runs in that round, and the round does not read the comments

#### Scenario: A dry run
- **WHEN** a job has failed its limit of rounds and a round runs with `dry_run`
- **THEN** the round does not read the comments

### Requirement: The store lists the comments of the repository newest first
`GitHubRoadmapStore.comments_since` SHALL read `repos/<repo>/issues/comments` with `sort=created`, `direction=desc` and 100 comments a page. It SHALL add the `since` time in UTC when one is given. It SHALL ask for a page only when the caller needs a comment of it. So a caller that stops at the first comment that it wants sends no request for another page.

#### Scenario: The listing path
- **WHEN** a caller reads the comments since 2026-11-05 12:00 UTC
- **THEN** the store sends one request for `issues/comments?sort=created&direction=desc&since=2026-11-05T12:00:00Z&per_page=100`, and each comment holds its author login, association and creation time

#### Scenario: No time
- **WHEN** a caller reads the comments with no `since` time
- **THEN** the request has no `since` parameter

#### Scenario: A caller that stops at the first comment
- **WHEN** the first page links a next page and the caller takes only the first comment
- **THEN** the store sent one request

#### Scenario: A caller that takes one page
- **WHEN** the first page holds 100 comments and links a next page, and the caller takes 100 comments
- **THEN** the store sent one request

#### Scenario: A comment on a pull request
- **WHEN** the listing holds a comment with the `html_url` path `/pull/844` and one with `/issues/844`, and both have the `issue_url` `issues/844`
- **THEN** the first comment says that it is on a pull request, and the second does not

### Requirement: The suspension line names the new inputs
The log line that suspends a job SHALL say that the job does not run again until its input changes. It SHALL name a webhook, a change of an issue and a comment of a person as the new inputs.

#### Scenario: The line names the comment
- **WHEN** a job fails its limit of rounds
- **THEN** the log line that suspends the job contains `a comment of a person`

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
