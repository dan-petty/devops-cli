# roadmap-alternatives Specification

## Purpose
The check of `devops roadmap alternatives`: which open items it takes and in what order, how the agent run finds an open, maintained tool for an item, what the job validates in the reply, and what it writes to the issue.

## Requirements

### Requirement: The check takes the items that need one, in order
`devops roadmap alternatives` SHALL take an open Item whose Status is New or Ready and that passes the check of `roadmap-author-trust`, and SHALL take no other item. It SHALL take the items with no check first, lowest number first, then the items whose last check is older than `roadmap.alternatives.recheck_days` (default 30) or whose body changed since the check, the oldest check first. `--limit` (default 5) SHALL cap the run.

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
The request to the model SHALL hold the item's title, its body without the record block and without the job's block, and the budget. It SHALL also hold the comments of trusted authors after the job's last comment, or every comment of trusted authors when the job left none. A trusted author is a person with write access or the Service App's bot (`roadmap-author-trust`). A comment of any other account SHALL NOT reach the model.

#### Scenario: A request
- **WHEN** an item with a body, a job block and two comments after the job's last comment is checked
- **THEN** the request holds the title, the body without the block, the two comments in `replies`, and the budget of `CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES` searches and `CONST_ROADMAP_ALTERNATIVES_MAX_FACT_READS` fact reads

#### Scenario: A comment of an account that the jobs do not trust
- **WHEN** an account with the association NONE, `dependabot[bot]` and the owner comment on an item, and the first account also writes the marker of the job
- **THEN** the `replies` of the request hold the comment of the owner only

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
With `--confirm`, a check SHALL replace the block `devops-roadmap-alternatives:start` to `:end` in the body, or add it at the end, and record `alternatives.checked_at`, `alternatives.body_hash`, `alternatives.verdict` and `alternatives.tool` in the job record. The check SHALL NOT change a label and SHALL NOT close the issue.

#### Scenario: A marker with no partner
- **WHEN** the body holds the start marker of the block with no end marker, or the end marker with no start marker before it
- **THEN** the item is skipped with a named reason, no comment and no block is written for it, and the person's text is not changed

#### Scenario: Refine ignores the job's writes
- **WHEN** the job has written its block and its comment on an item that refine left waiting on a person
- **THEN** refine hashes the body without the block, takes the comment as no reply, and the item still waits and no model call is made

#### Scenario: A covering tool
- **WHEN** a run with `--confirm` checks an item and the reply names a maintained covering tool whose facts were read
- **THEN** the issue has one comment with the marker, its body has one block with the verdict and the tool, its job record has the four keys, its labels are unchanged and it is open

### Requirement: A check posts its comment only for a first or changed result
A check SHALL post one comment with the marker `devops roadmap alternatives` when the job record holds no `alternatives.verdict`, or when the verdict or the tool of the check differs from the recorded `alternatives.verdict` or `alternatives.tool`. A check with the same verdict and the same tool SHALL post no comment and SHALL still write the block and the record, so `alternatives.checked_at` moves.

#### Scenario: A first check
- **WHEN** a check ends for an item whose job record holds no `alternatives.verdict`
- **THEN** the check posts its comment

#### Scenario: A recheck with the same result
- **WHEN** a recheck ends with the verdict and the tool that the job record holds
- **THEN** the check posts no second comment, the block shows the new date, `alternatives.checked_at` holds the new time, and the next selection does not take the item before the recheck days pass

#### Scenario: A recheck with a new verdict or a new tool
- **WHEN** a recheck ends with a verdict that differs from the record, or with a tool that differs from the record, or with a tool where the record holds none
- **THEN** the check posts one comment and records the new verdict, the new tool and the new date

### Requirement: The comment gives the verdict and its evidence
The comment SHALL give the verdict, the reason of the verdict in the model's words, the tool with its license, its last activity, whether it is maintained and its URL, and what it covers and lacks. The model SHALL give a reason in every reply, and the job SHALL refuse a reply with none.

#### Scenario: A comment
- **WHEN** a check ends with a covering tool
- **THEN** the comment names the verdict, the reason, the tool, its license, its last push, its maintained state, its URL, the lists of covers and lacks, the tools considered, and the queries run

#### Scenario: A reply with no reason
- **WHEN** the model replies with no reason
- **THEN** the reply fails the schema of the output and the model is asked again

### Requirement: The comment lists the searches and the tools considered
The comment SHALL list every tool whose facts the run read with its URL, license and last activity, and each search that a provider answered with its number of results.

