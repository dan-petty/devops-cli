## ADDED Requirements

### Requirement: Job comments in alternatives request
The alternatives request SHALL keep comments of other roadmap jobs in a separate `job_comments` list, labeled with the name of each job. It SHALL NOT put job comments in `replies`.

#### Scenario: An intake reason reaches the request
- **WHEN** the item has an intake reason comment and the alternatives request is built
- **THEN** the request holds the comment in `job_comments` with job `intake`.

#### Scenario: A person reply and a job comment on one item
- **WHEN** the item has one person reply and one intake reason comment
- **THEN** the `replies` list holds only the person reply and the `job_comments` list holds only the intake reason comment.

### Requirement: Comment window for alternatives
The alternatives request SHALL show the newest comments whole, SHALL give one index line for each older comment, and SHALL name `read_comment` when comments do not all fit.

#### Scenario: Comments exceed token room
- **WHEN** the comments of the item exceed the token room of the alternatives request
- **THEN** the newest comment is whole, each older comment has an index line, and the request names `read_comment`.

### Requirement: Read a job comment in full
The `read_comment` tool of alternatives SHALL return the whole text of a job comment when given its number.

#### Scenario: Model reads an indexed job comment
- **WHEN** the model calls `read_comment` with the number of an older job comment
- **THEN** the tool returns the whole text of that comment.
