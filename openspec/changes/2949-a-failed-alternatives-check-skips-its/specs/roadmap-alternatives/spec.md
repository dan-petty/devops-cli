## MODIFIED Requirements

### Requirement: The check takes the items that need one, in order
`devops roadmap alternatives` SHALL take an open Item whose Status is New or Ready and whose author has write access to the repository (`CONST_ROADMAP_TRUSTED_AUTHORS`), and SHALL take no other item. It SHALL take the items with no check first, lowest number first, then the items whose last check is older than `roadmap.alternatives.recheck_days` (default 30) or whose body changed since the check, the oldest check first. It SHALL NOT take an item whose last check failed less than `roadmap.alternatives.retry_days` (default 3) days ago, and `--limit` (default 5) SHALL cap the run.

#### Scenario: Unchecked items come before stale items
- **WHEN** item 4 was checked 40 days ago, items 7 and 9 have no check, item 6 was checked 2 days ago with an unchanged body, and the run has `--limit 3`
- **THEN** the run checks items 7, 9 and 4, in that order, and does not check item 6

#### Scenario: A changed body is checked again
- **WHEN** item 3 was checked 2 days ago and a person edited its body since
- **THEN** the run checks item 3

#### Scenario: Only the job's own text changed
- **WHEN** item 3 was checked 2 days ago and only the job's block and the refine section of its body changed since
- **THEN** the run does not check item 3

#### Scenario: A started, blocked or untrusted item is left out
- **WHEN** one item is In Progress, one is Blocked, and one was opened by an account with no write access
- **THEN** the run checks none of them

#### Scenario: An item whose check failed lately
- **WHEN** item 5 has no check, its last check failed 1 day ago, and `roadmap.alternatives.retry_days` is 3
- **THEN** the run does not check item 5

#### Scenario: An item whose check failed long ago
- **WHEN** item 5 has no check, its last check failed 4 days ago, and `roadmap.alternatives.retry_days` is 3
- **THEN** the run checks item 5 in the order of an item with no check

### Requirement: The job refuses a reply with a source no tool returned
The job SHALL refuse a reply whose `sources` or `tool_url` cite a URL that no tool returned in this run, and a `covers` or `partly` verdict with no tool, or with a tool whose facts no tool read. It SHALL skip that item and write no check for it, write the checks of the other items, record the failure of the skipped item, and then fail with an error that names each skipped item and its reason only when it wrote no check.

#### Scenario: A made-up URL
- **WHEN** a reply cites `https://example.com/invented` and no tool returned that URL, and the check of another item succeeds
- **THEN** the item is skipped, no check is written for it, the other item is written, and the run does not fail

#### Scenario: Not-applicable after a tool ran
- **WHEN** a reply gives the verdict `not-applicable` and the run made a search or a fact read
- **THEN** the item is skipped with a named reason and no check is written for it

#### Scenario: A model call fails
- **WHEN** the model call of one item fails and the call of another item succeeds
- **THEN** the run writes the second item and does not fail

#### Scenario: Rejected credentials
- **WHEN** the model refuses the key on the first item
- **THEN** the run stops at that item and writes nothing

#### Scenario: Every check fails
- **WHEN** the model call of each item fails
- **THEN** the run writes no check, and then fails with an error that names each item and its reason

### Requirement: A check writes a comment, a block and a record
With `--confirm`, a check SHALL post one comment with the marker `devops roadmap alternatives`, replace the block `devops-roadmap-alternatives:start` to `:end` in the body, or add it at the end, and record `alternatives.checked_at`, `alternatives.body_hash`, `alternatives.verdict` and `alternatives.tool` in the job record. The check SHALL NOT change a label and SHALL NOT close the issue.

#### Scenario: A marker with no partner
- **WHEN** the body holds the start marker of the block with no end marker, or the end marker with no start marker before it
- **THEN** the item is skipped with a named reason, no comment and no block is written for it, and the person's text is not changed

#### Scenario: Refine ignores the job's writes
- **WHEN** the job has written its block and its comment on an item that refine left waiting on a person
- **THEN** refine hashes the body without the block, takes the comment as no reply, and the item still waits and no model call is made

