# roadmap-stage Specification

## Purpose
Defines how `devops roadmap stage` makes a Ready roadmap item Staged: which items it takes, how it plans the OpenSpec change in task groups that fit a context budget, and what it writes to git and GitHub, so a later implementation step starts from a branch and a draft pull request.

## Requirements

### Requirement: The label filter names the items to stage
`devops roadmap stage` SHALL take the open items whose labels match the `--filter family=value` options. The families are `status`, `priority`, `type`, `value` and `effort`. Values of one family SHALL be alternatives, and the families SHALL all apply. With no `--filter`, the filter SHALL be `status=ready`. A family that is not in the list SHALL be refused.

#### Scenario: The default filter
- **WHEN** the roadmap holds a Ready P1 bug, a Ready P3 feature, a Ready P2 docs item and a New P1 bug, and the command runs with no filter
- **THEN** the plan holds the three Ready items, and not the New one

#### Scenario: Values of one family
- **WHEN** the command runs with `--filter priority=p2-medium --filter priority=p3-low --filter status=ready`
- **THEN** the plan holds the Ready items of priority P2 and P3, and no item of another priority

#### Scenario: An unknown family
- **WHEN** the command runs with `--filter color=red`
- **THEN** the command exits 1, names the families it accepts, and makes no request

### Requirement: The job stages Ready items only
Whatever the filter says, the job SHALL stage an item only when its Status is Ready. A `status` filter can narrow the Ready items and SHALL NOT widen them.

#### Scenario: A filter with no status
- **WHEN** the roadmap holds a Ready bug, a New bug and a bug with no Status, and the command runs with `--filter type=bug`
- **THEN** the plan holds only the Ready bug, and it leaves out the other two and names their Status

### Requirement: The job leaves out the items it must not stage
The job SHALL leave out an item that is not Ready, has the label `needs-split`, has an untrusted author, or depends on an open issue. It SHALL leave out a held item: `origin` or a worktree of the clone has a branch `<type>/<issue>-<slug>` for it. It SHALL leave out an item whose plan is on `origin/<default branch>` or whose change is archived there, matched by the issue number only. The plan SHALL name each item it leaves out and say why.

#### Scenario: Items that are left out
- **WHEN** the filter names a Blocked item, an item with `needs-split`, an item opened by an account with no write access, an item that depends on an open issue, and an item with a pushed branch
- **THEN** the plan stages none of them and gives one reason for each

#### Scenario: The plan is on the default branch and the branch is gone
- **WHEN** `origin/main` holds the folder `openspec/changes/7-stop-the-drop/`, `origin` has no branch for item 7, the record of item 7 holds a `stage.pr` that is merged, and the title of item 7 gives another slug
- **THEN** the plan stages no item, and the reason for item 7 says that its plan is on `main` and names the folder

#### Scenario: The plan is on the default branch and the branch is still there
- **WHEN** `origin/main` holds the folder of item 7 and `origin` still has the staged branch of item 7
- **THEN** the plan stages no item, and item 7 has one reason

#### Scenario: The change is archived
- **WHEN** `origin/main` holds the folder `openspec/changes/archive/2026-10-28-7-stop-the-drop/`
- **THEN** the plan leaves out item 7 and the reason says that its change is archived on `main`

#### Scenario: The issue is closed
- **WHEN** the folder of item 7 is on `origin/main` and item 7 is closed
- **THEN** the plan holds no reason for item 7, because the job reads open items only

#### Scenario: A stale record and no plan on the default branch
- **WHEN** the record of item 7 names a merged `stage.pr` and a branch that is gone, and `origin/main` holds no folder for item 7
- **THEN** the plan stages item 7 again

#### Scenario: Two planned items
- **WHEN** `origin/main` holds the folders of items 7 and 8, and both are Ready bugs
- **THEN** the plan leaves out both, each with its own reason

### Requirement: A run stages a bounded number of items
`--limit`, default 3, SHALL cap the items a run stages. `--item N` SHALL stage the one item it names when that item is open and Ready.

#### Scenario: The limit
- **WHEN** the filter names five stageable items and the command runs with `--limit 2`
- **THEN** the plan holds the first two, by priority and then by number

#### Scenario: One item by number
- **WHEN** the command runs with `--item N` and #N is a Ready item
- **THEN** the plan holds #N alone, whatever the filter says

### Requirement: A staged item gets a branch and one commit
For each item the job SHALL make the branch `<type>/<issue>-<slug>` at `origin/<default branch>`, where the type is the Conventional Commit type of the title and the slug comes from its summary. The job SHALL write the change folder `openspec/changes/<issue>-<slug>/`, make one commit as the identity of the session, and push the branch with `-u origin`.

#### Scenario: A Ready bug is staged
- **WHEN** the job runs with `--confirm` on a Ready P1 bug and the model gives a valid plan
- **THEN** the branch is pushed with one commit by the session identity, and the commit holds the change folder

### Requirement: A staged item gets a draft pull request
The job SHALL open a draft pull request whose title is `docs(openspec): plan #<issue> <summary>` and whose body starts with `Plans #<issue>` and holds no closing keyword. The part of the title after the colon SHALL have at most 60 characters, and the job SHALL NOT cut it: the schema keeps a summary short enough for an issue number of up to 6 digits, and a longer number stops that item with an error. The job SHALL NOT mark the pull request ready: the row `stage_ready` of the Service does.

#### Scenario: The draft opens
- **WHEN** the job stages a Ready bug
- **THEN** a draft pull request opens with a body that starts with `Plans #<issue>`

#### Scenario: The body names no closing keyword
- **WHEN** the plan of the model holds the text `Closes #12` in its description of the change
- **THEN** the job stops that item with a failure that names the closing keyword, and pushes nothing

#### Scenario: The title of a bug and of a feature
- **WHEN** the job stages item 12, a bug, and item 13, a feature
- **THEN** the title of each draft starts with `docs(openspec): plan #12 ` and `docs(openspec): plan #13 `, and the branch of each keeps the type of its issue

#### Scenario: A summary at the limit
- **WHEN** the model gives a summary of the most characters that the schema accepts (47: the room after `plan #<issue> ` for an issue number of 6 digits) for item 7 and for item 3249
- **THEN** the title holds the whole summary, ends with no `...`, and passes the form check of titles, and the planner prompt names the same limit

#### Scenario: A long summary
- **WHEN** the model gives a summary that has more than 47 characters as the title shows it, such as 48 characters, or 47 characters with a handle that gets a code span
- **THEN** the schema refuses the reply, the reply goes back to the model with the count and the limit, and a second refusal stops that item only

#### Scenario: Spare whitespace costs nothing
- **WHEN** the model gives a summary of 47 characters followed by a new line
- **THEN** the schema accepts the reply, because the title shows the text on one line

#### Scenario: A number of 7 digits
- **WHEN** the job builds the title of item 1000000 for a summary of 47 characters
- **THEN** the job stops that item with an error that names the limit, and the title is not cut

#### Scenario: An emoji counts as two
- **WHEN** the model gives a summary of 24 emoji, which are 24 characters and 48 UTF-16 code units
- **THEN** the schema refuses the reply, because the check `Semantic PR title` counts 48 units

#### Scenario: A blank summary
- **WHEN** the model gives a summary of spaces and new lines only
- **THEN** the schema refuses the reply, because the title would show no summary

### Requirement: The job measures each task group
The job SHALL measure each task group with tiktoken: the tokens of the group's instructions, the item, the change folder, the `AGENTS.md` of the repository, the routed sections of its documents, and the files that the tasks of the group name in code spans, each packed as the implement step packs it, at most `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens. The budget SHALL be `roadmap.stage.step_tokens`, default 64000, and `--step-tokens` SHALL override it for one run.

#### Scenario: A group is measured
- **WHEN** the model gives a group whose task names a file of the repository
- **THEN** the comment on the issue gives the group's measure, and that measure is more than the tokens of the file packed

#### Scenario: A large file counts as the step reads it
- **WHEN** a task of a group names one file that holds more tokens than the budget
- **THEN** the group measure is under the budget, and the job asks the model for no split

#### Scenario: A file that no task names
- **WHEN** the `Reads:` line of a group lists a file that no task of the group names
- **THEN** the file adds no token to the measure, as the step does not read it

#### Scenario: The rules count
- **WHEN** the repository holds an `AGENTS.md` and a group names `tests/test_sample.py`
- **THEN** the measure of the group holds the tokens of the `AGENTS.md` and of the routed sections of `docs/TESTING.md`