#### Scenario: Two searches with results
- **WHEN** a run makes two searches and the fake search returns two results each
- **THEN** the comment lists each query with `results: 2`

#### Scenario: Two tools read
- **WHEN** the run reads the facts of two repositories and names one as the tool
- **THEN** the comment lists both under `Tools considered:`, each with its license and last activity

### Requirement: The comment shows at most five sources
The comment SHALL show at most five sources, and SHALL say how many more it leaves out.

#### Scenario: More sources than the bound
- **WHEN** the reply cites eight sources that the tools returned
- **THEN** the comment shows five and the line `3 more sources are left out`

### Requirement: A check never changes an earlier comment
A check SHALL add a new comment and SHALL NOT change the comment of an earlier check.

#### Scenario: A later check
- **WHEN** a second check of the same item writes its comment
- **THEN** the item has two comments and the first is unchanged

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

### Requirement: A dry run makes no request
`devops roadmap alternatives --dry-run` SHALL make no request, and SHALL print the requests a run makes, with the exact `gh` command of each GitHub request, the URL of the request of the first configured search provider and the URL of each PyPI request.

#### Scenario: A dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** it exits 0 after it makes no GitHub, model, search or PyPI request, and its output lists the requests a run makes

### Requirement: The recheck window is a setting
The setting `roadmap.alternatives.recheck_days` SHALL be an integer of at least 1, default 30, and SHALL decide when a check is old.

#### Scenario: A short window
- **WHEN** the setting is 7 and an item was checked 10 days ago
- **THEN** the run checks the item again

### Requirement: The limit of a round is a setting
`roadmap.alternatives.limit` (default 5, at least 1) SHALL be the number of items that the row and `devops roadmap alternatives` check in one run when every eligible item has a check. `roadmap.alternatives.first_pass_limit` (default 20, at least 1) SHALL be that number while an eligible item has no check and its last check did not fail inside `roadmap.alternatives.retry_days`. `--limit` SHALL replace either for one run of the command.

#### Scenario: The command without --limit
- **WHEN** `roadmap.alternatives.limit` is 2 and `devops roadmap alternatives` runs without `--limit` on 4 items that have a check older than `roadmap.alternatives.recheck_days`
- **THEN** the plan checks the 2 items with the oldest checks

#### Scenario: The command with --limit
- **WHEN** `roadmap.alternatives.first_pass_limit` is 20 and the command runs with `--limit 3` on 4 unchecked items
- **THEN** the plan checks 3 items

#### Scenario: A first pass
- **WHEN** 25 items have no check, `roadmap.alternatives.limit` is 5 and `roadmap.alternatives.first_pass_limit` is 20
- **THEN** the plan checks the 20 lowest numbers

#### Scenario: Every item has a check
- **WHEN** 8 items have a check older than `roadmap.alternatives.recheck_days`, `roadmap.alternatives.limit` is 5 and `roadmap.alternatives.first_pass_limit` is 20
- **THEN** the plan checks 5 items

#### Scenario: Items with a check join a first pass
- **WHEN** 3 items have no check, 10 items have a check older than `roadmap.alternatives.recheck_days`, and the two limits are 5 and 20
- **THEN** the plan checks the 3 unchecked items and then the 10 with the oldest checks

#### Scenario: A failed item does not hold the first pass
- **WHEN** the only 2 items with no check failed 1 day ago, `roadmap.alternatives.retry_days` is 3, and 8 items have a check older than `roadmap.alternatives.recheck_days`
- **THEN** the plan checks 5 items

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
The due table of the roadmap SHALL hold the row `alternatives` in `MODEL_LANE_ROWS`, after `refine`. The row SHALL be due on a first run and every `DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES` (719) after its last success, and SHALL be due by no webhook hint. It SHALL check in a round the items that the limit of a round allows, and SHALL fail the round only when it tried items and checked none. `devops roadmap run --dry-run` SHALL list the row when it is due.

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
- **WHEN** `roadmap.alternatives.limit` is 2 and 4 items have a check older than `roadmap.alternatives.recheck_days`
- **THEN** the round checks the 2 items with the oldest checks

#### Scenario: A round of the first pass
- **WHEN** 25 items have no check and the two limits are 5 and 20
- **THEN** the round checks the 20 lowest numbers and writes their checks

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

