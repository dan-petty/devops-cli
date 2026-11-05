## MODIFIED Requirements

### Requirement: The check takes the items that need one, in order
`devops roadmap alternatives` SHALL take an open Item whose Status is New or Ready and whose author the jobs trust (`roadmap-author-trust`). A trusted author is a person with write access, the Service App's bot or `github-actions[bot]`. For an item of a bot, the job SHALL take the item only when the approval of refine's review holds. The job SHALL take no other item. It SHALL take the items with no check first, lowest number first, then the items whose last check is older than `roadmap.alternatives.recheck_days` (default 30) or whose body changed since the check, the oldest check first. `--limit` (default 5) SHALL cap the run.

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
- **WHEN** one item is In Progress, one is Blocked, and one was opened by an account with no write access that the jobs do not trust
- **THEN** the run checks none of them

#### Scenario: An item of a bot
- **WHEN** the Service App's bot opened item 3 and item 4, refine's review approved item 3, and no review approved item 4
- **THEN** the run checks item 3 and does not check item 4

#### Scenario: An item of a bot whose body changed after the review
- **WHEN** the Service App's bot opened item 3, refine's review approved it, and a person edited its body since
- **THEN** the run does not check item 3 until a refine round reviews the new body

#### Scenario: An item whose check failed lately
- **WHEN** item 5 has no check, its last check failed 1 day ago, and `roadmap.alternatives.retry_days` is 3
- **THEN** the run does not check item 5

#### Scenario: An item whose check failed long ago
- **WHEN** item 5 has no check, its last check failed 4 days ago, and `roadmap.alternatives.retry_days` is 3
- **THEN** the run checks item 5 in the order of an item with no check

### Requirement: The request holds the item and the replies
The request to the model SHALL hold the item's title, its body without the record block and without the job's block, and the budget. It SHALL also hold the comments of trusted authors after the job's last comment, or every comment of trusted authors when the job left none. A trusted author is a person with write access or the Service App's bot (`roadmap-author-trust`). A comment of any other account SHALL NOT reach the model.

#### Scenario: A request
- **WHEN** an item with a body, a job block and two comments after the job's last comment is checked
- **THEN** the request holds the title, the body without the block, the two comments in `replies`, and the budget of `CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES` searches and `CONST_ROADMAP_ALTERNATIVES_MAX_FACT_READS` fact reads

#### Scenario: A comment of an account that the jobs do not trust
- **WHEN** an account with the association NONE, `dependabot[bot]` and the owner comment on an item, and the first account also writes the marker of the job
- **THEN** the `replies` of the request hold the comment of the owner only