### Requirement: A group over the budget is split once or stops the item
A group over the budget SHALL go back to the model once with its measure and the ask to split it. The job SHALL ask for a split once for each item, also when a corrected reply is over the budget again. A group still over the budget SHALL stop the item: the job posts a comment that names the group and its measure, records `stage.needs_split`, and makes no branch.

#### Scenario: Every group is under the budget
- **WHEN** the model gives three groups and the measure of each is under the budget
- **THEN** the job asks the model once, and the comment lists the three groups with their measures

#### Scenario: A group is split
- **WHEN** one group is over the budget and the second reply splits it into two groups under the budget
- **THEN** the job stages the item with the groups of the second reply

#### Scenario: A corrected reply is over the budget
- **WHEN** the first reply is split, the split fails the validation, and the corrected reply is over the budget
- **THEN** the job stops the item as over the budget and asks the model for no second split, so it made three calls

#### Scenario: A group stays over the budget
- **WHEN** one group is over the budget after the second reply
- **THEN** the job posts a comment that names the group and its measure, records `stage.needs_split`, pushes no branch and opens no pull request

### Requirement: The change passes the OpenSpec validation
When the `openspec` binary is on `PATH`, the job SHALL run `openspec validate <change> --strict --json` on the change before it writes to git. A failed validation SHALL go back to the model once with the output of the tool. A second failure SHALL stop the item. Without the binary, the comment on the issue SHALL say that the validation did not run.

#### Scenario: The validation fails once
- **WHEN** the first plan fails the validation and the second plan passes it
- **THEN** the job stages the second plan and the model got the output of the first failure

#### Scenario: The validation fails twice
- **WHEN** both plans fail the validation
- **THEN** the job stops the item, pushes nothing, and reports the output of the second failure

#### Scenario: No openspec binary
- **WHEN** the `openspec` binary is not on `PATH`
- **THEN** the job stages the item and its comment says that the validation did not run

### Requirement: The validation judges the change against the base specs
The job SHALL run the validation in a scratch directory that also holds the base spec of each capability the change has a delta for. Any issue in the report of OpenSpec SHALL count as a problem and SHALL go back to the model once with the text of the issues. This holds also for an issue that OpenSpec gives for a valid change, such as a delta that `openspec archive` would refuse.

#### Scenario: A MODIFIED requirement that the base spec lacks
- **WHEN** the plan modifies a requirement whose name is not in the base spec of an existing capability
- **THEN** the validation reports the refusal and the model gets it as the problem to correct

### Requirement: A failure stops one item and never hides the others
A model call that fails SHALL skip its item. The job SHALL stage the other items, and then fail and name each skipped item. Rejected credentials SHALL stop the run. A tool error of the validation, such as a timeout, SHALL skip its item in the same way. A push that GitHub refuses SHALL stop its item with the reason, and SHALL leave no remote branch without an open pull request. An item whose title or body looks like a secret SHALL be left out before the model reads it.

#### Scenario: One model call fails
- **WHEN** the model call fails for the first of two items
- **THEN** the second item is staged, the command exits 1, and the error names the first item

#### Scenario: The validation times out
- **WHEN** the validation of the first of two items runs past its timeout
- **THEN** the second item is planned, and the error names the first item

#### Scenario: Rejected credentials
- **WHEN** the model call fails with rejected credentials for the first item
- **THEN** the run stops and stages no item

#### Scenario: The push is refused
- **WHEN** GitHub refuses the push of a branch
- **THEN** the job stops that item with the reason, opens no pull request and records no key

#### Scenario: A secret in the body
- **WHEN** the body of an item holds a text that looks like a secret
- **THEN** the plan leaves the item out, and the model reads none of its text

### Requirement: A failed write stops one item
A write that fails, also the comment on an item stopped on the budget, SHALL stop its item with the reason and SHALL NOT stop the other writes. The job SHALL fail after the other writes and name each item that failed.

#### Scenario: The comment of a stopped item fails
- **WHEN** two items stop on the budget and the comment on the first fails
- **THEN** the second item still gets its comment and its record, the first item gets no record, and the error names the first item

### Requirement: A closed item loses its staged branch when only the App wrote to it
In each run the job SHALL look at the staged branch of each closed item whose record holds `stage.branch`. When every commit of the branch past `origin/<default branch>` has the identity of the session as its author, read from the name of each commit, the job SHALL close the draft pull request and delete the branch. When any other commit exists, the job SHALL keep both and say so in the plan.

#### Scenario: Only the App wrote to the branch
- **WHEN** the item is closed and its staged branch holds one commit by the session identity
- **THEN** the job closes the draft and deletes the branch

#### Scenario: A person added a commit
- **WHEN** the item is closed and its staged branch holds a commit by another author
- **THEN** the job keeps the branch and the draft, and the plan says why

### Requirement: A dry run makes no request
`devops roadmap stage --dry-run` SHALL make no request to GitHub, to git remotes or to the model. It SHALL list the requests and the git commands that a run makes, in order.

#### Scenario: The dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** it exits 0, the GitHub fake and the model fake record no request, and the output lists the reads, the git commands and the writes

### Requirement: The Service runs the stage job on the model lane
The model lane of the Service SHALL hold the row `stage` after the row `refine`. The row SHALL be due by its interval of 60 minutes, on its first run, and in a round where `refine` set an item Ready. The row SHALL run the stage job in the model clone of the lane, write what its plan holds, and fail the round for the items that failed. `devops roadmap run --dry-run` SHALL list the row when it is due.

#### Scenario: The first run
- **WHEN** a repository has no record of a `stage` round
- **THEN** the row is due, after the rows that come before it

#### Scenario: The interval
- **WHEN** the last success of the row is 61 minutes old and no other trigger exists
- **THEN** the row is due
- **AND** with a last success 59 minutes old, the row is not due

#### Scenario: Refine set an item Ready
- **WHEN** the last success of the row is 5 minutes old and the `refine` row of the same round returned an outcome with `set_ready`
- **THEN** the row is due in that round

#### Scenario: Refine set an item Ready and failed another
- **WHEN** the last success of the row is 5 minutes old and the `refine` row of the same round set one item Ready and failed for another item
- **THEN** the row is due in that round
- **AND** the round still fails for the `refine` row

#### Scenario: Refine set no item Ready
- **WHEN** the last success of the row is 5 minutes old and the `refine` row returned an outcome with no `set_ready`
- **THEN** the row is not due

#### Scenario: The dry run
- **WHEN** `devops roadmap run --dry-run` runs for a repository with no record of a round
- **THEN** its `Due:` line lists `stage` after `refine`, and no request is made

### Requirement: The settings name the filter, the limit and the step budget
The settings `roadmap.stage.filter`, `roadmap.stage.limit` and `roadmap.stage.step_tokens` SHALL set what the stage job takes. Each SHALL have the variable `DEVOPS_CLI_ROADMAP_STAGE_FILTER`, `DEVOPS_CLI_ROADMAP_STAGE_LIMIT` or `DEVOPS_CLI_ROADMAP_STAGE_STEP_TOKENS`. The defaults SHALL be the filter `status=ready`, the limit 3 and the step budget 64000, half of the default window of the implement task. The example ConfigMap of the Service SHALL hold the default filter.

#### Scenario: The defaults
- **WHEN** no config file and no variable sets a `roadmap.stage` setting
- **THEN** the filter, the limit and the step budget are the defaults above

#### Scenario: A config file and a variable
- **WHEN** the config file sets `roadmap.stage.limit` to 1 and the variable `DEVOPS_CLI_ROADMAP_STAGE_FILTER` holds `status=ready,type=feature`
- **THEN** the limit is 1 and the filter is `status=ready` and `type=feature`

#### Scenario: A round uses the settings
- **WHEN** the filter is `type=feature` and the limit is 1, and the roadmap holds two Ready features and a Ready bug
- **THEN** a round of the `stage` row plans the first feature only

#### Scenario: The example ConfigMap
- **WHEN** the example ConfigMap of the Service is rendered and loaded as settings
- **THEN** its stage filter equals the default filter

### Requirement: A filter entry is checked when the settings load
A filter entry SHALL be `family=value` over a label family of the stage job. The settings SHALL refuse any other entry and an empty filter, and the message SHALL name the entry.