### Requirement: A skip-class item is not-applicable with no model call
The check SHALL give the verdict `not-applicable`, with no model call and no search, to an item whose title has the Conventional Commit type `test`, `docs`, `refactor`, `chore`, `ci` or `perf`, and to an item whose title has the type `fix` and whose body holds the text `Traceback (most recent call last)`. The comment and the block of the body SHALL name the class: the type, or `fix-with-stack-trace`. An item of any other type, and an item with no type, SHALL NOT be a skip class.

#### Scenario: Each type is a skip class
- **WHEN** the check runs on six items whose titles have the types `test`, `docs`, `refactor`, `chore`, `ci` and `perf`
- **THEN** each check has the verdict `not-applicable`, each comment names the type, and the model received no request and no search ran

#### Scenario: The base rule of one agent run holds for non-skip items only
- **WHEN** the check runs on a skip-class item
- **THEN** no agent run happens for it, and the rule "The check of one item SHALL be one agent run" of the requirement "The agent finds facts with three tools only" holds for an item that is not a skip class

#### Scenario: A fix with a stack trace
- **WHEN** the check runs on an item titled `fix(roadmap): a crash` whose body holds `Traceback (most recent call last)`
- **THEN** the check has the verdict `not-applicable`, the comment names `fix-with-stack-trace`, and the model received no request

#### Scenario: A fix with no stack trace
- **WHEN** the check runs on an item titled `fix(roadmap): a crash` whose body holds no traceback
- **THEN** the model receives a request for the item

#### Scenario: A type that is no skip class
- **WHEN** the check runs on items whose titles have the types `feat`, `build` and `style`, and on an item whose title has no type
- **THEN** the model receives a request for each of them

#### Scenario: A skip class with an unpaired marker
- **WHEN** the body of a skip-class item holds the start marker of the block with no end marker
- **THEN** the item is skipped with a named reason and nothing is written for it

### Requirement: A non-skip item needs a search before any verdict
For an item that is no skip class, the check SHALL refuse a reply that follows no answered `search_web` call, and SHALL give the model one more turn to search. A second reply that follows no answered search SHALL end as a failed check: the job skips the item with a named reason and writes nothing for it. The check SHALL refuse a reply with the verdict `not-applicable` from the model, because the job sets that verdict for a skip class only.

#### Scenario: A reply with no search gets one more turn
- **WHEN** the model answers a `feat` item with the verdict `none` and no search, then searches, then answers with the verdict `none`
- **THEN** the model received three requests, the check is written with the query of the search, and the counter `devops_cli_web_searches_total` has a point

#### Scenario: Two replies with no search
- **WHEN** the model answers a `feat` item twice with a verdict and no search
- **THEN** the model received two requests, the item is skipped with the reason that the reply gives a verdict with no answered search, and nothing is written for it

#### Scenario: A not-applicable reply from the model
- **WHEN** the model searches for a `feat` item and then answers with the verdict `not-applicable`
- **THEN** the item is skipped with the reason that the job sets `not-applicable` for a skip class only, and nothing is written for it

### Requirement: The check reads the context window of the analysis task
The run of one item SHALL pass the context window of the `analysis` task to the investigation, so that the window ends the tools of the run before the counts do.

#### Scenario: The window reaches the run
- **WHEN** an item is checked and the window of the `analysis` task is 65536 tokens
- **THEN** the investigation gets the window 65536

### Requirement: The check reads the ADRs of the repository
The check SHALL list the files of `docs/adr/` on the default branch once for a run, before it selects the items. It SHALL read each file named with four digits, a hyphen and a name that ends with `.md`, and keep its number, its title, its front matter and its `Considered Options` section. It SHALL read the status from the front matter, never from prose. A failed read or a front matter that does not validate SHALL stop the run, but a missing directory SHALL NOT.

#### Scenario: A file that is no ADR
- **WHEN** `docs/adr/` holds `README.md` and `0009-third.md`
- **THEN** the check keeps the third ADR only

#### Scenario: An ADR with no options
- **WHEN** an ADR has a title and no `Considered Options` section
- **THEN** the check keeps its number and its title and no options text

#### Scenario: A front matter that is not valid
- **WHEN** the front matter of `docs/adr/0011-old.md` holds an unknown key, an unknown status, or a record number that is not a quoted string of four digits
- **THEN** the read stops with an error that names `docs/adr/0011-old.md`

#### Scenario: A run of skip-class items
- **WHEN** every selected item is a skip class
- **THEN** the run reads `docs/adr/` once and makes no model call

