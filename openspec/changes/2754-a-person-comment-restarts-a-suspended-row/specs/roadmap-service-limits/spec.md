## ADDED Requirements

### Requirement: A comment of a person starts a suspended job again
The input of a job that failed a round SHALL hold the creation time of the newest comment of a person on an issue or a pull request of its repository, when that comment is not older than the last success of the job. A new comment of a person SHALL make the input differ from the input of the failed rounds, so a suspended job runs again and counts its failed rounds from one. A comment made before the last success, and a poll with no new comment, SHALL leave the input as it was.

#### Scenario: A person comments on a suspended job
- **WHEN** a job has failed its limit of rounds, a person with the association OWNER then comments on an issue of its repository, and a poll follows
- **THEN** the job runs again in that round

#### Scenario: A restarted job counts from one
- **WHEN** a job runs again after a comment of a person and keeps failing with no further comment
- **THEN** the job runs for its limit of rounds and then does not run

#### Scenario: A poll with no new comment
- **WHEN** a job has failed its limit of rounds with a comment of a person in its input, and two polls follow with no new comment
- **THEN** the job does not run at either poll

#### Scenario: A comment made before the last success
- **WHEN** a person comments, the job then succeeds once, and the job then fails its limit of rounds
- **THEN** the job does not run at the next poll

### Requirement: Only a person with write access is a person
A person SHALL be an author whose association is OWNER, MEMBER or COLLABORATOR, whose login does not end in `[bot]`, and who is not the account that the process acts as. A comment of any other author SHALL leave the input of a suspended job as it was.

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

### Requirement: A round reads the comments once, and only for a job that failed
A round SHALL read the comments of its repository only when a job that may run in the round holds a failed round. It SHALL read one listing for all such jobs of the lane, newest first, from the oldest last success among them (from no limit when one of them never succeeded), and SHALL stop at the first comment of a person. A round with no failed job and a dry run SHALL read no comment. A read that fails SHALL end the round with its error and SHALL count as no failed round of a job.

#### Scenario: Three failed jobs in one lane
- **WHEN** three jobs of a lane have each failed a round, and a poll follows
- **THEN** the round asks the store for the comments once, and takes no more comment than the first of a person

#### Scenario: No failed job
- **WHEN** no job of the lane has failed a round, and a poll follows
- **THEN** the round does not read the comments

#### Scenario: A dry run
- **WHEN** a job has failed its limit of rounds and a round runs with `dry_run`
- **THEN** the round does not read the comments

#### Scenario: A failed read
- **WHEN** a job has failed a round, and the read of the comments fails in the next round
- **THEN** the round ends with the error of the read, the job does not run, and its count of failed rounds is as it was

### Requirement: The store lists the comments of the repository newest first
`GitHubRoadmapStore.comments_since` SHALL read `repos/<repo>/issues/comments` with `sort=created`, `direction=desc`, the `since` time in UTC when one is given, and 100 comments a page. It SHALL ask for a page only when the caller needs a comment of it, so a caller that stops at the first comment that it wants sends no request for another page.

#### Scenario: The listing path
- **WHEN** a caller reads the comments since 2026-11-05 12:00 UTC
- **THEN** the store sends one request for `issues/comments?sort=created&direction=desc&since=2026-11-05T12:00:00Z&per_page=100`, and each comment holds its author login, association and creation time

#### Scenario: No time
- **WHEN** a caller reads the comments with no `since` time
- **THEN** the request has no `since` parameter

#### Scenario: A caller that stops at the first comment
- **WHEN** the first page links a next page and the caller takes only the first comment
- **THEN** the store sent one request

### Requirement: The suspension line names the new inputs
The log line that suspends a job SHALL say that the job does not run again until its input changes, and SHALL name a webhook, a change of an issue and a comment of a person as the new inputs.

#### Scenario: The line names the comment
- **WHEN** a job fails its limit of rounds
- **THEN** the log line that suspends the job contains `a comment of a person`