#### Scenario: A covering tool
- **WHEN** a run with `--confirm` checks an item and the reply names a maintained covering tool whose facts were read
- **THEN** the issue has one comment with the marker, its body has one block with the verdict and the tool, its job record has the four keys, its labels are unchanged and it is open

### Requirement: The Service runs the check twice a day
The due table of the roadmap SHALL hold the row `alternatives` in `MODEL_LANE_ROWS`, after `refine`. The row SHALL be due on a first run and every `DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES` (719) after its last success, and SHALL be due by no webhook hint. It SHALL check at most `roadmap.alternatives.limit` items in a round, and SHALL fail the round, once the failures are recorded, only when it tried at least one item and checked none. A round that selects no item SHALL NOT fail. `devops roadmap run --dry-run` SHALL list the row when it is due.

#### Scenario: A first run
- **WHEN** a round runs on a roadmap whose `schedule.json` holds no success of the row
- **THEN** the row runs once, after `refine`, with the job's plan and apply functions

#### Scenario: Twice a day
- **WHEN** the row succeeded 2 hours ago and a round runs
- **THEN** the row does not run, and when the row succeeded 13 hours ago it runs

#### Scenario: A webhook hint
- **WHEN** a round runs with a webhook hint that makes intake due and the row succeeded 2 hours ago
- **THEN** the row does not run

#### Scenario: The limit of a round
- **WHEN** `roadmap.alternatives.limit` is 2 and 4 items have no check
- **THEN** the round checks the 2 lowest numbers

#### Scenario: A failed check
- **WHEN** the model call for one item fails and the call for another succeeds
- **THEN** the check of the second item is written, the failure of the first is recorded, and the row succeeds

#### Scenario: Every check fails
- **WHEN** the model call for each of 2 items fails
- **THEN** the failure of each item is recorded and the row fails, naming both

#### Scenario: A round with no item to check
- **WHEN** every eligible item has a current check or a failure inside its delay
- **THEN** the row makes no model call and succeeds

#### Scenario: A dry run lists the row
- **WHEN** `devops roadmap run --dry-run` runs on a roadmap whose rows are all due
- **THEN** its `Due:` line ends with `alternatives`, after `refine`

## ADDED Requirements

### Requirement: A failed check is recorded and tried again later
`devops roadmap alternatives --confirm` and the row SHALL record each failed check, whether a failed model call, a stopped run or a refused reply, in the job record of its item with `alternatives.failed_at` (the time of the failure) and `alternatives.failed_error` (the class of the error). A written check SHALL clear both keys. The reason of a stopped run SHALL hold the class of the error and its masked message, and the job record SHALL hold no text of the model.

#### Scenario: One of five checks fails
- **WHEN** the row runs on 5 items without a check and the model call of one item fails
- **THEN** the round succeeds, 4 checks are written, and the job record of the failed item holds the time of the round and the class `AIClientError`, and the item has no comment and no block

#### Scenario: A stopped run
- **WHEN** the run of an item stops with `UsageLimitExceeded`
- **THEN** the job record holds the class `UsageLimitExceeded`, and the reason in the report names the class and the message of the stop

#### Scenario: A retry after the delay
- **WHEN** the check of an item failed 4 days ago with `roadmap.alternatives.retry_days` at 3, and the next round checks it successfully
- **THEN** a check is written for the item and `alternatives.failed_at` and `alternatives.failed_error` are cleared

#### Scenario: A retry before the delay
- **WHEN** the check of an item failed 1 day ago with `roadmap.alternatives.retry_days` at 3, and a round runs
- **THEN** the round makes no model call for the item and its job record is unchanged

#### Scenario: A plan that is not applied
- **WHEN** a run only plans the checks and one check fails
- **THEN** the job record of the item is unchanged

### Requirement: The retry delay is a setting
The setting `roadmap.alternatives.retry_days` SHALL be an integer of at least 1, default 3, and SHALL decide how long after a failed check the item is left out of the selection.

#### Scenario: The default
- **WHEN** the setting is not set
- **THEN** it is 3, and a value of 0 is refused

#### Scenario: A longer delay
- **WHEN** the setting is 7 and the check of an item failed 4 days ago
- **THEN** the run does not check the item