#### Scenario: A failed read
- **WHEN** GitHub fails the read of `docs/adr/` with a server error
- **THEN** the run stops with that error and writes no check

#### Scenario: A dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** its output lists the read of `docs/adr` and the read of each file of it, with the `gh` command of each

### Requirement: The check leaves out an ADR that a later ADR supersedes
The check SHALL keep only the ADRs in force: an ADR whose `status` is `accepted`, or that has no status, whose `superseded-by` is empty and whose number no `supersedes` of another ADR names. Either ADR of a supersession can say so in its front matter. An ADR that another ADR amends SHALL stay.

#### Scenario: The older ADR says so
- **WHEN** ADR 0001 has `superseded-by: ["0002"]` and ADR 0002 has no `supersedes`
- **THEN** the check keeps ADR 0002 and leaves out ADR 0001

#### Scenario: The newer ADR says so
- **WHEN** ADR 0005 has `supersedes: ["0004"]` and ADR 0004 has no `superseded-by`
- **THEN** the check leaves out ADR 0004

#### Scenario: An ADR that is not accepted
- **WHEN** ADRs have the status `proposed`, `rejected`, `deprecated` and `superseded`, an ADR has `status: accepted` and an ADR has no front matter
- **THEN** the check keeps the accepted ADR and the ADR with no front matter only

#### Scenario: An ADR that a later ADR amends or supersedes in part
- **WHEN** ADR 0004 has `amended-by: ["0014"]`, the link of an amendment or of a supersession in part, and ADR 0014 has `amends: ["0004"]`
- **THEN** the check keeps both ADRs, and the entry of ADR 0004 names ADR 0014

### Requirement: The request holds the decisions of the ADRs
The request of an item SHALL hold the key `decisions`. For each ADR in force it SHALL hold the number as four digits, the title, a line `Amended by` with each ADR of its `amended-by`, and the options, the highest number first. The text SHALL hold at most `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS` tokens. The cut SHALL take whole entries, and the job SHALL log a warning that names each ADR that the cut leaves out. A repository with no `docs/adr/` SHALL send no `decisions` key.

#### Scenario: Two ADRs
- **WHEN** the repository holds ADR 0006 with `amended-by: ["0008"]`, ADR 0007, and ADR 0008 with `supersedes: ["0007"]` and `amends: ["0006"]`
- **THEN** `decisions` holds the entry of ADR 0008, then the entry of ADR 0006, and no entry of ADR 0007
- **AND** the entry of ADR 0006 holds the line `Amended by ADR 0008.` and its options

#### Scenario: The decisions are cut to the cap
- **WHEN** the entries of the ADRs hold more tokens than `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS`
- **THEN** `decisions` holds whole entries only, starts with the ADR of the highest number, and holds no more tokens than the cap
- **AND** a warning names each ADR that the cut leaves out

#### Scenario: A repository with no ADR directory
- **WHEN** the repository has no `docs/adr/`
- **THEN** the request holds no `decisions` key, and the verdict is the one that the reply gives

### Requirement: A text names a tool in a form that says so
A text SHALL name a tool when it holds the full `owner/name` of the repository. It SHALL also name the tool when it holds a name of two words or more as a whole word. A name of one word SHALL name the tool only inside a code span, a link or strong emphasis. The job SHALL test the last segment of the repository or package name, and the `tool_name` of the reply. The test SHALL ignore case, and SHALL take a space, `-`, `_` and `.` as one separator.

#### Scenario: A name of two words
- **WHEN** a text says "the Argo Workflows controller" and the tool is `argoproj/argo-workflows`
- **THEN** the text names the tool

#### Scenario: A name of one word in a form that marks it
- **WHEN** a text says "Run `just` for the build." and the tool is `casey/just`
- **THEN** the text names the tool

#### Scenario: A common word in prose
- **WHEN** a text says "just add it" and the tool is `casey/just`
- **THEN** the text does not name the tool

#### Scenario: The owner and the name
- **WHEN** a text says "Run example/scanner now." and the tool is `example/scanner`
- **THEN** the text names the tool

#### Scenario: The display name of the reply
- **WHEN** a text says "DBOS Transact in-process", the tool is `dbos-inc/dbos-transact-py` and `tool_name` is "DBOS Transact"
- **THEN** the text names the tool

#### Scenario: A longer name
- **WHEN** a text says "add pytest-cov" and the tool is `pytest-dev/pytest`
- **THEN** the text does not name the tool