#### Scenario: An invalid entry
- **WHEN** the filter holds the entry `color=red` or the entry `ready`
- **THEN** loading the settings fails with a message that names that entry

### Requirement: The options replace the settings for one run
`devops roadmap stage` SHALL use the filter and the limit of the settings when `--filter` and `--limit` are not given. The options SHALL replace them for that run.

#### Scenario: The options replace the settings
- **WHEN** the filter setting is `type=feature` and `devops roadmap stage --plan --filter status=ready --filter type=bug --limit 2` runs
- **THEN** the plan holds the Ready bugs, at most 2

### Requirement: Each item of a stage round counts once by its result
A stage round, whether the Service or the command runs it, SHALL add 1 to `devops_cli_roadmap_stage_total` for each item it handled, with the label `result`: `staged` for an item written as a branch and a draft, `needs_split` for an item stopped on a group over the budget, `returned` for an item returned to New on a false premise, `failed` for an item that failed in the plan or in the writes, and `skipped` for an item the job left out with a reason. An item SHALL count under one result.

#### Scenario: Four results in one round
- **WHEN** a round stages one item, stops one on the budget, fails one in the model call, and leaves one out for an open dependency
- **THEN** the counter has one point each for `staged`, `needs_split`, `failed` and `skipped`

#### Scenario: A returned item
- **WHEN** a round returns one item to New on a false premise, besides the four items above
- **THEN** the counter also has one point for `returned`, and each item counts under one result

#### Scenario: A plan with no write
- **WHEN** `devops roadmap stage --plan` runs
- **THEN** the counter has no point

### Requirement: A round reads the plans on the default branch once
A round SHALL fetch the default branch and read the tree of `origin/<default branch>` with one `git ls-tree` of `openspec/changes/` and `openspec/changes/archive/`, before it selects an item. A read that fails SHALL fail the run with the reason of git and stage no item.

#### Scenario: One read for many items
- **WHEN** a round judges three items
- **THEN** git received one `ls-tree` command

#### Scenario: The tree cannot be read
- **WHEN** `git ls-tree` fails
- **THEN** the run raises an error that names the command and the reason of git, and no item is staged

### Requirement: A task group names its files
A task group of the reply SHALL name at least one path in `changes`. A path SHALL hold no backtick and no control character. `reads` MAY be empty. Every path of `creates` SHALL be a path of `changes`.

#### Scenario: A group with no changed file
- **WHEN** the reply holds a group with an empty `changes`
- **THEN** the reply fails the schema

#### Scenario: A path that breaks the line
- **WHEN** the reply holds a path with a new line or a backtick
- **THEN** the reply fails the schema

### Requirement: A task group has the text of its tasks
A task group of the reply SHALL have a text in `title` with at least one character after its whitespace is stripped. It SHALL have a text in `implementation` with at least one character that is no space and no full stop. `test` and `documentation`, when set, SHALL have the same. `verify` and `process`, when set, SHALL have at least one character after their whitespace is stripped. `test`, `verify`, `process` and `documentation` MAY be null.

#### Scenario: A blank text
- **WHEN** the reply holds a group whose `documentation` is blank
- **THEN** the reply fails the schema

#### Scenario: A text of only full stops
- **WHEN** the reply holds a group whose `documentation` is `...`
- **THEN** the reply fails the schema, as a blank text does

#### Scenario: A group with no documentation
- **WHEN** the reply holds a group whose `documentation` is null
- **THEN** the reply passes the schema

### Requirement: A reply that breaks the schema returns once
A reply of the proposal that fails the schema SHALL go back to the model once, with the field of each violation. A second reply that fails the schema SHALL stop the item with the class `StructuredOutputValidationError` and the count of violations.

#### Scenario: A valid second reply
- **WHEN** the first reply holds a group with an empty `changes` and the second reply is valid
- **THEN** the model gets two requests, the second names `groups[0].changes`, and the item is staged

#### Scenario: A second reply that fails
- **WHEN** both replies hold a blank `documentation`
- **THEN** the model gets two requests, and the item stops with the class `StructuredOutputValidationError`

### Requirement: A task group renders without stray punctuation
The group SHALL render as the line `Reads: <paths>. Changes: <paths>.` where an empty `reads` shows `none`, and a created path shows `(new)` after it. A rendered group SHALL hold no double full stop and no task that starts with a comma.

#### Scenario: A group with no reads
- **WHEN** a group has an empty `reads` and a `changes` that holds `src/devops_cli/sample.py`
- **THEN** its line is ``Reads: none. Changes: `src/devops_cli/sample.py`.``

#### Scenario: A created path
- **WHEN** a group has `tests/test_sample.py` in `changes` and in `creates`
- **THEN** its line shows ``Changes: `tests/test_sample.py` (new).``

#### Scenario: A task ends in a full stop
- **WHEN** the `implementation` of a group ends in a full stop or in several
- **THEN** the task renders with no full stop before the comma

### Requirement: A stop record counts only for the measure that made it
The job SHALL record `stage.file_cap`, the file cap of the measure, with `stage.needs_split`. The job SHALL leave an item out for a recorded split only when `stage.file_cap` is the file cap of now. The job SHALL clear `stage.file_cap` when it stages the item.

#### Scenario: A record of an earlier measure
- **WHEN** the record of an item holds `stage.needs_split` and no `stage.file_cap`, or another one
- **THEN** the job does not leave the item out for the record

#### Scenario: A record of the measure of now
- **WHEN** the record of an item holds `stage.needs_split` and the `stage.file_cap` of now
- **THEN** the plan leaves the item out and says why, and `--item` stages it

### Requirement: The Service marks a green stage pull request ready
The row `stage_ready` of the status lane SHALL mark a draft pull request ready for review when the record of an open item holds it as `stage.pr` and all its check runs ended and passed. It SHALL read only the pull requests that the stage job recorded. It SHALL leave a draft with a failed, cancelled, unread or running check, or with no check, and SHALL NOT retry a check.

#### Scenario: Every check passed
- **WHEN** the record of an open item holds a draft `stage.pr` whose check runs all passed
- **THEN** the round marks the pull request ready once, and the record holds `stage.ready` with its number

#### Scenario: A check failed, a check runs, or no check exists
- **WHEN** the head of a recorded draft has a failed check, a running check, or no check run
- **THEN** the round marks no pull request ready and records nothing

#### Scenario: A draft of a person
- **WHEN** a draft pull request is open, green and recorded in no item
- **THEN** the round sends no request for it and marks it ready never

#### Scenario: The same pull request twice
- **WHEN** a second round runs after the first marked the pull request ready
- **THEN** the second round sends no request

#### Scenario: A pull request that left the draft state
- **WHEN** the recorded pull request is ready, merged or closed
- **THEN** the round records `stage.ready` and calls `gh pr ready` never

#### Scenario: No recorded draft
- **WHEN** no open item holds a `stage.pr` that `stage.ready` has not recorded
- **THEN** the round sends no request

#### Scenario: A Job works on the item
- **WHEN** the record of the item holds `implement.job`
- **THEN** the round leaves its pull request a draft

#### Scenario: One item fails
- **WHEN** `gh pr ready` fails for the first of two green drafts
- **THEN** the second pull request is marked ready, and the round fails naming the first item

#### Scenario: The check runs only
- **WHEN** a recorded draft is green
- **THEN** the round sends no request to the commit status endpoint

### Requirement: The row reads again before it marks and stops on a rate limit
The row SHALL read the pull request again before it marks, and SHALL leave a draft whose head moved. A rate limit, rejected credentials and the stop of the Service SHALL stop the round. Any other error SHALL fail its item only.

#### Scenario: A push after the read of the checks
- **WHEN** the head of a recorded draft changes between the read of its checks and the mark
- **THEN** the round marks no pull request ready and records nothing

#### Scenario: GitHub cannot find the pull request
- **WHEN** GitHub answers 404 for the read of a recorded pull request
- **THEN** the round records nothing, reads the pull request again in the next round, and fails naming the item

#### Scenario: A rate limit
- **WHEN** GitHub refuses a read for the rate limit
- **THEN** the round stops at once and sends no request for the pull requests that follow

### Requirement: One function decides, and one function marks
`draft_readiness` SHALL be the only function that decides whether a recorded draft is marked. The row SHALL mark with `mark_ready`, the function the implement job uses, and SHALL record `stage.ready` with the number of the pull request, so that no later round reads it.

