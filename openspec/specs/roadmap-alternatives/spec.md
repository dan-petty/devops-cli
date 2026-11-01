# roadmap-alternatives Specification

## Purpose
The check of `devops roadmap alternatives`: which open items it takes and in what order, how the agent run finds an open, maintained tool for an item, what the job validates in the reply, and what it writes to the issue.

## Requirements

### Requirement: The check takes the items that need one, in order
`devops roadmap alternatives` SHALL take an open Item whose Status is New or Ready and whose author has write access to the repository (`CONST_ROADMAP_TRUSTED_AUTHORS`), and SHALL take no other item. It SHALL take the items with no check first, lowest number first, then the items whose last check is older than `roadmap.alternatives.recheck_days` (default 30) or whose body changed since the check, the oldest check first. `--limit` (default 5) SHALL cap the run.

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

### Requirement: One item can be named
`--item` SHALL check the one item it names whenever it is open, whoever opened it and whatever its Status, and SHALL check no other item.

#### Scenario: An item named by number
- **WHEN** `--item` names an open item that an account with no write access opened and that was checked 2 days ago
- **THEN** the run checks that item and no other item

### Requirement: The agent finds facts with three tools only
The check of one item SHALL be one agent run with the tools `search_web`, `github_repository` and `pypi_package`. `search_web` SHALL run at most `CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES` searches of 5 results each, and the two fact tools SHALL make at most `CONST_ROADMAP_ALTERNATIVES_MAX_FACT_READS` reads together. A tool SHALL answer a failed read, or a read over its limit, as text.

#### Scenario: The search limit
- **WHEN** the model calls `search_web` four times for one item
- **THEN** three calls search and the fourth answers that the limit is reached

#### Scenario: A PyPI package that states its license in a field other than the SPDX expression
- **WHEN** the model calls `pypi_package` for a package whose `license_expression` is empty and whose `license` holds a short name
- **THEN** the answer gives that name as the license, and when `license` holds a whole text or nothing, the name in the package's `License ::` classifier, and "not stated" only when none of the three holds a name

#### Scenario: A repository with no release
- **WHEN** the model calls `github_repository` for a repository that has no release
- **THEN** the answer gives the license, the last push and the star count, and says that the repository has no release

### Requirement: The request holds the item and the replies
The request to the model SHALL hold the item's title, its body without the record block and without the job's block, the comments after the job's last comment, or every comment when the job left none, and the budget.

#### Scenario: A request
- **WHEN** an item with a body, a job block and two comments after the job's last comment is checked
- **THEN** the request holds the title, the body without the block, the two comments in `replies`, and the budget of 3 searches and 6 fact reads

### Requirement: The job sets whether a tool is maintained
The job SHALL set `maintained` from the facts that a tool read, and the model SHALL NOT write it. A tool SHALL be maintained when its repository is not archived and its last push is within 12 months, or, for a PyPI package whose repository no tool read, when its latest upload is within 12 months.

#### Scenario: An archived repository
- **WHEN** the reply names a covering tool whose repository is archived
- **THEN** the check records the tool as not maintained

#### Scenario: A repository that is quiet for two years
- **WHEN** the reply names a covering tool whose last push was two years ago
- **THEN** the check records the tool as not maintained

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

### Requirement: The comment gives the verdict and its evidence
The comment SHALL give the verdict, the tool with its license, its last activity, whether it is maintained and its URL, what it covers and lacks, and the searches run.

#### Scenario: A comment
- **WHEN** a check ends with a covering tool
- **THEN** the comment names the verdict, the tool, its license, its last push, its maintained state, its URL, the lists of covers and lacks, and the queries run

### Requirement: The model's text makes no live link or marker
The text of the model in the comment and the block SHALL make no image, no HTML tag, no mention, no link to a URL that no tool returned, and no comment marker.