### Requirement: The model proposes rejected and the job confirms it
The reply MAY hold the key `adr`: the number of the ADR that rejected the tool of a `covers` or `partly` verdict. The job SHALL give `rejected` when the ADRs that the model saw hold that ADR and only its options that say `rejected` or `not chosen` name the tool. The check SHALL record the tool URL. The comment SHALL keep the tool line with the URL and name the ADR as four digits. The block SHALL name the ADR too.

#### Scenario: Temporal and ADR 0008
- **WHEN** ADR 0008 holds the options line "Temporal and Hatchet: rejected." in strong emphasis, and the reply gives `covers` for `https://github.com/temporalio/temporal` with `adr` 8
- **THEN** the check has the verdict `rejected`, its comment holds the tool URL and `ADR 0008`, and its block names `ADR 0008`

#### Scenario: The record
- **WHEN** a run with `--confirm` writes that check
- **THEN** the job record holds the verdict `rejected` and the tool URL
- **AND** the counter `devops_cli_roadmap_alternatives_total` has a point with the `verdict` `rejected`

#### Scenario: The display name of the tool
- **WHEN** ADR 0008 says "DBOS Transact in-process (runner-up): rejected for now.", the tool is `dbos-inc/dbos-transact-py`, and the reply gives `tool_name` "DBOS Transact" and `adr` 8
- **THEN** the check has the verdict `rejected`

#### Scenario: A rejected tool that the item names
- **WHEN** the job confirms `adr` 8 and the body of the item names the tool too
- **THEN** the check has the verdict `rejected`

#### Scenario: An ADR that adopts the tool
- **WHEN** ADR 0010 names OpenSpec in its chosen option and in two options that say "rejected", and the reply gives `covers` for `https://github.com/Fission-AI/OpenSpec` with `adr` 10
- **THEN** the check has the verdict `covers` and no ADR

### Requirement: The job drops a rejection that it cannot confirm
If the job cannot confirm the ADR of a reply, it SHALL drop the number, keep the verdict of the reply and write the check. It SHALL NOT refuse the reply for that reason. A reply with a verdict that names no tool SHALL keep its verdict.

#### Scenario: An ADR that the repository does not hold
- **WHEN** the reply gives `covers` with `adr` 99 and the repository holds no ADR 0099
- **THEN** the check has the verdict `covers` and no ADR, and refine asks its question

#### Scenario: An ADR that does not name the tool
- **WHEN** the reply gives `adr` 7 for a tool that the title and the options of ADR 0007 do not name
- **THEN** the check has the verdict of the reply and no ADR

#### Scenario: An ADR that a later ADR supersedes
- **WHEN** the reply gives `adr` 4, and ADR 0005 supersedes ADR 0004
- **THEN** the check has the verdict of the reply and no ADR

#### Scenario: An ADR that the cut left out
- **WHEN** the cut of `decisions` left out ADR 0008 and the reply gives `adr` 8
- **THEN** the check has the verdict of the reply and no ADR

#### Scenario: An ADR with a verdict of no tool
- **WHEN** the reply gives the verdict `none` and `adr` 8
- **THEN** the check has the verdict `none`

### Requirement: The model proposes in-use and the job confirms it
The reply MAY hold the key `in_use`. The job SHALL give the check the verdict `in-use` when four things hold. The reply has `in_use` true. Its verdict is `covers` or `partly`. No ADR gave `rejected`. The title or the body of the item names the tool. The job SHALL read the body outside the block of the check and outside the refine section. The check SHALL hold the tool and a line that says that the item already names it.

#### Scenario: The body names the tool
- **WHEN** the reply gives `covers` for `https://github.com/example/scanner` with `in_use` true, and the body says "Run example/scanner on each file."
- **THEN** the check has the verdict `in-use` and records the tool URL

#### Scenario: A partly verdict
- **WHEN** the reply gives `partly` for a tool that the item names, with `in_use` true
- **THEN** the check has the verdict `in-use`

#### Scenario: Only the block of the check names the tool
- **WHEN** the title and the body outside the block name no tool, and the block of an earlier check names `example/scanner`
- **THEN** the check keeps the verdict `covers`

#### Scenario: Only the refine section names the tool
- **WHEN** the body outside the refine section names no tool, and the refine section holds an open question that names the tool
- **THEN** the check keeps the verdict `covers`

#### Scenario: A common word for a name
- **WHEN** the body says "Just add the file." and the tool is `casey/just`
- **THEN** the check keeps the verdict `covers`
- **AND** a body that says "Run `just` for the build." gives the verdict `in-use`