#### Scenario: The implement job and the row mark the same way
- **WHEN** the implement job and the row each mark a pull request ready
- **THEN** both run `gh pr ready <number> --repo <repo>`

#### Scenario: The decision is replaced
- **WHEN** a test replaces `draft_readiness` in `stage_ready` with a function that answers refuse
- **THEN** the round marks no pull request

### Requirement: The job leaves out an item that an agent or a person claimed
The job SHALL stage no Item that holds `owner/agent` or `owner/human`, `--item` included, and SHALL give the reason "It is claimed by agent." or "It is claimed by human.". An Item that holds `owner/service` SHALL not be left out for its owner.

#### Scenario: A claimed Item
- **WHEN** a Ready Item holds `owner/human` and the filter names it
- **THEN** the plan stages no Item and lists the Item as left out with a reason that contains "claimed by human"

#### Scenario: An agent claimed the named Item
- **WHEN** `--item` names a Ready Item that holds `owner/agent`
- **THEN** the plan lists the Item as left out with a reason that contains "claimed by agent"

#### Scenario: The Service holds the Item
- **WHEN** a Ready Item holds `owner/service`
- **THEN** the job stages it as it does an Item with no owner

### Requirement: The job takes the highest priority first
A run SHALL take the items that the filter names with the highest priority first, and the lowest issue number first among equal priorities. An item with no priority SHALL go last. The type of the branch of a staged item SHALL be the Conventional Commit type of its title.

#### Scenario: Priority order
- **WHEN** the default filter names a Ready P3 chore, a Ready P2 feature and a Ready P0 docs item, and the limit is 2
- **THEN** the plan stages the P0 docs item and the P2 feature

#### Scenario: The type of the branch
- **WHEN** the plan stages a feature titled `feat(cli): add a flag` and a docs item titled `docs(k8s): fix a path`
- **THEN** the branches start with `feat/` and `docs/`

### Requirement: The job leaves out a tracker
The job SHALL leave out an item that has sub-issues or the label `type/epic`, and the plan SHALL give the reason. Its sub-issues deliver it, so it gets no plan of its own.

#### Scenario: A tracker under the default filter
- **WHEN** the roadmap holds a Ready item with the label `type/epic`, a Ready item with two sub-issues and a Ready plain bug, and the command runs with no filter
- **THEN** the plan stages the plain bug only, and it names the tracker reason for the other two

### Requirement: The limit bounds a round, not the open drafts
`--limit` SHALL be the only bound on the staging drafts. The job SHALL NOT take fewer items because staging draft pull requests are open. A person merges or closes the plans.

#### Scenario: Drafts stay open
- **WHEN** three staging drafts are open and the roadmap holds more Ready items
- **THEN** the next round still stages up to `--limit` items

### Requirement: The plan lists the items that matched no filter when asked
`stage --plan` SHALL list, under "Matched no filter" and only with `--why`, each open item that the filter does not name. Each line SHALL name the family that the item misses, the values the filter takes, and the value the item has. The section SHALL not be part of "Left out". Without `--why`, the output SHALL not change.

#### Scenario: Why
- **WHEN** the filter is `priority=p0-critical` and a Ready P1 item exists
- **THEN** `stage --plan --why` lists the P1 item under "Matched no filter" with the family `priority`

#### Scenario: No why
- **WHEN** the same plan runs without `--why`
- **THEN** the output has no section "Matched no filter"

### Requirement: The plan names files that exist at the staged commit
The job SHALL check each path of the reply against the tracked files of the staged commit: the paths of `reads` and `changes`, the paths in the code spans of the tasks, and the paths in `verify`. A path SHALL pass when the commit holds it, or when `creates` of its group or of an earlier group lists it. A missing path SHALL go back to the model once, with the files of the commit that have the same file name. A second reply with a missing path SHALL stop the item and open no draft pull request.

#### Scenario: A test file that moved
- **WHEN** a group changes `tests/test_scanner_tool_executor.py` and the commit holds `tests/security/test_scanner_tool_executor.py`
- **THEN** the job asks the model again, and the problem names the missing path and lists `tests/security/test_scanner_tool_executor.py`

#### Scenario: The second reply has a missing path
- **WHEN** the second reply still names `tests/test_scanner_tool_executor.py`
- **THEN** the job stops the item with the problem, pushes no branch and opens no draft pull request

#### Scenario: A path in a task or in a verify command
- **WHEN** a code span of a task or the `verify` command of a group names a file that the commit lacks and no group up to it creates
- **THEN** the problem names that file

#### Scenario: A created path
- **WHEN** a group changes `tests/test_new.py`, lists it in `creates`, and a later group reads it
- **THEN** the job finds no missing path
- **AND** when only a later group lists it in `creates`, the earlier group names a missing path

#### Scenario: A word that is no path
- **WHEN** a code span holds `status/blocked`, `--strict` or `uv run devops ci docs`
- **THEN** the job finds no missing path

#### Scenario: A name with no folder
- **WHEN** a code span of a task or the `verify` command holds `ruff.toml` or `grep step_files.py`
- **THEN** the job finds no missing path
- **AND** a path of `reads` or `changes` with no folder is still checked

### Requirement: A problem names the group that creates a missing path
When a later group lists a missing path in `creates`, the problem SHALL name the group that names the path and the first later group that creates it, and SHALL tell the model to move the creating group before the reading group. A path that no group creates SHALL keep the problem without a creating group.

#### Scenario: A path that only a later group creates
- **WHEN** group 1 reads `tests/test_new.py` and only group 3 lists it in `creates`
- **THEN** the problem names group 1 and group 3, and tells the model to move group 3 before group 1

#### Scenario: A path that no group creates
- **WHEN** group 1 reads `tests/test_new.py` and no group lists it in `creates`
- **THEN** the problem names group 1 and names no creating group

### Requirement: The comment and the record of a staged item
The job SHALL post one comment on the issue with the marker `<!-- devops roadmap stage -->` that names the branch, the pull request, the groups with their measures and the budget. The job SHALL record `stage.branch`, `stage.pr`, `stage.sha` and `stage.groups` in the job record. The job SHALL NOT change the Status of the item.

#### Scenario: The comment and the record
- **WHEN** the job stages a Ready bug
- **THEN** the issue gets one comment with the marker, the record holds the four keys, and the Status is still Ready

#### Scenario: A title with no type
- **WHEN** the title of the item has no Conventional Commit type
- **THEN** the plan leaves the item out and says that its title has no type

### Requirement: A task group has a kind
A task group of the reply SHALL have a `kind`: `behavior` or `other`. A `behavior` group SHALL have a `test` and a `verify`, no `process`, and a path under `src/` in `changes`. An `other` group SHALL have no `test`, and exactly one of `verify` and `process`. The reply that breaks a rule SHALL fail the schema, and the problem text SHALL name each rule it breaks.

#### Scenario: A test on an other group
- **WHEN** the reply holds an `other` group with a `test`
- **THEN** the reply fails the schema, and the model gets the problem text

#### Scenario: A behavior group with no test
- **WHEN** the reply holds a `behavior` group whose `test` is null
- **THEN** the reply fails the schema

#### Scenario: A behavior group that changes no source
- **WHEN** the reply holds a `behavior` group whose `changes` hold only `docs/TESTING.md`
- **THEN** the reply fails the schema

#### Scenario: An other group with no proof
- **WHEN** the reply holds an `other` group with no `verify` and no `process`
- **THEN** the reply fails the schema

### Requirement: A task group renders the tasks of its kind
A `behavior` group SHALL render `n.1` as its failing test, `n.2` as its implementation, and `n.3` as its documentation when `documentation` is set. An `other` group SHALL render `n.1` as its implementation with its `verify` or its `process`, and `n.2` as its documentation when `documentation` is set. A task with a command SHALL write it on a line `- Verification: ` under the task, as a code span that `step_files` reads. A group with no `documentation` SHALL render no documentation task.

#### Scenario: A deletion that keeps behavior
- **WHEN** an `other` group deletes a definition and its `verify` is a `git grep` that must print nothing
- **THEN** its first task names the deletion, the line under it holds the `git grep` and says "passes", and no task asks for a test or says "fails on the base"

#### Scenario: A manual check
- **WHEN** an `other` group has a `process`
- **THEN** its first task holds the steps of the process, and it has no `Verification:` line

#### Scenario: A behavior group
- **WHEN** a `behavior` group has a `test`
- **THEN** its first task is the test, and the line under it holds the `verify` command and says "fails on the base"

