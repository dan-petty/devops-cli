## ADDED Requirements

### Requirement: The stop report is on the issue once
On a stop, the job SHALL post the stop comment on the issue before it writes the comment of the run on the pull request. The stop comment SHALL be the one copy of the stop report: the failure class, the table of the steps, the end of the check log, the reason, the last message of the agent, the discarded diff and the retry instructions.

#### Scenario: A stop after a push
- **WHEN** group 1 passes and is pushed, and the step of group 2 stops
- **THEN** the stop comment on the issue holds the table of the steps once, and the comment of the run on the pull request holds no table and no failure class

### Requirement: The comment of a stopped run links the stop comment
When the pull request exists, the comment of a stopped run SHALL hold the line "Stopped at <step>. The stop report is on #<issue>: <url>." with the page of the stop comment, and the lines that only it holds: the amendments, the skipped steps, the scoped runs, the strength and check lines, and the comments that the steps read. A run that finishes SHALL keep its table in the comment of the run.

#### Scenario: A stop after a push
- **WHEN** group 1 passes and is pushed, and the step of group 2 stops
- **THEN** the comment of the run on the pull request holds the line "Stopped at group 2. The stop report is on #<issue>: <url>." with the page of the stop comment

#### Scenario: A run that finishes
- **WHEN** both groups pass and the pull request is ready
- **THEN** the comment of the run on the pull request holds a row for each step

### Requirement: A refused repeat gives the page of the earlier comment
The roadmap store SHALL give the page of a comment that it posts and say that it posted it. For a comment that it refuses as a repeat, it SHALL give the page of the earlier comment that holds the same text and say that it posted nothing. A stop comment that the store refuses SHALL be linked by that page.

#### Scenario: A refused repeat of a comment
- **WHEN** the store refuses a comment of a job as a repeat of its earlier comment
- **THEN** the store gives the page of the earlier comment and says that it posted nothing

### Requirement: The dry run lists the writes of a stop in order
The dry run of the implement job SHALL list the writes of a stop in this order: the comment on the item, the comment of the run on the pull request, the Status. It SHALL list the writes of a finished run in this order: the Status, the comment on the item.

#### Scenario: The plan of the writes
- **WHEN** a person reads the plan of `devops roadmap implement --dry-run`
- **THEN** the writes under the condition of a stop list the comment on the item, the comment of the run and the Status, in that order

### Requirement: A retry of a person clears one stop
A comment `implement: retry` of a trusted person SHALL clear one stop. The comment of the clear SHALL follow the retry, so a later stop SHALL wait for a new retry, and the round SHALL create no Job for it.

#### Scenario: A second stop after a retry
- **WHEN** the runner stops an item, the owner comments `implement: retry`, the round clears the stop and creates a Job, and the runner of that Job stops the item again
- **THEN** the item stays Blocked, the round created two Jobs in all, and one comment names the retry rule