### Requirement: The job drops an in-use flag that the text does not back
The job SHALL NOT give `in-use` from the text of the item when `in_use` is false. If `in_use` is true and the title and the body name no tool of the reply, the job SHALL drop the flag. It SHALL keep the verdict of the reply and write the check, unless the inventory holds the tool.

#### Scenario: The model gives no flag
- **WHEN** the body names the tool, the reply holds no `in_use`, and the inventory does not hold the tool
- **THEN** the check keeps the verdict `covers`

#### Scenario: The text does not name the tool
- **WHEN** the reply holds `in_use` true, the title and the body name no tool of the reply, and the inventory does not hold the tool
- **THEN** the check keeps the verdict `covers`, and refine asks its question

### Requirement: The model cannot give a verdict that the job sets
The job SHALL give a reply with the verdict `rejected`, `in-use` or `not-applicable` one more turn. The message SHALL say that the job sets the verdict, and name the keys `adr` and `in_use`. The job SHALL refuse a second reply with one of these verdicts. A refused reply SHALL skip its item with a named reason and write no check for it.

#### Scenario: A natural reply with in-use
- **WHEN** the model first gives the verdict `in-use`, and then gives `covers` with `in_use` true
- **THEN** the check is written with the verdict `in-use`, and the item is not skipped

#### Scenario: A second reply with a verdict of the job
- **WHEN** the model gives the verdict `rejected` twice
- **THEN** the item is skipped with the reason that the job sets that verdict, and no check is written for it

### Requirement: A round records the coverage of the check
The Service row SHALL record, once in each round and before the round writes, the gauge `devops_cli_roadmap_alternatives_unchecked_items` and the gauge `devops_cli_roadmap_alternatives_oldest_check_age_seconds`, with the attribute `repo`. The first counts the items that the check can take (open, Status New or Ready, trusted author) with no check, also one in the retry delay. The second is the age of the oldest check of these items. No other path SHALL record them.

#### Scenario: Six items with no check
- **WHEN** a round finds 10 items that the check can take, 4 of them with a check, and one of the other 6 failed 1 day ago
- **THEN** the gauge `devops_cli_roadmap_alternatives_unchecked_items` records 6 for the repository

#### Scenario: An item that the check cannot take
- **WHEN** an item with no check is In Progress, and another with no check is from an author with no write access
- **THEN** the gauge does not count either of them

#### Scenario: The oldest check is 72 hours old
- **WHEN** the oldest check of the items was written 72 hours before the round
- **THEN** the gauge `devops_cli_roadmap_alternatives_oldest_check_age_seconds` records 259200

#### Scenario: No item has a check
- **WHEN** no item that the check can take has a check
- **THEN** the gauge of the unchecked items records the count, and the gauge of the age records no point

#### Scenario: A round with nothing to check
- **WHEN** every item that the check can take has a current check
- **THEN** the row records the unchecked gauge 0 and the age gauge, and the model gets no request

#### Scenario: A path that is not the Service row
- **WHEN** the command runs with `--item 7`, with no `--confirm`, with `--confirm`, or on a repository where the check is off
- **THEN** neither gauge has a point

### Requirement: Each written check observes its searches
For each check that it writes, the job SHALL observe the histogram `devops_cli_roadmap_alternatives_searches` once, with the attribute `verdict` and the number of searches that a provider answered for the check. A skip-class check SHALL observe 0. The job SHALL observe nothing for a failed check, for a check skipped because a person changed the body, and for a plan that it does not apply.

#### Scenario: A check that searched three times
- **WHEN** the job writes a check with the verdict `none` after 3 answered searches
- **THEN** the histogram has the point `{verdict="none"}` with the value 3

#### Scenario: A skip-class check
- **WHEN** the job writes the check of an item titled `docs(roadmap): a change`
- **THEN** the histogram has the point `{verdict="not-applicable"}` with the value 0

#### Scenario: A check that is not written
- **WHEN** a check fails, a person changes the body between the read and the write, or a run only plans
- **THEN** the histogram has no point for that item

### Requirement: The check is off without a public repository and a search provider
The check SHALL be off when the repository is private, when its visibility cannot be read, or when no search provider is configured. The plan SHALL say why, and the run SHALL make no model call, no search and no write.

#### Scenario: A private repository
- **WHEN** the repository is private
- **THEN** the plan says that the check is off because the repository is private, and no search runs