#### Scenario: The step reads the command
- **WHEN** the text that `group_text` writes for a group with a `verify` is parsed with `parse_task_groups`
- **THEN** `verification_commands` of the parsed group holds the `verify` of the group

#### Scenario: A group with documentation
- **WHEN** a group has a `documentation` task
- **THEN** its last task holds the command that regenerates the documents, and its `Verification:` line holds `uv run devops ci docs`

### Requirement: The prompts and the validator name the same kinds
The stage prompt and the split prompt SHALL name each value of the kind and each field of a task group. The implement prompt SHALL tell the step to write the failing test first only when its group has a test task.

#### Scenario: A kind the prompt does not name
- **WHEN** a value of the kind is absent from the stage prompt
- **THEN** the guard test fails

### Requirement: The planner has a read-only toolbox
The planner of the stage job SHALL plan with an agent that has the tools of the toolset `roadmap.stage.toolset`. The toolset `base` SHALL have exactly `list_files`, `read_file`, `search_code`, `git_log`, `git_show`, `file_symbols`, `callers`, `repo_map` and `read_spec`. The toolset `extended` SHALL add `references`, `read_issue` and `find_issues`. No tool SHALL write a file or run a shell command. A tool SHALL answer a bad argument as text and SHALL NOT raise.

#### Scenario: The tool set
- **WHEN** the toolbox is built for a checkout and a commit with the toolset `base`
- **THEN** the names of its tools are exactly the nine above, and `search_web` is not one of them

#### Scenario: A path outside the repository
- **WHEN** `read_file` gets the path `../outside.txt`
- **THEN** it answers that the path is outside the repository, and it raises no error

#### Scenario: An argument that is an option
- **WHEN** `git_show` gets `--output=out.txt`
- **THEN** it answers that the argument is no commit, and no file `out.txt` exists

#### Scenario: The prompt names the tools
- **WHEN** the system text of a toolbox run is built
- **THEN** it names each tool of the toolset of the run and no tool of the other toolset

### Requirement: A plan run has a budget
A plan run of the toolbox SHALL make at most `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS` tool calls and `CONST_ROADMAP_STAGE_MAX_REQUESTS` model requests. It SHALL set no count of output tokens: the context window ends the tools of a run. The run SHALL offer no tool to a request when fewer than 4 tool calls are left, so the model gives its plan. A run that passes a limit SHALL fail the item with a reason. The job SHALL plan the other items, and SHALL open no draft pull request for the failed item.

#### Scenario: The tool call limit
- **WHEN** one reply of the model in a plan run holds one more parallel tool call than `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS`
- **THEN** the item fails, and the reason names `tool_calls_limit`

#### Scenario: The tools are gone near the limit
- **WHEN** the model has made `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS` minus 3 tool calls, one in each turn
- **THEN** the next request offers no tool, and a valid plan in the reply stages the item

#### Scenario: The output token limit
- **WHEN** the replies of the model in one plan run hold more than 50000 output tokens, and the last reply is a valid plan
- **THEN** the item is staged

#### Scenario: A run inside the budget
- **WHEN** the model reads two files and then answers with a valid plan
- **THEN** the item is staged

#### Scenario: One item fails and the others are planned
- **WHEN** the plan run of the first of two items spends its budget
- **THEN** the second item is planned, and the job fails at the end for the first item

### Requirement: A plan run keeps its messages inside the context window
A plan run SHALL offer no tool to a request when the tokens of its messages, with a quarter of the context window of the `analysis` task, reach the window. The model SHALL then give its plan. The tool answers SHALL NOT make a request longer than the window by more than the reply that was kept free.

#### Scenario: A model that reads a big file in every turn
- **WHEN** a plan run has a window of 12000 tokens and the model reads a file of 120 long lines in every turn
- **THEN** a request offers no tool before the budget of tool calls, no request passes the window, and the plan stages the item

#### Scenario: A run with no window
- **WHEN** a run is given no window
- **THEN** only the budget of tool calls takes the tools away

### Requirement: The tools read a checkout that is the staged commit
The toolbox SHALL refuse a checkout whose HEAD is not the staged commit, or that has a change that is not committed or a file that git does not track, before any model call. The failure SHALL be a `RoadmapStageError`. A tool SHALL read the size of a file before it reads the file, SHALL refuse a file of more than 2000000 bytes, and SHALL number only the lines that it returns. `search_code` and `callers` SHALL stop at one more than `CONST_ROADMAP_REFINE_TOOL_MAX_LINES` matches in one file.

#### Scenario: A modified file
- **WHEN** the checkout holds a modified tracked file
- **THEN** building the toolbox raises `RoadmapStageError` and the model gets no request

#### Scenario: A file over the size limit
- **WHEN** `read_file` gets a file of more than 2000000 bytes
- **THEN** it answers that the file is too large to read

#### Scenario: A file with many matches
- **WHEN** a file holds three times `CONST_ROADMAP_REFINE_TOOL_MAX_LINES` lines that match `callers`
- **THEN** the answer holds `CONST_ROADMAP_REFINE_TOOL_MAX_LINES` lines and says that lines are left out

### Requirement: The map and the spec tools give short answers
`repo_map` SHALL give one line for each of at most `CONST_ROADMAP_STAGE_MAP_MAX_FILES` files, with the path and the names of the top-level symbols, cut to 180 characters. It SHALL end with a line that says so when the directory holds more files. `read_spec` SHALL read the capabilities, the requirement names and the requirement text from the JSON of `openspec list --specs` and `openspec show --type spec`. It SHALL answer as text when OpenSpec is not installed.

#### Scenario: A directory with more files than the limit
- **WHEN** `repo_map` maps a directory of `CONST_ROADMAP_STAGE_MAP_MAX_FILES` plus 5 Python files
- **THEN** the answer has `CONST_ROADMAP_STAGE_MAP_MAX_FILES` file lines and a last line that says that files are left out

#### Scenario: A requirement
- **WHEN** `read_spec` gets a capability and a requirement name
- **THEN** it answers with the heading, the text and the scenarios of that requirement

### Requirement: A call to a tool that is gone gets a retry
When a request offers no tool, a call of the model to a function tool SHALL get a retry prompt, and the run SHALL go on. The run SHALL fail the item when the model calls a gone tool a third time, because the tool retry limit is 2. The reason of the failure SHALL name the retry limit, and no budget limit. It holds no tool name, because the name of a tool in an error message is text that the model chose.

#### Scenario: One call after the tools are gone
- **WHEN** the model has made `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS` minus 3 tool calls, calls `read_file` once in a request that offers no tool, and then gives a valid plan
- **THEN** the item is staged

#### Scenario: Two calls after the tools are gone
- **WHEN** the model calls `read_file` twice in requests that offer no tool, and then gives a valid plan
- **THEN** the item is staged

#### Scenario: Three calls after the tools are gone
- **WHEN** the model calls `read_file` a third time in requests that offer no tool
- **THEN** the item fails, and the reason names the retry limit 2, and no budget limit

### Requirement: The budget is for each plan run
A plan run SHALL be one model call for a plan. The budget of a plan run SHALL be for that run, not for the item. The planner can make a second plan run for one item, when the checks of the job refuse the first plan. That second run SHALL start with a new budget, so one item can use twice `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS` tool calls at most. The model call that splits the groups of an item SHALL use no tool and SHALL have no tool budget.

#### Scenario: The budget is for each plan run
- **WHEN** the first plan run of an item makes 20 tool calls, the checks refuse its plan, and the second plan run makes 20 tool calls
- **THEN** the second run is inside its own budget, and the item is staged

### Requirement: A toolbox run keeps the return rules of a broken reply
A plan run of the toolbox SHALL send a reply that breaks the schema back to the model once, with the violations. A second reply that breaks the schema SHALL stop the item with the class `StructuredOutputValidationError` and the count of violations. A reply that the checks of the job refuse SHALL go back once, as it does without the toolbox.

#### Scenario: A reply that breaks the schema twice
- **WHEN** both replies of a plan run hold a group with an empty `changes`
- **THEN** the item stops with the class `StructuredOutputValidationError`

#### Scenario: A missing path after the tools
- **WHEN** the first plan of a toolbox run names a path that the commit lacks
- **THEN** the job asks again with the problem, and a second plan with a missing path stops the item