#### Scenario: A reply with a mention and a forged marker
- **WHEN** the reply lists `@someone` and `<!-- devops roadmap alternatives -->` in what the tool covers
- **THEN** the comment holds the mention in a code span, holds no second marker, and the block holds no marker of its own except its two

#### Scenario: A second run within the recheck window
- **WHEN** a run with `--confirm` repeats within `roadmap.alternatives.recheck_days` on an item whose body did not change
- **THEN** the run makes no model call and writes nothing

#### Scenario: A person replies
- **WHEN** a person comments after the job's comment and a later check runs
- **THEN** the request to the model holds that comment in `replies`

### Requirement: The check is off without a public repository and a key
The check SHALL be off when the repository is private, when its visibility cannot be read, or when no Firecrawl key is set. The plan SHALL say why, and the run SHALL make no model call, no search and no write.

#### Scenario: A private repository
- **WHEN** the repository is private
- **THEN** the plan says that the check is off because the repository is private, and no search runs

#### Scenario: No Firecrawl key
- **WHEN** the repository is public and no Firecrawl key is set
- **THEN** the plan says that no Firecrawl key is set, and no search runs

### Requirement: A dry run makes no request
`devops roadmap alternatives --dry-run` SHALL make no request, and SHALL print the requests a run makes, with the exact `gh` command of each GitHub request and the URL of each Firecrawl and PyPI request.

#### Scenario: A dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** it exits 0 after it makes no GitHub, model, Firecrawl or PyPI request, and its output lists the requests a run makes

### Requirement: The recheck window is a setting
The setting `roadmap.alternatives.recheck_days` SHALL be an integer of at least 1, default 30, and SHALL decide when a check is old.

#### Scenario: A short window
- **WHEN** the setting is 7 and an item was checked 10 days ago
- **THEN** the run checks the item again

### Requirement: The limit of a round is a setting
`roadmap.alternatives.limit` (default 5, at least 1) SHALL be the number of items that the row and `devops roadmap alternatives` check in one run. `--limit` SHALL replace it for one run of the command.

#### Scenario: The command without --limit
- **WHEN** `roadmap.alternatives.limit` is 2 and `devops roadmap alternatives` runs without `--limit` on 4 unchecked items
- **THEN** the plan checks 2 items

#### Scenario: The command with --limit
- **WHEN** `roadmap.alternatives.limit` is 2 and the command runs with `--limit 3` on 4 unchecked items
- **THEN** the plan checks 3 items

### Requirement: Each written check counts once by its verdict
The job SHALL add 1 to the counter `devops_cli_roadmap_alternatives_total` with the attribute `verdict` for each check it writes, and SHALL count no plan that it does not write, no check it skips and no failed check.

#### Scenario: Two written checks
- **WHEN** a run writes one `covers` check and one `none` check
- **THEN** the counter has one point with `verdict` `covers` and one with `verdict` `none`

#### Scenario: A plan that is not applied
- **WHEN** a run only plans a check and does not apply it
- **THEN** the counter has no point

#### Scenario: A check skipped because the body changed
- **WHEN** a person edits the body between the read and the write of a check
- **THEN** the job writes no check and counts none

### Requirement: The Service runs the check twice a day
The due table of the roadmap SHALL hold the row `alternatives` in `MODEL_LANE_ROWS`, after `refine`. The row SHALL be due on a first run and every `DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES` (719) after its last success, and SHALL be due by no webhook hint. It SHALL check at most `roadmap.alternatives.limit` items in a round, and SHALL fail the round only when it tried items and checked none. `devops roadmap run --dry-run` SHALL list the row when it is due.

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
The setting `roadmap.alternatives.retry_days` SHALL be an integer of at least 1, default 3, and and the selection SHALL NOT take an item whose last check failed less than that many days ago, unless `--item` names it.

#### Scenario: The default
- **WHEN** the setting is not set
- **THEN** it is 3, and a value of 0 is refused

#### Scenario: A longer delay
- **WHEN** the setting is 7 and the check of an item failed 4 days ago
- **THEN** the run does not check the item