#### Scenario: No search provider
- **WHEN** the repository is public and no search provider is configured
- **THEN** the plan says that no search provider is configured, and no search runs

### Requirement: An alternatives round writes each check when the check is done
An alternatives round SHALL write the body block, the record and the comment of check N before check N+1 starts. A kill of the worker SHALL lose at most the check in progress.

#### Scenario: Kill in item 3 of 5
- **WHEN** a round selects 5 items and the model call of the third item raises a `BaseException` that no handler catches
- **THEN** checks 1 and 2 have their body block, record and comment, and the other items have none

### Requirement: A rate limit ends an alternatives round and keeps the written checks
An alternatives round SHALL end when a write fails with a GitHub rate limit. It SHALL keep the checks that it wrote and SHALL NOT check the items after the failed one.

#### Scenario: Rate limit in check 2
- **WHEN** the write of the body of item 2 of 5 fails with a rate-limit error
- **THEN** the round raises the error, item 1 keeps its written check, and the model gets no request for items 3, 4 and 5

### Requirement: An alternatives plan writes nothing
`devops roadmap alternatives --plan` SHALL make no write to the roadmap store.

#### Scenario: Plan only
- **WHEN** the command runs with `--plan` on 3 items that have no check
- **THEN** the store receives no write

### Requirement: Only an answered search counts as a search
A search SHALL count as a search of the check only when a search provider answered it, with results or with no result. A search that no provider answered, and a query that the guard refused, SHALL NOT count. Every call of `search_web` SHALL count toward the limit `CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES`, whether it was answered or not. The text that the tool answers to the model SHALL not change.

#### Scenario: Every search fails
- **WHEN** no provider answers, and the model searches once and then gives the verdict `none` twice
- **THEN** the item is skipped with the reason that the reply gives a verdict with no answered search, its job record names the class `RefusedReply`, and nothing is written to its body or its comments

#### Scenario: A search fails and a later search is answered
- **WHEN** the first search of a run fails, the model searches again, a provider answers, and the model gives the verdict `none`
- **THEN** the check is written, and it lists the one answered search

#### Scenario: A search that answered with no result
- **WHEN** a provider answers a search with no result and the model gives the verdict `none`
- **THEN** the check is written, and it lists the query with `results: 0`

#### Scenario: Failed searches use the limit
- **WHEN** no provider answers and the model calls `search_web` one time more than the limit
- **THEN** the tool sends one request for each call up to the limit, answers the last call that the limit is reached, and records no search

### Requirement: A check writes its block and its marks with one request
With `--confirm`, a check SHALL write the new body with the job's block, and the marks of the job record, with one `PATCH` of the issue, and its comment, when it posts one, as a separate request after it. A stop of the Service after the write SHALL leave the block and `alternatives.checked_at` together. The dry-run plan SHALL list no separate write of the body, and SHALL list the comment with its condition.

#### Scenario: A stop after the write of a check
- **WHEN** a check writes the block and the Service stops right after the write
- **THEN** the body holds the block, the job record holds `alternatives.checked_at`, and the next selection does not take the item

#### Scenario: The requests of one check
- **WHEN** `--confirm` writes one check with a first result or a changed result
- **THEN** the run makes one write of the issue and one comment, and no label changes

#### Scenario: The requests of a recheck with the same result
- **WHEN** `--confirm` writes a recheck with the verdict and the tool of the record
- **THEN** the run makes one write of the issue and no comment, and no label changes

#### Scenario: The dry-run plan of a check
- **WHEN** `devops roadmap alternatives --dry-run --item 7` plans the writes
- **THEN** the plan lists one read of issue 7, one `PATCH` for the body with the marks, and the comment with the condition that the check is a first one or that its verdict or its tool differs from the record

### Requirement: The check reads the tools in use
Once for a run that checks an item of no skip class, the check SHALL read the SPDX SBOM that the dependency graph of the repository exports, with one request. When the run has a clone, the check SHALL also read the files under `roadmap.alternatives.inventory_paths` of the clone. A dependency graph that is off SHALL give an empty SBOM and no error.

#### Scenario: A run of skip-class items
- **WHEN** every selected item is a skip class
- **THEN** the run reads no SBOM

#### Scenario: Two items
- **WHEN** the run checks two items of no skip class
- **THEN** it reads the SBOM once

#### Scenario: A dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** its output lists the `gh` command of the SBOM read and the URL of the deps.dev read, each with its condition