### Requirement: The comment of a staged item reports the plan run
The comment of an item that the toolbox planned SHALL report all plan runs of the item, in the order they ran. It SHALL list each tool call with the name and the masked, cut argument of the call. It SHALL state the count of model requests, the input tokens and the output tokens, summed over all plan runs of the item. The comment of an item planned without the toolbox SHALL hold none of these lines.

#### Scenario: The comment lists the calls
- **WHEN** the model calls `read_file` for `src/devops_cli/sample.py` and then answers
- **THEN** the comment of the staged item lists `read_file` with that path and the token counts

#### Scenario: An item with two plan runs
- **WHEN** the first plan of an item is refused, and the second plan run makes one tool call
- **THEN** the comment lists the tool calls of both runs in order, and its token counts are the sums of both runs

#### Scenario: An argument with a secret
- **WHEN** a tool call has an argument that looks like a secret
- **THEN** the comment holds the masked text and not the secret

### Requirement: A verification pass follows the gates
When the caller gives a verifier, the planner SHALL make one verification call for each plan after the plan passes `check_proposal` and `validate_change`, and before the job opens the draft pull request. The verifier SHALL be the client of the task slot `ai.tasks.verification`. The request SHALL hold the issue, the plan, and the capped start of each file that the plan cites. The pass SHALL NOT merge a pull request and SHALL NOT mark one ready.

#### Scenario: A plan that passes the gates
- **WHEN** a plan passes the gates and the verifier finds nothing
- **THEN** the verifier gets one request with the issue, the plan and the cited files, and the job opens the draft pull request

#### Scenario: A long cited file
- **WHEN** a plan cites a file with more tokens than `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS`
- **THEN** the request holds only the first tokens of that file

#### Scenario: A plan that fails the gates
- **WHEN** the gates refuse a plan twice
- **THEN** the verifier gets no request

#### Scenario: No pull request is merged or marked ready
- **WHEN** the pass ends with findings
- **THEN** the draft pull request stays a draft and the job makes no merge call

### Requirement: A finding has one of the nine defect types
A verification reply SHALL hold findings, and each finding SHALL have a `type` that is one of `missing_path`, `false_premise`, `spec_delta_wrong`, `verify_form`, `task_order`, `criterion_dropped`, `ignores_existing_code`, `contrived_test` and `other`, a place, a problem and a quote. The prompt of the pass SHALL name the same nine types.

#### Scenario: An unknown type
- **WHEN** the verifier names a finding type outside the nine types on both tries
- **THEN** the item stops with the class `StructuredOutputValidationError` and the job opens no pull request

#### Scenario: The prompt and the schema agree
- **WHEN** the prompt of the pass is read
- **THEN** it names each of the nine types and no other type

### Requirement: An evidence-backed finding returns the plan once
A finding of type `missing_path`, `false_premise` or `ignores_existing_code` whose quote is in the issue, the plan or a cited file SHALL return the plan to the planner once, with the finding as the problem. The revised plan SHALL pass the gates and the verification again. The planner SHALL NOT return a plan for a second time.

#### Scenario: A false premise with a quote
- **WHEN** the verifier returns a `false_premise` finding whose quote is in the issue
- **THEN** the planner gets a second request with the finding as `problem` and the first plan as `previous`, and the job opens the draft pull request with the revised plan

#### Scenario: A quote that is not in the input
- **WHEN** the verifier returns a `false_premise` finding whose quote is in none of the issue, the plan and the cited files
- **THEN** the planner gets no second request and the finding goes into the comment

#### Scenario: The revised plan has a finding too
- **WHEN** the revised plan gets a `missing_path` finding with a quote
- **THEN** the planner makes no third request and the finding goes into the comment

### Requirement: Other findings go into the comment
The job SHALL list each finding that does not return the plan in the comment that names the draft pull request, with its type, place, problem and quote. The text of a finding SHALL be on one line, with a handle, a link or a reference to another repository in a code span. The job SHALL open the draft pull request.

#### Scenario: A contrived test finding
- **WHEN** the verifier returns a `contrived_test` finding
- **THEN** the comment lists the finding and the draft pull request is open

#### Scenario: No finding
- **WHEN** the verifier returns no finding
- **THEN** the comment holds no findings section

### Requirement: Refuse a spec delta that the changed paths do not need
`check_proposal` SHALL refuse a proposal with `skip_specs: false` when every path of every group's `changes` starts with `tests/`, `.github/workflows/`, `docs/` or `openspec/`.

#### Scenario: Every changed path is a test, CI, document or plan path
- **WHEN** A proposal has `skip_specs: false` and every `changes` path starts with `tests/`, `.github/workflows/`, `docs/` or `openspec/`
- **THEN** `check_proposal` returns a problem that says no spec delta is needed

#### Scenario: One changed path is source code
- **WHEN** A proposal has `skip_specs: false` and one `changes` path starts with `src/`
- **THEN** `check_proposal` returns no problem about the spec delta

### Requirement: Refuse an added requirement that the base spec already has
`check_proposal` SHALL refuse an ADDED requirement whose name equals the name of a requirement in the base spec of that capability.

#### Scenario: An added requirement name is in the base spec
- **WHEN** A spec delta ADDs a requirement whose name is a requirement name of `openspec/specs/<capability>/spec.md`
- **THEN** `check_proposal` returns a problem that names the duplicate requirement

#### Scenario: An added requirement name is new
- **WHEN** A spec delta ADDs a requirement whose name is in no requirement of the base spec of that capability
- **THEN** `check_proposal` returns no problem about a duplicate

### Requirement: The model input holds the purpose and the requirement names of each capability
The stage job SHALL give the model the purpose and the requirement names of every capability under `openspec/specs/`.

#### Scenario: The input lists a capability
- **WHEN** The stage job builds the model input for a proposal
- **THEN** the input holds the purpose and the requirement names of each capability

### Requirement: A verify command has the project form
`check_proposal` SHALL refuse a group whose `verify` command does not start with `uv run devops` as a whole word, unless it is a negative search. It SHALL refuse a `verify` command of the project form that the implement step refuses to run, and the problem SHALL hold the reason of the step. The reason SHALL come from the table that the step reads, so that the gate and the step cannot differ.

#### Scenario: A pytest verify command is refused
- **WHEN** a group gives the `verify` command `uv run pytest tests/roadmap/test_stage.py`
- **THEN** `check_proposal` returns a problem that names the command and the accepted forms

#### Scenario: A devops command or a negative search is accepted
- **WHEN** a group gives the `verify` command `uv run devops ci test tests/roadmap/test_stage.py` or `! git grep -n old_name src/ tests/`
- **THEN** `check_proposal` returns no problem about the `verify` command

#### Scenario: A negative search that the step refuses
- **WHEN** a group gives the `verify` command `! git grep -n name src/ | cat` or `! git grep -O name src/`
- **THEN** `check_proposal` returns a problem that names the command and the reason that the step gives

#### Scenario: A verify command that the step runs
- **WHEN** a group gives any of the commands `uv run devops ci`, `uv run devops docs check`, `! git grep -n absent_name src/ tests/` and `! git grep -nI -F old_name -- src/ tests/`
- **THEN** `check_proposal` returns no problem, and the step runs each of them

### Requirement: A new test module sits in a mirror directory
`check_proposal` SHALL refuse a path in `creates` that is a test module under `tests/` unless it is in `tests/invariants/` or in the directory that mirrors the package of a source file that the plan changes.

#### Scenario: A flat test path is refused
- **WHEN** a group creates `tests/test_stage.py` and the plan changes `src/devops_cli/roadmap/stage.py`
- **THEN** `check_proposal` returns a problem that names the path and the directory `tests/roadmap`

#### Scenario: A mirrored or an invariant test path is accepted
- **WHEN** a group creates `tests/roadmap/test_stage.py` or `tests/invariants/test_source_tree.py`
- **THEN** `check_proposal` returns no problem about the test path

### Requirement: The prompt and the rules give a mirrored test path
The stage prompt and `openspec/config.yaml` SHALL give only example test paths whose folder under `tests/` mirrors a package of `src/devops_cli/`.

#### Scenario: Every example path is mirrored
- **WHEN** a test reads the stage prompt and `openspec/config.yaml`
- **THEN** each example test path has a folder under `tests/` that mirrors a package of `src/devops_cli/`

### Requirement: Criteria mapping in the stage reply
The stage reply SHALL hold a `criteria` list in which each entry gives the text of one acceptance criterion of the issue and either the number of the group that delivers it or `pending-person` with a reason. An acceptance criterion SHALL be a top-level item of a list under a heading `Acceptance criteria` in the text of the issue body that a person wrote, before the block of the refine job. An issue with no such list SHALL have no criterion.