### Requirement: A tool in use gives in-use with no proposal
When no ADR gave `rejected`, the job SHALL give `in-use` to a check whose reply gives `covers` or `partly` for a tool that the inventory holds: the SBOM holds its repository or package, the deployed files name it as a whole word in any case, or the SBOM holds a package that deps.dev links to its GitHub project as the source. The job SHALL ask deps.dev only when the SBOM holds a package. The check SHALL say that the repository already uses the tool.

#### Scenario: A package of the SBOM
- **WHEN** the SBOM holds `pkg:pypi/mcp@2.3.0` and the reply gives `covers` for `https://pypi.org/project/MCP`
- **THEN** the check has the verdict `in-use`, and its comment and its block say "The repository already uses this tool."

#### Scenario: An action with a path
- **WHEN** the SBOM holds `pkg:githubactions/github/codeql-action/init` and the reply gives `covers` for `https://github.com/github/codeql-action`
- **THEN** the check has the verdict `in-use`

#### Scenario: A deployed service
- **WHEN** a file under `k8s` of the clone says `image: ghcr.io/berriai/LiteLLM:main`, a file under `docs` names Velero, and a file under `tf` says `trivyscan`
- **THEN** a reply for `https://github.com/BerriAI/litellm` gives `in-use`, and replies for `velero-io/velero` and `aquasecurity/trivy` keep `covers`

#### Scenario: A package that deps.dev links
- **WHEN** the SBOM holds `pkg:pypi/mcp@2.3.0`, deps.dev links the PyPI package `mcp` to `github.com/modelcontextprotocol/python-sdk`, and the reply gives `covers` for that repository
- **THEN** the check has the verdict `in-use` after one deps.dev read

#### Scenario: An empty SBOM
- **WHEN** the SBOM holds no package and the reply gives `covers` for a tool that the deployed files do not name
- **THEN** the check keeps `covers` and sends no deps.dev request

#### Scenario: The census
- **WHEN** a test replays the 97 `covers` and `partly` checks of the census of 2026-11-11 over the SBOM and the deployed words recorded at its commit
- **THEN** at least 55 of the 58 tools in use give `in-use`

### Requirement: A failed read of deps.dev skips the item
If the read of deps.dev for the tool of a reply fails, the job SHALL skip the item with a named reason, record the failure in its job record and write no check for it.

#### Scenario: deps.dev answers 502
- **WHEN** the SBOM holds a package, the tool of the reply is in no source, and deps.dev answers 502
- **THEN** the run writes no check for the item and records `alternatives.failed_error` `HTTPStatusError`

### Requirement: A check records the canonical id of its tool and the hash of its ADRs
A written check SHALL record `alternatives.tool_id` and `alternatives.adr_hash`. The id SHALL be `github.com/<owner>/<name>` in lower case for the GitHub project of the tool, which a PyPI tool takes from the source URL of its PyPI record, else `pkg:pypi/<name>` with the canonical name of `packaging`, else the tool URL. The hash SHALL cover the ADR entries that the model saw.

#### Scenario: A PyPI package with a source
- **WHEN** the PyPI record of `pydantic-ai-slim` names the `Source` `https://github.com/Pydantic/Pydantic-AI`
- **THEN** the id of the tool is `github.com/pydantic/pydantic-ai`

#### Scenario: A PyPI package with no GitHub source
- **WHEN** the tool is `https://pypi.org/project/Markdown_It.py` and its record names no GitHub project
- **THEN** the id of the tool is `pkg:pypi/markdown-it-py`

#### Scenario: The census
- **WHEN** a test maps the 88 tool strings of the 330 blocks of the census
- **THEN** they give at most 81 ids

#### Scenario: The record
- **WHEN** a run with `--confirm` writes a check of `https://pypi.org/project/gidgethub`, whose source is `gidgethub/gidgethub`
- **THEN** the job record holds the id `github.com/gidgethub/gidgethub` and the hash of the ADRs that the model saw

### Requirement: A change of the ADRs makes a check due
The check SHALL take an item of no skip class whose check is current when its recorded `alternatives.adr_hash` differs from the hash of the ADRs at HEAD, or when its check recorded none, in the order of the items whose check is old. It SHALL NOT take a skip-class item for that reason.

#### Scenario: Another ADR hash
- **WHEN** four items were checked 2 days ago with unchanged bodies: one with the hash at HEAD, one with another hash, one with no hash, and one skip-class item with no hash
- **THEN** the run takes the items with another hash and with no hash, and leaves the other two current