#### Scenario: Every criterion is mapped
- **WHEN** The issue has three acceptance criteria and the reply's `criteria` list holds an entry for each, with a group number or `pending-person` and a reason
- **THEN** `check_proposal` returns no problem for the criteria mapping

#### Scenario: The list of the refine block is not read
- **WHEN** The issue body holds a list under `Acceptance criteria` in the refine block as well, and the reply maps the items of the list that a person wrote
- **THEN** `check_proposal` returns no problem for the criteria mapping

#### Scenario: The issue has no acceptance list
- **WHEN** The issue body has no heading `Acceptance criteria` and the reply's `criteria` list is empty
- **THEN** `check_proposal` returns no problem for the criteria mapping

#### Scenario: A pending-person entry has no reason
- **WHEN** An entry of `criteria` gives `pending-person` and a blank reason
- **THEN** the reply breaks the schema and goes back to the model

### Requirement: An unmapped criterion is refused
`check_proposal` SHALL refuse a reply that leaves an acceptance criterion of the issue with no entry in `criteria`, and an entry that names a group the plan does not have. The problem SHALL quote the exact text of the criterion. The check SHALL read the whole body of the issue.

#### Scenario: One of three criteria is unmapped
- **WHEN** The issue has three acceptance criteria and the reply's `criteria` list maps only two
- **THEN** `check_proposal` returns a problem that quotes the text of the unmapped criterion

#### Scenario: The retry copies the text
- **WHEN** The first reply leaves a criterion out and the second reply maps it
- **THEN** the second request to the model holds the problem with the exact text, and the item is staged

#### Scenario: An entry names a group that does not exist
- **WHEN** An entry of `criteria` names group 3 and the plan has 2 groups
- **THEN** `check_proposal` returns a problem that names the criterion and the count of groups

### Requirement: Criteria section in tasks.md
The `tasks.md` of a staged plan SHALL hold a `## Criteria` section before `## Workflow follow-up`. It SHALL list each criterion as a bullet with no checkbox, and each bullet SHALL start with a fixed word: `Group <n>:` and the criterion, or `Pending person:`, the criterion and the reason. A criterion that reads as a heading or a task SHALL add no group and no task.

#### Scenario: Staged plan shows the mapping
- **WHEN** A plan is rendered with criteria mapped to groups
- **THEN** `tasks.md` holds a `## Criteria` section with one line for each criterion, as `Group <n>: <criterion>` or `Pending person: <criterion>, <reason>`

#### Scenario: A plan with no criterion has no section
- **WHEN** A plan is rendered with an empty `criteria` list
- **THEN** `tasks.md` holds no `## Criteria` section

#### Scenario: A criterion that reads as a heading
- **WHEN** a criterion of the issue is `## 2. Cleanup`
- **THEN** the gate accepts the entry that copies it, and `tasks.md` holds the group 1 only

### Requirement: A split moves the criteria with the groups
The split request SHALL hold the `criteria` list, the split reply SHALL give it again with the numbers of the new groups, and the job SHALL check it as it checks the first reply.

#### Scenario: A split renumbers the groups
- **WHEN** The model splits a group and gives the criteria with the new group numbers
- **THEN** `tasks.md` shows the new numbers

### Requirement: The replay judges the criteria gate on plans with a criteria list
The golden-set replay SHALL run the `criteria` gate on a plan that has a `criteria` list, and SHALL not judge a recorded plan that has none.

#### Scenario: A plan leaves a criterion out
- **WHEN** The replay runs a plan with a `criteria` list that leaves one criterion of its issue out
- **THEN** the `criteria` gate refuses the plan

#### Scenario: A recorded plan has no list
- **WHEN** The replay runs a recorded plan with no `criteria` key
- **THEN** the `criteria` gate finds no problem

### Requirement: The job probes the premise at the staging commit
Before the model call, the stage job SHALL probe each path and each identifier that the issue cites at the staging commit, and SHALL put the probe text in the model input under the key `probes`. The job SHALL take the cited items from the same extraction as the context of the model. A missing path SHALL be probed for the commit that deleted or renamed it, and an identifier with no definition for the commit that last added or removed its text.

#### Scenario: Probe output is in the model input
- **WHEN** the job plans an issue that cites a file of the staging commit and a function that the commit defines
- **THEN** the model input holds `probes` with a line that says the file is present and a line that names the definition of the function

#### Scenario: A removed identifier names its removal commit
- **WHEN** the issue cites `validate_url`, which a commit removed from the history before the staging commit
- **THEN** `probes` says that the identifier has no definition and names that commit

#### Scenario: A removed path names its removal commit
- **WHEN** the issue cites a path that a commit deleted
- **THEN** `probes` says that the path is missing and names the commit that deleted it

#### Scenario: A thing that never existed
- **WHEN** the issue cites a path that no commit ever held
- **THEN** `probes` says that the path is missing and that no commit in the history deleted or renamed it

#### Scenario: A backtick text that is no path and no identifier
- **WHEN** the issue holds the backtick texts `git log -S x`, `owner/repo` and the number 0.41
- **THEN** `probes` holds no line for any of them

### Requirement: The probes are bounded and read-only
The probes of one item SHALL run at most 10 git commands. When the issue cites more items than the bound allows, the probe SHALL stop at the bound and list the items it did not probe. Every probe command SHALL be `git cat-file`, `git grep` or `git log`, and no probe SHALL change the checkout.

#### Scenario: The bound stops the probes
- **WHEN** the issue cites 12 paths that the commit holds
- **THEN** the probe runs 10 commands and `probes` lists 2 paths as not probed

#### Scenario: Only reading commands
- **WHEN** the probe runs for an issue that cites a missing path, a missing identifier and a present path
- **THEN** every command it ran is `cat-file`, `grep` or `log`, and `git status --porcelain` of the checkout is empty

### Requirement: A false premise returns the item
When the model reply sets `premise_failed` with evidence, the stage job SHALL comment the evidence on the issue and set its Status to New, as `devops roadmap return` does, and SHALL make no branch and no pull request for the item. The job SHALL ask for no plan from such a reply.

#### Scenario: Replay of #2971
- **WHEN** the job plans an issue that cites `validate_url`, which a commit removed, and the model replies with `premise_failed` and the evidence
- **THEN** the issue gets the evidence as a comment and the Status New, and the repository gets no branch and no pull request

#### Scenario: A plan with a true premise
- **WHEN** the model reply sets no `premise_failed`
- **THEN** the job stages the change as before

#### Scenario: A reply with no plan and no premise_failed
- **WHEN** the model reply sets no `premise_failed` and holds no groups
- **THEN** the reply fails the schema and goes back to the model once

### Requirement: The prompt asks feasibility to quote the probes
The prompt of the stage job SHALL tell the model that `probes` holds the result of read-only commands at the staging commit, SHALL ask `feasibility` to quote the lines of `probes` that confirm the premise, and SHALL tell the model to set `premise_failed` only when the probes or the inputs show that the premise of the issue is false.

#### Scenario: The prompt names the probes
- **WHEN** the stage prompt loads
- **THEN** it names `probes` and `premise_failed`, and asks `feasibility` to quote the probes

### Requirement: The setting toolset chooses the tools of a plan run
The setting `roadmap.stage.toolset` SHALL be `base` or `extended`, with the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET`. The default SHALL be `extended`. The settings SHALL refuse any other value and name it. The example ConfigMap of the Service SHALL set the key. The toolset `base` SHALL have no GitHub tool and SHALL need no GitHub client.

#### Scenario: The default
- **WHEN** no config file and no variable sets `roadmap.stage.toolset`
- **THEN** the toolset is `extended`, and a plan run offers twelve tools

#### Scenario: The base toolset
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET` is `base`
- **THEN** a plan run offers the nine tools, and none of `references`, `read_issue` and `find_issues`

#### Scenario: A value that is none of the two
- **WHEN** the variable is `wide`
- **THEN** loading the settings fails with a message that names the variable and the values `base` and `extended`

### Requirement: The tool references counts a text in every file of the commit
`references(name)` SHALL run `git grep -n -I -F` for the text over the whole staged commit with no cap for a file. It SHALL answer the count of files and lines, and for each file its path, its exact count of lines and its first five line numbers. It SHALL answer as text for a name that is empty, longer than 100 characters, or not one line.

#### Scenario: Every file with its count
- **WHEN** a name is in a source file, a test, a fixture, a spec, two documents and a manifest, and one file holds it 400 times
- **THEN** the answer lists each of the eight files with its count, and the count of the large file is 400

#### Scenario: A name that cannot be searched
- **WHEN** the name is empty, or 101 characters long, or holds a line break
- **THEN** the answer says so as text, and the tool runs no git command

### Requirement: The tool references keeps files of every group
`references` SHALL keep at most 60 files. It SHALL take them in turn from the source, the tests, the specs, the documents, the change folders and the other files, so that a long list of one group hides no other group. It SHALL say how many files it left out.

#### Scenario: Files left out
- **WHEN** a name is in more than 60 files, among them a spec and a document
- **THEN** the answer lists 60 files that include the spec and the document, and says how many files it left out

### Requirement: The tool read_issue answers the state of an item
`read_issue(number)` SHALL answer the state, the title, the labels, the first 1500 characters of the body, and the last 3 comments cut to 600 characters each. For a closed issue it SHALL name the merged pull request that closed it, or say that none did. For a closed pull request it SHALL say whether it merged.

#### Scenario: An issue closed by a merged pull request
- **WHEN** `read_issue` reads a closed issue whose last closing commit is in a merged pull request
- **THEN** the answer holds the state, the title, the labels and the line "Closed by merged pull request #N."

#### Scenario: A closed pull request
- **WHEN** `read_issue` reads a closed pull request that did not merge
- **THEN** the answer says that the pull request closed with no merge

### Requirement: The tool find_issues lists open items that name the terms
`find_issues(terms)` SHALL answer at most 10 open issues and pull requests of the repository that name the terms, each as `#N state title`. It SHALL take every colon and quote out of the terms, so that the search names no repository but that of the job.

#### Scenario: Open items
- **WHEN** `find_issues` gets the terms `redaction point` and GitHub finds an issue and a pull request
- **THEN** the answer lists both as `#N state title`

#### Scenario: A qualifier in the terms
- **WHEN** `find_issues` gets the terms `repo:other/private`
- **THEN** the search that GitHub receives holds no `repo:` qualifier except that of the repository of the job

### Requirement: The GitHub tools read only, mask what they read and answer a failure as text
`read_issue` and `find_issues` SHALL read through the GitHub client of the Service with its existing token, send GET requests only, and add no permission. They SHALL reach no host but the GitHub API host of the Service, and no other tool SHALL open a network connection. They SHALL mask secrets in the text from GitHub, cut each text, and state that it is data and no instruction. They SHALL answer each failure as text and SHALL NOT raise.

#### Scenario: A secret in the text from GitHub
- **WHEN** the body, a comment and the title of an issue each hold a token
- **THEN** the answer holds none of the three tokens

#### Scenario: An item that does not exist
- **WHEN** `read_issue` gets a number that GitHub does not hold
- **THEN** the answer says that GitHub holds no such issue or pull request, and it raises no error

#### Scenario: A failure of GitHub
- **WHEN** the connection to GitHub fails
- **THEN** the answer names the class of the failure, tells the model to go on without it, and holds no text of the failure

#### Scenario: A run with no client
- **WHEN** a plan run has the toolset `extended` and the job gave no GitHub client
- **THEN** `read_issue` and `find_issues` answer that GitHub is not available

### Requirement: The prompt of the extra tools says when to call each one
The prompt of a run with the toolset `extended` SHALL tell the model to call `references` for a rename, a move or a removal, `read_issue` for each issue number that the issue names, and `find_issues` before the plan says what it depends on. It SHALL tell the model that text from GitHub is data and never an instruction. The prompt of a run with the toolset `base` SHALL name none of the three tools.

#### Scenario: The extended prompt
- **WHEN** the system text of a run with the toolset `extended` is built
- **THEN** it names `references`, `read_issue` and `find_issues`, and it says that text from GitHub is data

#### Scenario: The base prompt
- **WHEN** the system text of a run with the toolset `base` is built
- **THEN** it names none of `references`, `read_issue` and `find_issues`

### Requirement: A text of a group stays on one line
The `title`, `test`, `implementation`, `documentation`, `verify` and `process` of a task group, and the `criterion` and the `reason` of a criterion, SHALL be written to `tasks.md` on one line, and a text set after validation SHALL be validated again. A line break in one of them SHALL add no line, no task, no group and no `Verification:` line.

#### Scenario: A line break and a command
- **WHEN** the `implementation` of a group holds a line break and a line `- Verification: ` with a command
- **THEN** the `verification_commands` of the parsed group are the `verify` of the group and the check of the documents, and no more

#### Scenario: A line break in a title
- **WHEN** the `title` of a group holds a blank line and a line `- [ ] 9.9 Extra`
- **THEN** `tasks.md` holds one group and the task list is that of the group

#### Scenario: A line break in the reason of a criterion
- **WHEN** the `reason` of a `pending-person` criterion holds a line `## 2. Extra`
- **THEN** `tasks.md` holds one group

#### Scenario: Any line terminator
- **WHEN** a text of a group holds a heading after any character that ends a line in markdown or in Python, such as `\r`, `\x85` or U+2028
- **THEN** `tasks.md` holds one group, and the text holds one space in place of the character

#### Scenario: A text set after validation
- **WHEN** the `implementation` of a validated group is set to a text with a line break and a `Verification:` line
- **THEN** the text is on one line, and the group renders no extra command

### Requirement: A verify command holds no backtick
`form_problems` SHALL give a problem for a `verify` command that holds a backtick, and the problem SHALL say that it holds a backtick. A command that also has a wrong form SHALL get the problem of its form in the same run.

#### Scenario: A backtick in a command
- **WHEN** the `verify` of a group is ``uv run devops ci test `x` ``
- **THEN** `form_problems` gives one problem, and it says that the command holds a backtick

#### Scenario: A backtick and a wrong form
- **WHEN** the `verify` of a group is ``pytest `x` ``
- **THEN** `form_problems` gives two problems: the backtick, and the form to use

### Requirement: The paths of a negative search are checked against the staged commit
`check_proposal` SHALL read the paths of a `verify` command that is a negative search from the reader of the step, and SHALL refuse a path that is no file or folder of the staged commit and that no group up to its own creates. The path `.` SHALL not be judged. A glob SHALL be judged by the files that it matches.

#### Scenario: A folder that is not in the commit
- **WHEN** a group gives the `verify` command `! git grep -n hello scr/ testz/` and the commit has `src/` and `tests/` only
- **THEN** `check_proposal` returns a problem for `scr` and one for `testz`

#### Scenario: Folders of the commit and a folder that the plan creates
- **WHEN** a group gives the `verify` command `! git grep -n old_name src/ tests/`, `! git grep -n x -- .` or `! git grep -n x -- tests/newdir`, and the plan creates `tests/newdir/test_new.py`
- **THEN** `check_proposal` returns no problem about the paths

### Requirement: A text of the proposal, the design and the spec delta stays on one line
The `why`, `what_changes`, `feasibility` and `existing_tool` of the reply, the texts of its decisions and rejected alternatives, and the `purpose`, the names, the texts and the scenario lines of its spec deltas, SHALL be written on one line. A text that is written at the start of a line SHALL start with no mark of markdown: a heading, a quote, a list marker, a box, a rule, a fence or a comment. The reply that breaks the rule fails the schema.

#### Scenario: A removed section in a requirement
- **WHEN** the `text` of a requirement holds a line break, a heading `## REMOVED Requirements` and a requirement
- **THEN** the `spec.md` of the delta holds the headings Purpose, ADDED Requirements and the one requirement, and no REMOVED section

#### Scenario: A text that starts with a heading
- **WHEN** the `why` of the reply is `## REMOVED Requirements`
- **THEN** the reply fails the schema, and the error says that the text starts with a mark of markdown

#### Scenario: A line break in a bullet
- **WHEN** an item of `feasibility` holds a blank line and a heading
- **THEN** the item is one line

### Requirement: A verify command keeps its spaces
The `verify` of a task group SHALL be written on one line by joining its lines with one space, and SHALL keep every other space of the command.

#### Scenario: Two spaces in a word
- **WHEN** the `verify` is `! git grep -n 'a  b'` and a line break and `src/`
- **THEN** the `verify` of the group is `! git grep -n 'a  b' src/`
