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
The job SHALL leave out an item that is not Ready, has the label `needs-split`, fails the check of `roadmap-author-trust`, or depends on an open issue. It SHALL leave out a held item: `origin` or a worktree of the clone has a branch `<type>/<issue>-<slug>` for it. It SHALL leave out an item whose plan is on `origin/<default branch>` or whose change is archived there, matched by the issue number only. The plan SHALL name each item it leaves out and say why.

#### Scenario: Items that are left out
- **WHEN** the filter names a Blocked item, an item with `needs-split`, an item opened by an account with no write access that the jobs do not trust, an item of a bot that no review approved, an item that depends on an open issue, and an item with a pushed branch
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
The job SHALL run the validation in a scratch directory that also holds the base spec of each capability the change has a delta for. Any issue in the report of OpenSpec SHALL count as a problem and SHALL go back to the model once with its text, even for a valid change, such as a delta that `openspec archive` would refuse. The one exception is the INFO note that a change sets `skip_specs`.

#### Scenario: A MODIFIED requirement that the base spec lacks
- **WHEN** the plan modifies a requirement whose name is not in the base spec of an existing capability
- **THEN** the validation reports the refusal and the model gets it as the problem to correct

#### Scenario: A change that sets skip_specs
- **WHEN** OpenSpec reports only the INFO message that `skip_specs` is set
- **THEN** the validation gives no problem

#### Scenario: Another issue next to the skip_specs message
- **WHEN** OpenSpec reports the `skip_specs` message and a second INFO issue
- **THEN** the validation gives a problem that holds the second issue and not the `skip_specs` message

### Requirement: A failure stops one item and never hides the others
A model call that fails SHALL skip its item. The job SHALL stage the other items and record each skipped item in its job record. The command SHALL exit 1 and name each skipped item. Rejected credentials SHALL stop the run. A validation error, such as a timeout, SHALL skip its item the same way. A push that GitHub refuses SHALL stop its item with the reason and leave no remote branch without an open pull request. An item whose text looks like a secret SHALL be left out before the model reads it.

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
- **THEN** the job stops that item with the reason, opens no pull request and records no staged key

#### Scenario: A secret in the body
- **WHEN** the body of an item holds a text that looks like a secret
- **THEN** the plan leaves the item out, and the model reads none of its text

### Requirement: A failed write stops one item
A write that fails, also the comment on an item stopped on the budget, SHALL stop its item with the reason and SHALL NOT stop the other writes. The job SHALL record each item that failed in its job record, and the command SHALL fail after the other writes and name each item that failed. The labels of the draft pull request are the one exception: a label that GitHub refuses stops no item (requirement "The draft pull request gets the labels of its title").

#### Scenario: The comment of a stopped item fails
- **WHEN** two items stop on the budget and the comment on the first fails
- **THEN** the second item still gets its comment and its record, the first item gets no stop record but gets a failure record, and the error names the first item

### Requirement: A closed item loses its staged branch when only the App wrote to it

In each run the job SHALL look at the staged branch of each closed item whose record holds `stage.branch`. When every commit of the branch past `origin/<default branch>` has the identity of the session as its author or is a clean merge, the job SHALL close the draft pull request and delete the branch. A clean merge is a merge commit whose tree is the one that `git merge-tree --write-tree` gives for its two parents. When any other commit exists, the job SHALL keep both and say so in the plan.

#### Scenario: Only the App wrote to the branch
- **WHEN** the item is closed and its staged branch holds one commit by the session identity
- **THEN** the job closes the draft and deletes the branch

#### Scenario: A person added a commit
- **WHEN** the item is closed and its staged branch holds a commit by another author
- **THEN** the job keeps the branch and the draft, and the plan says why

#### Scenario: A person added only a clean merge
- **WHEN** the item is closed and its staged branch holds one commit by the session identity and a clean merge by another author
- **THEN** the job closes the draft and deletes the branch

### Requirement: A dry run makes no request
`devops roadmap stage --dry-run` SHALL make no request to GitHub, to git remotes or to the model. It SHALL list the requests and the git commands that a run makes, in order.

#### Scenario: The dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** it exits 0, the GitHub fake and the model fake record no request, and the output lists the reads, the git commands and the writes

### Requirement: The Service runs the stage job on the model lane
The model lane of the Service SHALL hold the row `stage` after the row `refine`. The row SHALL be due by its interval of 60 minutes, on its first run, and in a round where `refine` set an item Ready. The row SHALL run the stage job in the model clone of the lane and write what its plan holds. The row SHALL fail the round only when the round tried items and staged or stopped none, and for a failure that no item explains. `devops roadmap run --dry-run` SHALL list the row when it is due.

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
A stage round, whether the Service or the command runs it, SHALL add 1 to `devops_cli_roadmap_stage_total` for each item it handled, with the label `result`: `staged` for an item written as a branch and a draft, `needs_split` for an item stopped on a group over the budget, `failed` for an item that failed in the plan or in the writes, and `skipped` for an item the job left out with a reason. An item SHALL count under one result.

#### Scenario: Four results in one round
- **WHEN** a round stages one item, stops one on the budget, fails one in the model call, and leaves one out for an open dependency
- **THEN** the counter has one point each for `staged`, `needs_split`, `failed` and `skipped`

#### Scenario: A returned item
- **WHEN** a round plans one item and the model answers with the key `premise_failed` twice
- **THEN** the item counts as `failed`, and the counter has no point for `returned`

#### Scenario: A plan with no write
- **WHEN** `devops roadmap stage --plan` runs
- **THEN** the counter has no point

#### Scenario: A staged item carries its repository
- **WHEN** A stage round counts a staged item for repository `owner/repo`.
- **THEN** The series `devops_cli_roadmap_stage_total{repo="owner/repo",result="staged"}` increases by one and no `devops_cli_roadmap_pipeline_plans_total` series exists.

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

### Requirement: The row refuses a plan with an open finding
The row `stage_ready` SHALL NOT mark a pull request that holds the label `plan/needs-fix`. It SHALL leave that draft and comment once that the label is the reason, and it SHALL record `stage.needs_fix` with the number of the pull request.

#### Scenario: A green draft with an open finding stays in draft
- **WHEN** every check of a staged draft pull request has passed and the pull request holds the label `plan/needs-fix`
- **THEN** the row leaves the pull request in draft and posts a comment that names the label as the reason

#### Scenario: The row states the reason once
- **WHEN** two rounds read a green draft pull request that holds `plan/needs-fix`
- **THEN** the first round posts one comment that names the label and records `stage.needs_fix`, and the second round makes no second comment

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
- **WHEN** a group has a `documentation` task and changes `src/devops_cli/commands/pr.py`
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
A plan run SHALL offer no tool to a request when the tokens of its messages, with a quarter of the context window of the `stage` task, reach the window. The model SHALL then give its plan. The tool answers SHALL NOT make a request longer than the window by more than the reply that was kept free. The run SHALL take the tokens of its messages from the usage of the last reply, plus the text after it, with no fixed factor.

#### Scenario: A model that reads a big file in every turn
- **WHEN** a plan run has a window of 12000 tokens and the model reads a file of 120 long lines in every turn
- **THEN** a request offers no tool before the budget of tool calls, no request passes the window, and the plan stages the item

#### Scenario: A run with no window
- **WHEN** a run is given no window
- **THEN** only the budget of tool calls takes the tools away

#### Scenario: The count follows the reported input
- **WHEN** the last reply of a run reports an input of 105,412 tokens and the window is 200000
- **THEN** the count of the messages is within 10 percent of 105,412 tokens and the next request offers its tools

#### Scenario: The reported input has no room for a reply
- **WHEN** the last reply reports an input of 149,900 tokens and the window is 200000
- **THEN** the next request offers no tool

#### Scenario: The text after the last reply counts
- **WHEN** the last reply reports 140,000 tokens and the answer after it holds more than 10,000 tokens of text
- **THEN** the next request offers no tool

#### Scenario: The first request
- **WHEN** the run has no reply yet
- **THEN** its count is the count of the instructions and the user prompt, within 2 percent

#### Scenario: A reply that reports no input
- **WHEN** a provider omits the input tokens of its replies
- **THEN** the count of the messages is the count of their text, within 2 percent, and not the count of their JSON form

#### Scenario: A call to a tool that is not offered
- **WHEN** the model calls `read_file` while only `final_result` is offered
- **THEN** the return names `final_result` as the tool that is available

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
`repo_map` SHALL give one line for each of at most `CONST_ROADMAP_STAGE_MAP_MAX_FILES` files, with the path and the names of the top-level symbols, cut to 180 characters, and a last line that says so when the directory holds more files. `read_spec` SHALL read the specs from the JSON of `openspec list --specs` and `openspec show --type spec`. For one capability it SHALL answer with a line `Purpose:` and then the requirement names. It SHALL answer as text when OpenSpec is not installed.

#### Scenario: A directory with more files than the limit
- **WHEN** `repo_map` maps a directory of `CONST_ROADMAP_STAGE_MAP_MAX_FILES` plus 5 Python files
- **THEN** the answer has `CONST_ROADMAP_STAGE_MAP_MAX_FILES` file lines and a last line that says that files are left out

#### Scenario: A requirement
- **WHEN** `read_spec` gets a capability and a requirement name
- **THEN** it answers with the heading, the text and the scenarios of that requirement

#### Scenario: A capability
- **WHEN** `read_spec` gets a capability and no requirement name
- **THEN** it answers with a first line `Purpose:` and the purpose, and then the requirement names

#### Scenario: A capability with no requirement
- **WHEN** `read_spec` gets a capability that holds a purpose and no requirement
- **THEN** it answers with the line `Purpose:` and the purpose

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
When the caller gives a verifier, the planner SHALL run one verification for each plan after the plan passes `check_proposal` and `validate_change`, and before the job opens the draft pull request. The verifier SHALL be an agent of the task slot `ai.tasks.verification` with the read-only tools of the toolset `roadmap.stage.toolset`. Its request SHALL hold the issue, the plan and the capped start of each file that the plan cites. The pass SHALL NOT merge a pull request or mark one ready.

#### Scenario: A plan that passes the gates
- **WHEN** a plan passes the gates and the verifier finds nothing
- **THEN** the verifier runs once with a request that holds the issue, the plan and the cited files, and no message of the planner, and the job opens the draft pull request

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

### Requirement: An evidence-backed finding returns the plan at most twice
A finding of type `missing_path`, `false_premise`, `ignores_existing_code`, `task_order` or `verify_form` whose quote is in the issue, the plan, a cited file or a tool answer of the run SHALL return the plan to the planner, with each open finding of the round as the problem. The revised plan SHALL pass the gates and the verification again, at most `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS` times, which is two.

#### Scenario: A false premise with a quote
- **WHEN** the verifier returns a `false_premise` finding whose quote is in the issue
- **THEN** the planner gets a second request with the finding as `problem` and the first plan as `previous`, and the job opens the draft pull request with the revised plan

#### Scenario: A quote that is not in the input
- **WHEN** the verifier returns a `false_premise` finding whose quote is in none of the issue, the plan, the cited files and the tool answers of the run
- **THEN** the planner gets no second request and the finding goes into the comment

#### Scenario: The revised plan has a finding too
- **WHEN** the first revised plan gets a `missing_path` finding with a quote
- **THEN** the planner gets a second repair request with the finding as `problem`

#### Scenario: A task order finding returns the plan
- **WHEN** the verifier returns a `task_order` finding whose quote is in the plan
- **THEN** the planner gets a second request with the finding as `problem`

#### Scenario: A quote from a tool answer
- **WHEN** the verifier reads a line past the cap of a cited file with a tool, and returns an `ignores_existing_code` finding that quotes that line
- **THEN** the planner gets a repair request with the finding as `problem`

### Requirement: Other findings go into the comment
The job SHALL list each finding that does not return the plan in the comment that names the draft pull request, with its type, place, problem and quote. The text of a finding SHALL be on one line, with a handle, a link or a reference to another repository in a code span. The job SHALL open the draft pull request.

#### Scenario: A contrived test finding
- **WHEN** the verifier returns a `contrived_test` finding
- **THEN** the comment lists the finding and the draft pull request is open

#### Scenario: No finding
- **WHEN** the verifier returns no finding
- **THEN** the comment holds no findings section

### Requirement: Refuse a spec delta that the changed paths do not need
`check_proposal` SHALL refuse a proposal with `skip_specs: false` when every path of every group's `changes` is under `tests/`, `.github/workflows/`, `docs/`, `openspec/` or `src/devops_cli/ai/knowledge_base/`, or is a markdown document outside `src/`.

#### Scenario: Every changed path is a test, CI, document or plan path
- **WHEN** A proposal has `skip_specs: false` and every `changes` path starts with `tests/`, `.github/workflows/`, `docs/` or `openspec/`
- **THEN** `check_proposal` returns a problem that says no spec delta is needed

#### Scenario: One changed path is source code
- **WHEN** A proposal has `skip_specs: false` and one `changes` path starts with `src/`
- **THEN** `check_proposal` returns no problem about the spec delta

#### Scenario: Root documents with a delta
- **WHEN** A plan changes only `SECURITY.md` and `CONTRIBUTING.md` and gives a spec delta
- **THEN** `check_proposal` reports that these paths need no spec delta

#### Scenario: Knowledge-base file and test path with a delta
- **WHEN** A plan changes only `src/devops_cli/ai/knowledge_base/example.md` and a path under `tests/`, and gives a spec delta
- **THEN** `check_proposal` reports that these paths need no spec delta

#### Scenario: Knowledge-base file and test path without a delta
- **WHEN** A plan changes only `src/devops_cli/ai/knowledge_base/example.md` and a path under `tests/`, and sets `skip_specs: true`
- **THEN** `check_proposal` reports no problem about a spec delta

#### Scenario: Task prompt with a delta
- **WHEN** A plan changes only `src/devops_cli/ai/tasks/roadmap_stage_change.md` and gives a spec delta
- **THEN** `check_proposal` reports no problem about a spec delta

### Requirement: Refuse an added requirement that the base spec already has
`check_proposal` SHALL refuse an ADDED requirement whose name equals the name of a requirement in the base spec of that capability.

#### Scenario: An added requirement name is in the base spec
- **WHEN** A spec delta ADDs a requirement whose name is a requirement name of `openspec/specs/<capability>/spec.md`
- **THEN** `check_proposal` returns a problem that names the duplicate requirement

#### Scenario: An added requirement name is new
- **WHEN** A spec delta ADDs a requirement whose name is in no requirement of the base spec of that capability
- **THEN** `check_proposal` returns no problem about a duplicate

### Requirement: The model input holds the purpose and the requirement names of each capability
The stage job SHALL give the model every capability under `openspec/specs/`. A plan run that has the tool `read_spec` SHALL get the names of the capabilities in the first request and SHALL read the purpose and the requirement names of one capability with `read_spec`. A call with no tool SHALL get the purpose and the requirement names of every capability in the input.

#### Scenario: The input lists a capability
- **WHEN** The stage job builds the model input for a proposal that is planned with one call and no tool
- **THEN** the input holds the purpose and the requirement names of each capability

#### Scenario: The input of a run with read_spec
- **WHEN** The stage job builds the first request of a plan run that has `read_spec`, for a checkout with many capabilities
- **THEN** the `capabilities` key holds the name of every capability in order, the request holds no purpose and no requirement name, and the run offers `read_spec`

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
- **WHEN** a group creates `tests/test_stage.py` and the plan changes `src/devops_cli/roadmap/stage/stage.py`
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

### Requirement: The prompt asks feasibility to quote the probes
The prompt of the stage job SHALL tell the model that `probes` holds the result of read-only commands at the staging commit, SHALL ask `feasibility` to quote the lines of `probes` that confirm the premise, and SHALL tell the model that the reply has no key to report a false premise: when the issue cannot be built as written, `feasibility` says so with the evidence and the plan holds no code that compensates for it.

#### Scenario: The prompt names the probes
- **WHEN** the stage prompt loads
- **THEN** it names `probes`, asks `feasibility` to quote the probes, and does not name `premise_failed` as a key to set

### Requirement: The setting toolset chooses the tools of a plan run
The setting `roadmap.stage.toolset` SHALL be `base`, `extended` or `research`, with the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET`. The default SHALL be `extended`. The settings SHALL refuse any other value and name it. The example ConfigMap of the Service SHALL set the key. The toolset `base` SHALL have no GitHub tool and SHALL need no GitHub client.

#### Scenario: The default
- **WHEN** no config file and no variable sets `roadmap.stage.toolset`
- **THEN** the toolset is `extended`, and a plan run offers twelve tools

#### Scenario: The base toolset
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET` is `base`
- **THEN** a plan run offers the nine tools, and none of `references`, `read_issue` and `find_issues`

#### Scenario: A value that is none of the two
- **WHEN** the variable is `wide`
- **THEN** loading the settings fails with a message that names the variable and the values `base`, `extended` and `research`

#### Scenario: The research toolset
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET` is `research`
- **THEN** a plan run offers thirteen tools: every tool of `extended` and `search_web`

### Requirement: The tool references counts a text in every file of the commit
`references(name)` SHALL run `git grep -n -I -F` for the text over the whole staged commit with no cap for a file. It SHALL answer the count of files and lines, and for each file its path, its exact count of lines and its first five line numbers. It SHALL answer as text for a name that is empty, longer than 100 characters, or not one line.

#### Scenario: Every file with its count
- **WHEN** a name is in a source file, a test, a fixture, a spec, two documents and a manifest, and one file holds it 400 times
- **THEN** the answer lists each of the eight files with its count, and the count of the large file is 400

#### Scenario: A name that cannot be searched
- **WHEN** the name is empty, or 101 characters long, or holds a line break
- **THEN** the answer says so as text, and the tool runs no git command

### Requirement: The tool references keeps files of every group
`references` SHALL keep at most 60 files. It SHALL take them in turn from the specs, the source, the tests, the documents, the change folders and the other files, so that a long list of one group hides no other group. It SHALL say how many files it left out.

#### Scenario: Files left out
- **WHEN** a name is in more than 60 files, among them a spec and a document
- **THEN** the answer lists 60 files that include the spec and the document, and says how many files it left out

#### Scenario: A command name exists in a spec and in source
- **WHEN** a name is in a file under the specs and in a file under the source, and the answer keeps both files
- **THEN** the answer lists the spec file before the source file

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
`check_proposal` SHALL read the paths of a `verify` command that is a negative search from the reader of the step, and SHALL refuse a path that is no file or folder of the staged commit and that no group up to its own creates. A path that ends in `/` SHALL be a folder. The path `.` SHALL not be judged. A glob SHALL be judged by the files that it matches.

#### Scenario: A folder that is not in the commit
- **WHEN** a group gives the `verify` command `! git grep -n hello scr/ testz/` and the commit has `src/` and `tests/` only
- **THEN** `check_proposal` returns a problem for `scr` and one for `testz`

#### Scenario: Folders of the commit and a folder that the plan creates
- **WHEN** a group gives the `verify` command `! git grep -n old_name src/ tests/`, `! git grep -n x -- .` or `! git grep -n x -- tests/newdir`, and the plan creates `tests/newdir/test_new.py`
- **THEN** `check_proposal` returns no problem about the paths

#### Scenario: A file with a trailing slash
- **WHEN** a group gives the `verify` command `! git grep -n devops README.md/` and `README.md` is a file of the commit
- **THEN** `check_proposal` returns a problem for `README.md`

### Requirement: A text of the proposal, the design and the spec delta stays on one line
The `why`, `what_changes`, `feasibility` and `existing_tool` of the reply, the texts of its decisions and rejected alternatives, and the `purpose`, the names, the texts and the scenario lines of its spec deltas, SHALL be written on one line, and U+FEFF SHALL count as white space. A text at the start of a line SHALL start with no mark of markdown: a heading, a quote, a list marker, a box, a rule, a fence or an HTML tag. The reply that breaks the rule fails the schema.

#### Scenario: A removed section in a requirement
- **WHEN** the `text` of a requirement holds a line break, a heading `## REMOVED Requirements` and a requirement
- **THEN** the `spec.md` of the delta holds the headings Purpose, ADDED Requirements and the one requirement, and no REMOVED section

#### Scenario: A text that starts with a heading
- **WHEN** the `why` of the reply is `## REMOVED Requirements`
- **THEN** the reply fails the schema, and the error says that the text starts with a mark of markdown

#### Scenario: A line break in a bullet
- **WHEN** an item of `feasibility` holds a blank line and a heading
- **THEN** the item is one line

#### Scenario: A mark after U+FEFF
- **WHEN** the `purpose` of a spec is U+FEFF, `##`, U+FEFF and `REMOVED Requirements`
- **THEN** the reply fails the schema

#### Scenario: An HTML tag
- **WHEN** the `existing_tool` of the reply starts with `<pre>`
- **THEN** the reply fails the schema

### Requirement: A verify command keeps its spaces
The `verify` of a task group SHALL be written on one line by joining its lines with one space, and SHALL keep every other space of the command.

#### Scenario: Two spaces in a word
- **WHEN** the `verify` is `! git grep -n 'a  b'` and a line break and `src/`
- **THEN** the `verify` of the group is `! git grep -n 'a  b' src/`

### Requirement: The draft pull request gets the labels of its title
After the job records an item, it SHALL add to its draft pull request the `type/*` label and the `scope/*` label that the title gives, each only when `.github/labels.yml` on the default branch declares it. A label that GitHub refuses SHALL NOT delete the branch, close the draft or unset the record. The comment of the item SHALL name each label not added and the reason. Rejected credentials SHALL stop the run.

#### Scenario: The title gives a type and a scope
- **WHEN** the job stages item 1 and the labels file declares `type/docs` and `scope/openspec`
- **THEN** the draft holds `type/docs` and `scope/openspec` and no other label

#### Scenario: A label is refused and the branch stays
- **WHEN** GitHub refuses `type/docs` for the draft
- **THEN** the remote branch exists, the draft is open, and the record holds `stage.branch`, `stage.pr`, `stage.sha` and `stage.groups`

#### Scenario: A label is refused and the comment says so
- **WHEN** GitHub refuses `type/docs` for the draft and accepts `scope/openspec`
- **THEN** the one comment of the item names the pull request, `type/docs` and the reason, and the draft holds `scope/openspec`

#### Scenario: Rejected credentials
- **WHEN** GitHub answers the label call with HTTP 401
- **THEN** the run stops with the unauthenticated error and the comment has no label note

#### Scenario: A dry run
- **WHEN** `devops roadmap stage --dry-run` runs
- **THEN** the plan lists the read of `.github/labels.yml` and the request that adds a label to the draft, and the run makes no request

### Requirement: A split reply is checked for the form of its commands
The job SHALL check the groups of a split reply for the form of their `verify` commands, as it checks the groups of a plan, and SHALL send a reply with a problem back to the model once.

#### Scenario: A split group with two commands
- **WHEN** a split group has a `verify` of ``uv run devops ci test tests/x.py` and `git push origin HEAD``
- **THEN** the reply goes back to the model with the `verify` problem, and the model is asked once more

### Requirement: A task of a group holds more than one word
`form_problems` SHALL give a problem for each `test`, `implementation` or `documentation` text of a group that holds one word or less, with a code span counted as one word. The problem SHALL name the group by its number and its title, and the part of the text.

#### Scenario: A bare filename as the first task
- **WHEN** the `test` of a behavior group is `src/devops_cli/roadmap/stage/stage_form.py`
- **THEN** `form_problems` gives one problem, and it names the group and the part `test`

#### Scenario: A single word as the work
- **WHEN** the `implementation` of a group is `Refactor`
- **THEN** `form_problems` gives one problem that names the part `implementation`

#### Scenario: A code span alone
- **WHEN** the `test` of a group is a path in a code span
- **THEN** `form_problems` gives one problem

#### Scenario: A task with a verb and an object
- **WHEN** the `test` of a group is `Add a test in tests/roadmap/stage/test_roadmap_stage_form.py for a bare filename task`
- **THEN** `form_problems` gives no problem for the task

### Requirement: A plan text is no placeholder
The stage job SHALL refuse a plan whose `why`, `existing_tool`, `feasibility` line, decision or task text is shorter than `PLAN_FIELD_MIN_CHARS` or holds only a placeholder word.

#### Scenario: Short why is refused
- **WHEN** A plan gives `why` as `x`.
- **THEN** `check_proposal` returns a problem that names `why` and the minimum length.

#### Scenario: Placeholder existing tool is refused
- **WHEN** A plan gives `existing_tool` as `todo`.
- **THEN** `check_proposal` returns a problem that names `existing_tool` and the placeholder rule.

#### Scenario: Short feasibility line is refused
- **WHEN** A plan gives a `feasibility` line `x`.
- **THEN** `check_proposal` returns a problem that names `feasibility` and the minimum length.

#### Scenario: A short real sentence is accepted
- **WHEN** A plan gives `why` as `No alternative.`
- **THEN** `check_proposal` returns no placeholder problem for `why`.

#### Scenario: The placeholder rule is the rule of the pull request form
- **WHEN** The content gate judges the text `TBD`.
- **THEN** It refuses the text through `is_placeholder` of `src/devops_cli/roadmap/pull_form.py`.

### Requirement: Feasibility quotes a probe line
When `probes` is not empty, the stage job SHALL refuse a `feasibility` list that holds no line of `probes` word for word.

#### Scenario: No quoted probe
- **WHEN** `probes` holds `def f(): pass` and `feasibility` holds `The function exists.`
- **THEN** `check_proposal` returns a problem that names `feasibility` and the quote rule.

#### Scenario: Exact probe quote
- **WHEN** `probes` holds `def f(): pass` and `feasibility` holds `The probe shows def f(): pass.`
- **THEN** `check_proposal` returns no quote problem.

#### Scenario: A job that read no probe is not judged
- **WHEN** `probes` is empty and `feasibility` holds `The function exists.`
- **THEN** `check_proposal` returns no quote problem.

### Requirement: Existing tool holds a build cost
A plan that sets `builds_own` to true SHALL give a token count and a time in `existing_tool`.

#### Scenario: Build cost missing
- **WHEN** `builds_own` is true and `existing_tool` is `Pydantic can set a minimum length.`
- **THEN** `check_proposal` returns a problem that names `existing_tool` and the cost rule.

#### Scenario: Build cost given
- **WHEN** `builds_own` is true and `existing_tool` is `Cost to build: about 80k tokens and 4 hours.`
- **THEN** `check_proposal` returns no cost problem.

#### Scenario: A plan that adopts a tool needs no cost
- **WHEN** `builds_own` is false and `existing_tool` is `Pydantic covers the need.`
- **THEN** `check_proposal` returns no cost problem.

### Requirement: The summary of a plan is not cut
The stage plan SHALL refuse a `summary` that is longer than `STAGE_SUMMARY_MAX_CHARS` or that ends with `...`.

#### Scenario: Long summary
- **WHEN** A reply gives a `summary` of `STAGE_SUMMARY_MAX_CHARS` plus one characters.
- **THEN** The schema returns a problem that names `summary` and the limit.

#### Scenario: Cut summary
- **WHEN** A reply gives a `summary` that ends with `...`.
- **THEN** The schema returns a problem that names `summary` and the cut rule.

### Requirement: A title holds the full summary
`staging_title` and `delivery_title` SHALL use the full summary and SHALL add no `...`.

#### Scenario: Long delivery summary
- **WHEN** `delivery_title` receives `feat(roadmap): a summary that is longer than the bound of the title`.
- **THEN** The returned title ends with the full summary and holds no added `...`.

#### Scenario: Staging title holds the summary
- **WHEN** `staging_title` receives item 3200 and the summary `Refuse placeholder text`.
- **THEN** The returned title is `docs(openspec): plan #3200 Refuse placeholder text`.

### Requirement: The replay judges a placeholder plan
The stage replay SHALL catch a recorded placeholder plan as a defect of type `other` through the `content` gate.

#### Scenario: Gate lookup
- **WHEN** The replay asks `gate_for(DefectType.OTHER)`.
- **THEN** The answer is `GateName.CONTENT`, not `none` or `pending`.

#### Scenario: Placeholder case replayed
- **WHEN** A golden-set case holds a placeholder in `why` and an `other` defect with the gate `content`.
- **THEN** `replay_case` marks the defect `caught` and reports no failure.

#### Scenario: Placeholder case no longer refused
- **WHEN** The plan of that case holds real text in every field that the content gate reads.
- **THEN** `replay_case` marks the `content` defect `missed` and reports a failure.

### Requirement: The group measure and the Job use one token counter
The stage SHALL count the tokens of a task group with the same tiktoken encoding as the implement Job, and SHALL raise an error that names the missing tiktoken cache when the encoding cannot be loaded.

#### Scenario: Both paths count the same text
- **WHEN** The stage and the implement Job count the same task-group text and the tiktoken cache is present
- **THEN** Both give the same token count

#### Scenario: The token cache is missing
- **WHEN** A plan run measures a task group and the tiktoken cache is missing
- **THEN** The run fails with an error that names the missing cache and no character count is used

### Requirement: A created file counts its estimated lines
The stage SHALL add 32 tokens for each estimated line of a path in the `creates` of a task group to the token count of that group, and SHALL refuse a group whose `creates` path has no line estimate with an error that names the path.

#### Scenario: A group creates a 1,500-line file
- **WHEN** A task group has a `creates_lines` entry with a 1,500-line estimate and no other input
- **THEN** The stage counts the group as at least 48,000 tokens and refuses it as over a 40,000-token budget

#### Scenario: A creates path has no estimate
- **WHEN** A task group creates a file and the reply gives no line estimate for that path
- **THEN** The stage refuses the group with an error that names the path

### Requirement: The staging prompt states the budget and the estimate rule
The staging prompt SHALL name the `budget` of the run as the most tokens of one step and the rule that each `creates` path carries a line estimate.

#### Scenario: The prompt states both limits
- **WHEN** The staging prompt of a plan run is loaded
- **THEN** It names the `budget` of the run and the line-estimate rule for each `creates` path

### Requirement: The stage job checks the form of the plan title
The stage job SHALL run `title_problems` on the title that it builds for the plan. A reply whose title has a problem SHALL go back to the model once with the problems, and a second reply with a problem SHALL stop the item.

#### Scenario: A summary that repeats plan
- **WHEN** the first reply has the summary `plan the form of a task`
- **THEN** the job sends the problem that names the word `plan` to the model, and the second reply sets the title

#### Scenario: A summary with the issue number
- **WHEN** the reply has the summary `Stop #1 dropping a comment` for issue 1, and the second reply is the same
- **THEN** the job sends a problem that names `#1`, and the item makes no plan

### Requirement: A task group writes no living spec
A `StageGroup` SHALL reject a path under `openspec/specs/` in `changes` or in `creates`, with a validation error that names the path and says that only `openspec archive` writes living specs. A path under `openspec/specs/` in `reads` SHALL stay accepted.

#### Scenario: A group lists a living spec in changes
- **WHEN** A `StageGroup` lists `openspec/specs/config-commands/spec.md` in `changes` and `creates`
- **THEN** validation fails, and the error names `openspec/specs/config-commands/spec.md` and says that only `openspec archive` writes living specs

#### Scenario: A group lists a living spec in creates
- **WHEN** A `StageGroup` lists `openspec/specs/new-capability/spec.md` in `changes` and `creates`
- **THEN** validation fails, and the error names `openspec/specs/new-capability/spec.md`

#### Scenario: A group writes a source file and reads a living spec
- **WHEN** A `StageGroup` lists `src/devops_cli/sample.py` in `changes` and `openspec/specs/config-commands/spec.md` in `reads`
- **THEN** validation succeeds

### Requirement: The stage prompt states the living-spec rule
The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL state that a task group never puts a path under `openspec/specs/` in `changes` or in `creates`, and that `openspec archive` writes living specs.

#### Scenario: The prompt holds the living-spec rule
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the text says that a task group must not change or create a file under `openspec/specs/`, and that `openspec archive` writes living specs

### Requirement: A title whose summary is over the limit is refused
The stage job SHALL refuse an item whose issue title has a Conventional Commit type and a summary longer than `SUMMARY_MAX_CHARS` UTF-16 code units, counted by `summary_length`.

#### Scenario: A summary of 61 UTF-16 units is refused
- **WHEN** A Ready item has a valid Conventional Commit type and a title summary of 61 UTF-16 code units
- **THEN** The stage job leaves the item out, and its reason names the current length and the limit of 60

#### Scenario: A summary of 60 UTF-16 units passes the length check
- **WHEN** A Ready item has a valid Conventional Commit type and a title summary of 60 UTF-16 code units
- **THEN** The stage job does not refuse the item for the length of its summary

#### Scenario: A title with no type keeps its reason
- **WHEN** A Ready item has a title with no Conventional Commit type and a summary longer than the limit
- **THEN** The stage job leaves the item out and its reason names the missing type, not the length of the summary

### Requirement: An open finding keeps the plan in draft
When the last review of a plan returns a finding that has a quote in its input or in a tool answer of the run and a defect type of `missing_path`, `false_premise`, `ignores_existing_code`, `task_order`, `verify_form`, `spec_delta_wrong` or `criterion_dropped`, or a finding that reports a placeholder with a quote in its request, the stage SHALL keep the plan pull request in draft, apply the label `plan/needs-fix` to it, and put those findings at the top of the stage comment.

#### Scenario: A placeholder finding from a fake client
- **WHEN** The fake verification client returns a placeholder finding whose quote is in the input.
- **THEN** The plan pull request is a draft, it holds the label `plan/needs-fix`, and its stage comment starts with the finding text.

#### Scenario: A clean review stages as today
- **WHEN** The fake verification client returns no finding with a quote in the input and an open defect type.
- **THEN** The stage opens the plan pull request as today and applies no `plan/needs-fix` label.

#### Scenario: A later clean round clears the label
- **WHEN** A stage round verifies a plan that holds `plan/needs-fix` and returns no open finding.
- **THEN** The stage removes the label from the pull request.

#### Scenario: An open task order finding
- **WHEN** The last review returns a `task_order` finding whose quote is in the input.
- **THEN** The plan pull request is a draft and it holds the label `plan/needs-fix`.

#### Scenario: A placeholder only in a tool answer
- **WHEN** The verifier reports a placeholder whose quote is in a tool answer and not in its request.
- **THEN** The finding is not open.

#### Scenario: A quoted dropped criterion finding is open
- **WHEN** A verification reply holds a `criterion_dropped` finding whose quote is in the issue.
- **THEN** `open_findings` returns the finding.

#### Scenario: An unquoted dropped criterion finding is advice
- **WHEN** A verification reply holds a `criterion_dropped` finding whose quote is in none of the issue, the plan and the cited files.
- **THEN** `open_findings` returns no finding.

#### Scenario: A test-only group with no code
- **WHEN** A group of a plan changes only a fixture file and a test file, no group changes the code that its criterion needs, and the verification reply holds a `criterion_dropped` finding that quotes the criterion of the issue.
- **THEN** `open_findings` returns the finding and `returning` returns none.

### Requirement: A plan with an open finding is a failed attempt
An item whose plan carries an open finding SHALL NOT count as a staged plan in the round budget of the Service, and its result SHALL be recorded as a failed attempt of failure class `plan_defect`.

#### Scenario: The round counts a plan with an open finding
- **WHEN** The stage records an open finding for an item and the Service counts the round.
- **THEN** The round budget counts no staged plan for the item, and the failure record of the item has class `plan_defect`.

### Requirement: A task group writes no file under openspec/changes
A `StageGroup` SHALL reject a path in `changes` or `creates` that is `openspec/changes` or that starts with `openspec/changes/`, and SHALL accept such a path in `reads`.

#### Scenario: A change-folder path in changes
- **WHEN** a `StageGroup` sets `changes` to `openspec/changes/3060-model-tier-ladder/proposal.md`
- **THEN** validation fails with a message that names that path and the rule

#### Scenario: A change-folder path in creates
- **WHEN** a `StageGroup` sets `creates` and `changes` to `openspec/changes/3060-model-tier-ladder/tasks.md`
- **THEN** validation fails with a message that names that path

#### Scenario: The change folder itself
- **WHEN** a `StageGroup` sets `changes` to `openspec/changes`
- **THEN** validation fails

#### Scenario: A change-folder path in reads
- **WHEN** a `StageGroup` sets `reads` to `openspec/changes/3060-model-tier-ladder/proposal.md` and changes `src/devops_cli/roadmap/stage/stage_change.py`
- **THEN** validation succeeds

### Requirement: The path check reports a change-folder path
`path_problems` SHALL report a group path that is `openspec/changes` or that starts with `openspec/changes/`, in the place where the group names it, so that `check_proposal` refuses a recorded plan that skipped the schema.

#### Scenario: A recorded group that creates a change file
- **WHEN** `path_problems` runs on a group built without validation that creates `openspec/changes/3060-model-tier-ladder/proposal.md`
- **THEN** it returns one problem that names the group, the path and the rule

#### Scenario: A recorded group that only reads a change file
- **WHEN** `path_problems` runs on a group that reads `openspec/changes/3060-model-tier-ladder/proposal.md` in a tree that holds that file
- **THEN** it returns no problem

### Requirement: The stage prompt forbids a change-folder write
The roadmap stage prompt SHALL state that an implementation group must not change or create a path under `openspec/changes/`.

#### Scenario: The prompt states the rule
- **WHEN** the prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` is read
- **THEN** it holds a sentence that names `openspec/changes/` and forbids the change and the creation of a path under it

### Requirement: A move group names every module of its prefix
The stage plan check SHALL refuse a group that moves a top-level Python module by name prefix and leaves another module of that prefix for no later group. A top-level module is a `.py` file directly under the folder. A file whose name starts with `test_`, and `conftest.py`, is no module of a job prefix.

#### Scenario: A move group omits a module of its prefix
- **WHEN** The staged tree holds `src/devops_cli/roadmap/stage/stage_ready.py` and `src/devops_cli/roadmap/stage/stage_verify.py`, and one group lists `src/devops_cli/roadmap/stage/stage_ready.py` in `changes` and `src/devops_cli/roadmap/stage/ready.py` in `creates`, with no later group.
- **THEN** `check_proposal` returns a problem that names `src/devops_cli/roadmap/stage/stage_verify.py`.

#### Scenario: A later group moves the missing module
- **WHEN** The staged tree holds `src/devops_cli/roadmap/stage/stage_ready.py` and `src/devops_cli/roadmap/stage/stage_verify.py`, the first group moves `stage_ready.py` into `stage/`, and a later group moves `stage_verify.py` into `stage/`.
- **THEN** `check_proposal` returns no problem for either module.

#### Scenario: A move group leaves a module of another prefix
- **WHEN** The staged tree holds `src/devops_cli/roadmap/stage/stage_ready.py` and `src/devops_cli/roadmap/status.py`, and a group moves `stage_ready.py` into `stage/`.
- **THEN** `check_proposal` returns no problem for `src/devops_cli/roadmap/status.py`.

#### Scenario: A move group leaves a test module
- **WHEN** The staged tree holds `src/devops_cli/roadmap/stage/stage_ready.py` and `tests/roadmap/stage/test_roadmap_stage_ready.py`, and a group moves `stage_ready.py` into `stage/`.
- **THEN** `check_proposal` returns no problem for `tests/roadmap/stage/test_roadmap_stage_ready.py`.

### Requirement: A move group verifies the whole prefix
The stage plan check SHALL refuse a move group whose `! git grep` verify literal equals the import path of one top-level module of the moved prefix, the bare prefix included.

#### Scenario: A move group verifies one sampled import
- **WHEN** A move group for prefix `stage` gives the verify command `! git grep -n -F devops_cli.roadmap.stage.stage_ready src/ tests/`.
- **THEN** `check_proposal` returns a problem that says the verify command must cover the prefix.

#### Scenario: A move group verifies the bare prefix
- **WHEN** A move group for prefix `stage` gives the verify command `! git grep -n -F devops_cli.roadmap.stage.stage src/ tests/`.
- **THEN** `check_proposal` returns a problem, because the literal names `stage.py` and matches the new `stage/` package.

#### Scenario: A move group verifies the dotted prefix
- **WHEN** A move group for prefix `stage` gives the verify command `! git grep -n -F devops_cli.roadmap.stage_ src/ tests/`.
- **THEN** `check_proposal` returns no problem about the verify command.

### Requirement: The stage prompt asks for every module of a prefix
The stage prompt SHALL tell the planner to list every module of a moved name prefix in the group `changes` and to give a `verify` command that covers the prefix, with the layout invariant test or with a `! git grep` literal that names no single module.

#### Scenario: The stage prompt describes a prefix move
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** The prompt text tells the planner to name every module of the prefix, not the entry module only, and to verify the prefix.

### Requirement: The stage context lists an overlapping pull request
The stage context builder SHALL list each open pull request that changes a path that the item body cites, with its number, title, state and the shared paths.

#### Scenario: A fake pull request changes a cited path
- **WHEN** A test gives the builder a fake client that holds pull request 3173, which changes `docs/TELEMETRY.md`, and an item body that cites `docs/TELEMETRY.md`.
- **THEN** The context holds one entry with number 3173, its title, its state and `docs/TELEMETRY.md`.

#### Scenario: A fake pull request changes a path that no item body cites
- **WHEN** A test gives the builder a fake client that holds pull request 3173, which changes `docs/TELEMETRY.md`, and an item body that cites only `src/devops_cli/roadmap/stage/stage.py`.
- **THEN** The context holds no overlap entry.

### Requirement: A plan pull request carries a plan mark
The stage context builder SHALL mark an open pull request whose title has the type `docs(openspec)` as a plan pull request.

#### Scenario: A plan pull request overlaps a cited path
- **WHEN** A test gives the builder a fake client that holds pull request 3252, titled `docs(openspec): plan #3252 stage context`, which changes `src/devops_cli/roadmap/stage/stage_overlap.py`, and an item body that cites that path.
- **THEN** The context entry holds the number, the title, the state, the plan mark and `src/devops_cli/roadmap/stage/stage_overlap.py`.

#### Scenario: A pull request that is no plan carries no mark
- **WHEN** A test gives the builder a fake client that holds pull request 3253, titled `feat(roadmap): stage context`, which changes `src/devops_cli/roadmap/stage/stage.py`, and an item body that cites that path.
- **THEN** The context entry holds the number and no plan mark.

### Requirement: A cited metric lists its other senders
For each cited metric name, the stage context builder SHALL list the other files that hold the name, from `git grep -w` at the staged commit.

#### Scenario: A cited counter lists the files that hold its name
- **WHEN** A test gives the builder an item body that cites `devops_cli_github_requests_total` and a staged tree that holds the name in two files.
- **THEN** The context lists `src/devops_cli/telemetry/instruments.py` and `docs/TELEMETRY.md` under the cited name.

#### Scenario: A name that `INSTRUMENTS` does not hold lists no sender
- **WHEN** A test gives the builder an item body that cites `devops_cli_dashboard_panel` and a staged tree that holds the name in one file.
- **THEN** The context lists no sender under that name.

### Requirement: The gate refuses an empty Dependencies part on an overlap
`check_proposal` SHALL refuse a reply whose `dependencies` field is empty when the context lists an overlap, and SHALL name the pull request and the shared path.

#### Scenario: An overlap with an empty Dependencies field
- **WHEN** `check_proposal` gets a reply whose `dependencies` field is empty and a context that lists pull request 3173 on `docs/TELEMETRY.md`.
- **THEN** The problems hold one sentence that names pull request 3173 and `docs/TELEMETRY.md`.

#### Scenario: A reply that names the overlap passes
- **WHEN** `check_proposal` gets a reply whose `dependencies` field names pull request 3173 and `docs/TELEMETRY.md`, and a context that lists that overlap.
- **THEN** The problems hold no sentence about the overlap.

### Requirement: The stage prompt states the Dependencies rule
The stage prompt SHALL tell the planner to write each overlap and each shared metric sender into the `dependencies` field.

#### Scenario: The prompt holds the Dependencies rule
- **WHEN** A test reads the stage prompt file.
- **THEN** The prompt holds a rule that names the `dependencies` field, the empty list and the overlap entry.

### Requirement: The overlap read costs a stated number of GitHub requests
The stage context builder SHALL read the open pull requests and their files in one GraphQL request for each 100 open pull requests, and SHALL state that count in the comment of the staged item.

#### Scenario: 150 open pull requests cost two requests
- **WHEN** A test gives the builder a fake client and 150 open pull requests.
- **THEN** The fake client records two GraphQL requests and no other request.

### Requirement: The stage check names the message file a task needs
The stage check SHALL return a problem that names `src/devops_cli/lang/en/messages.py` when a rendered task text of a group names `MESSAGES.roadmap` and no group lists that file in `changes`.

#### Scenario: A task text names a message without the message file
- **WHEN** A plan has a task text that names `MESSAGES.roadmap` and no group lists `src/devops_cli/lang/en/messages.py` in `changes`.
- **THEN** `content_problems` returns a problem that names `src/devops_cli/lang/en/messages.py`.

#### Scenario: A task text names a message with the message file
- **WHEN** A plan has a task text that names `MESSAGES.roadmap` and a group lists `src/devops_cli/lang/en/messages.py` in `changes`.
- **THEN** `content_problems` returns no problem about `src/devops_cli/lang/en/messages.py`.

#### Scenario: A task text names a dotted message entry
- **WHEN** A plan has a task text that names `MESSAGES.roadmap.some_entry` and no group lists `src/devops_cli/lang/en/messages.py` in `changes`.
- **THEN** `content_problems` returns a problem that names `src/devops_cli/lang/en/messages.py`.

### Requirement: The verification prompt names the missing path of a needed file
The verification prompt `src/devops_cli/ai/tasks/roadmap_stage_verify.md` SHALL name `missing_path` for a code change that needs a file that the plan does not change, and SHALL keep the type for a file that does not exist and that no earlier group creates.

#### Scenario: The prompt names the missing path type
- **WHEN** The verification prompt `src/devops_cli/ai/tasks/roadmap_stage_verify.md` is read.
- **THEN** The prompt states that a code change that needs an unchanged file is a `missing_path` finding.

#### Scenario: The prompt keeps the absent-file case
- **WHEN** The verification prompt `src/devops_cli/ai/tasks/roadmap_stage_verify.md` is read.
- **THEN** The prompt states that a file that does not exist and that no earlier group creates is a `missing_path` finding.

### Requirement: The stage job records the hits of a negative search
The stage job SHALL run the literal of each negative-search verify command on the staged tree with git grep and SHALL record the matching paths before it judges the reply.

#### Scenario: A negative search has staged hits
- **WHEN** The plan gives a negative-search verify command whose literal matches paths of the staged tree.
- **THEN** The job records each matching path under the literal and passes the record to check_proposal.

### Requirement: A negative search with no staged hit is refused
check_proposal MUST refuse a negative-search literal that the recorded evidence gives with no matching path.

#### Scenario: The literal finds nothing before the change
- **WHEN** The recorded evidence for a negative-search literal holds no matching path.
- **THEN** check_proposal returns a problem that says the search already passes before the change and proves nothing.

### Requirement: A negative search that a created module keeps is refused
check_proposal MUST refuse a negative-search literal when a source path that the plan creates has an import path that contains the literal.

#### Scenario: A created module matches the literal
- **WHEN** A group creates a source path under src/devops_cli/ whose import path contains the negative-search literal.
- **THEN** check_proposal returns a problem that says the search can never pass on the produced tree.

### Requirement: A negative search with a surviving hit is accepted
check_proposal MUST accept a negative-search literal when the recorded evidence holds a matching path and no created source path has an import path that contains the literal.

#### Scenario: A staged hit survives the change
- **WHEN** The recorded evidence holds a matching path and no created source path has an import path that contains the literal.
- **THEN** check_proposal returns no problem for that literal.

### Requirement: The stage prompt asks for the hit count of a negative search
The stage prompt MUST ask the planner to call search_code with the literal of each negative-search verify command and to quote the hit count in feasibility.

#### Scenario: The planner reads the prompt
- **WHEN** The stage job plans an item whose plan gives a negative-search verify command.
- **THEN** The prompt tells the planner to call search_code with the literal and to quote the hit count in feasibility.

### Requirement: The probe names the files of a cited bare name
When a cited path is no file at the root of the staging commit and the staged tree holds files with the same name under a folder, the stage probe SHALL name those files and give the existing file as the candidate.

#### Scenario: Cited bare name with a file under a folder
- **WHEN** The issue cites `stage_specs.py`, the staging commit holds no root `stage_specs.py`, and `src/devops_cli/roadmap/stage/stage_specs.py` is a file of the commit.
- **THEN** The probe line for `stage_specs.py` says the path is no file at the root of the staging commit, names `src/devops_cli/roadmap/stage/stage_specs.py` as the candidate, and lists `stage_specs.py` in `missing`.

#### Scenario: Cited root file lists no same-name file
- **WHEN** The issue cites `README.md` and the staging commit holds `README.md` at the root.
- **THEN** The probe reports `README.md` as a file of the staging commit and lists no other file.

#### Scenario: Missing path with no same-name file keeps its line
- **WHEN** The issue cites `src/devops_cli/never.py`, the staging commit holds no such file, and no file of the commit has the name `never.py`.
- **THEN** The probe reports the path as no file of the staging commit and names no candidate.

#### Scenario: Same-name files stay bounded
- **WHEN** Six files of the staged tree carry the name of the cited path and the root holds none of them.
- **THEN** The probe names at most five of them, in sorted order.

### Requirement: The first plan request has fixed caps and leaves a reserve for the tools
The first request of a plan run SHALL cap the context at `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` tokens and the body at `CONST_ROADMAP_STAGE_BODY_MAX_TOKENS` tokens, and a larger window SHALL NOT give a larger cap. Half of the window for the context, or one quarter for the body, SHALL cap it when that is less. For plain text, the request at the caps SHALL stay `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` tokens below the limit at which the run offers no tool.

#### Scenario: The context and the body at their caps
- **WHEN** a plan run has a window of 65536 tokens, and the context and the body of the item are longer than their caps
- **THEN** the context counts `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` tokens, the body counts `CONST_ROADMAP_STAGE_BODY_MAX_TOKENS` tokens, the first request counts at most the limit of 49152 tokens less `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS`, and the first request offers `read_spec`

#### Scenario: Code at the caps
- **WHEN** a plan run has a window of 65536 tokens, and the context and the body of the item are code, longer than their caps
- **THEN** the first request counts less than the limit of 49152 tokens, and the first request offers `read_spec`

#### Scenario: A large window
- **WHEN** a plan run has a window of 1048576 tokens, and the context and the body of the item are longer than their caps
- **THEN** the context counts `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` tokens and the body counts `CONST_ROADMAP_STAGE_BODY_MAX_TOKENS` tokens

#### Scenario: A small window
- **WHEN** a plan run has a window of 8192 tokens, and the context and the body of the item are longer than their caps
- **THEN** the context counts 4096 tokens and the body counts 2048 tokens

### Requirement: The context and the largest spec answer stay under half of the window
The context of the first plan request and the longest answer of `read_spec` SHALL together stay under half of the context window of the `analysis` task.

#### Scenario: The longest spec answer
- **WHEN** a test adds an answer of `CONST_ROADMAP_STAGE_SPEC_MAX_CHARS` characters to a context of `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` tokens
- **THEN** the sum is under 32768 tokens

### Requirement: The trace of a run records the tools that each request offered
`RunTrace` SHALL hold, for each model request of a run, the names of the function tools that the request offered, and an empty entry for a request that offered none. The combined trace of several runs SHALL hold the entries of every run in order.

#### Scenario: A run that loses its tools
- **WHEN** a scripted plan run reads a big file until the window limit takes the tools, and the model then gives its plan
- **THEN** the trace holds the tool names of the first request and an empty entry for the last request, and the entries equal the tools that the model saw

#### Scenario: Two runs
- **WHEN** `RunTrace.combined` gets two traces that hold one and two entries
- **THEN** the result holds the three entries in order

### Requirement: The window of the analysis task is documented with its source
The page `docs/roadmap/stage.md` SHALL state the `context_window` of the task `analysis` and the file that sets it, and the `max_input_tokens` of the model of that task and the file that sets it. The stated values SHALL equal the values in `k8s/devops/configmap.example.yaml` and `k8s/llm/gateway/config.yaml`.

#### Scenario: The page and the files agree
- **WHEN** a test reads the two files and the page
- **THEN** the page states 256,000 and `k8s/devops/configmap.example.yaml`, and 1,048,576 and `k8s/llm/gateway/config.yaml`, as the files hold them

### Requirement: The refine investigation request is measured against the tool-removal limit
A test SHALL build the first request of a refine investigation at a window of 65536 tokens, count its tokens as the run hook counts them, print the count with the limit of 49152 tokens, and assert that the request of a large item stays under the limit. Refine SHALL NOT change.

#### Scenario: A large item
- **WHEN** refine investigates an item with a body of 8192 tokens and three replies of 1000 tokens
- **THEN** the test prints the count and the limit, and the count is under 49152 tokens

### Requirement: A setting names the limit on Planned items
The setting `roadmap.stage.planned_limit` SHALL be the count of open Planned items at which the stage job plans only items with the priority `P0-Critical` or `P1-High`. It SHALL have the variable `DEVOPS_CLI_ROADMAP_STAGE_PLANNED_LIMIT`, the default 20 and a least value of 1. The example ConfigMap of the Service SHALL hold the default.

#### Scenario: The default
- **WHEN** no config file and no variable sets `roadmap.stage.planned_limit`
- **THEN** the limit is 20

#### Scenario: A config file and a variable
- **WHEN** the config file sets `roadmap.stage.planned_limit` to 7 and then the variable `DEVOPS_CLI_ROADMAP_STAGE_PLANNED_LIMIT` holds 9
- **THEN** the limit is 7 from the file and 9 with the variable

#### Scenario: A limit under 1
- **WHEN** the config file sets `roadmap.stage.planned_limit` to 0
- **THEN** loading the settings fails

### Requirement: The stage job plans only P0 and P1 items at the limit on Planned items
When the count of open Planned items is at `roadmap.stage.planned_limit` or over it, the stage job SHALL take only an item with the priority `P0-Critical` or `P1-High`. It SHALL leave out each other item that passes every other rule, with a reason that names the count, the setting and the two priorities. The item that `--item` names SHALL pass the limit. The count SHALL hold open items with the Status Planned only. The limit SHALL NOT apply to the filing of issues.

#### Scenario: At the limit
- **WHEN** 2 items are Planned, the limit is 2, and a Ready `P2-Medium` item passes every other rule
- **THEN** the job takes no item, and the reason of the Ready item names the count 2, the setting `roadmap.stage.planned_limit` and `P0-Critical or P1-High`

#### Scenario: Under the limit
- **WHEN** 1 item is Planned, the limit is 2, and two Ready items pass every other rule
- **THEN** the job takes both items

#### Scenario: An item of the highest priority
- **WHEN** 2 items are Planned, the limit is 2, and a Ready `P0-Critical` item and a Ready `P2-Medium` item pass every other rule
- **THEN** the job takes the `P0-Critical` item and leaves out the `P2-Medium` item with the reason of the limit

#### Scenario: The priorities that pass
- **WHEN** 2 items are Planned, the limit is 2, and a Ready `P0-Critical` item, a Ready `P1-High` item, a Ready `P2-Medium` item and a Ready `P3-Low` item pass every other rule
- **THEN** the job takes the `P0-Critical` item and the `P1-High` item, and leaves out the other two with the reason of the limit

#### Scenario: A closed item and an item of another Status
- **WHEN** 1 open item is Planned, 1 closed item is Planned, 1 item is Staged, and the limit is 2
- **THEN** the count is 1 and the job takes a Ready item

#### Scenario: A named item
- **WHEN** 2 items are Planned, the limit is 2, and `--item` names a Ready `P2-Medium` item
- **THEN** the job takes that item

#### Scenario: Another rule fails first
- **WHEN** 2 items are Planned, the limit is 2, and a Ready `P2-Medium` item is claimed by a person
- **THEN** the reason of that item is the claim, not the limit

#### Scenario: The command at the limit
- **WHEN** 1 item is Planned, the setting is 1, and `devops roadmap stage --plan` runs with a Ready `P2-Medium` item
- **THEN** the plan holds no branch, makes no model call, and lists the Ready item as left out with the reason of the limit

### Requirement: The stage prompt names a sample file by a bare name
The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL tell the planner to write a sample file that a test writes at run time, and that no group creates, as a bare name with no folder.

#### Scenario: The prompt holds the bare-name rule
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the text names `test_sample.py` as a bare name and says that a name with a folder is read as a path of the repository

### Requirement: A failed item is recorded in its job record
When the plan or a write of an item fails, the job SHALL record the time (`stage.failed_at`) and the class of the error (`stage.failed_error`) in the job record of the item. A run that stages the item or stops it on the budget SHALL clear both keys.

#### Scenario: A failure is recorded
- **WHEN** the model call fails for an item with the error class `AIClientError`
- **THEN** the job record of the item holds the time of the round and `AIClientError`

#### Scenario: The item is staged
- **WHEN** a run stages an item whose job record holds a failure
- **THEN** the job record of the item holds neither key afterwards

### Requirement: A failed item waits for the retry delay
The job SHALL leave an item out of the selection until the `RETRY_AFTER` wait of the class in `stage.failed_class` has passed since `stage.failed_at`, and SHALL take the other items in the same round. A missing or unknown class SHALL wait as `ci_infra`. `--item` SHALL take the item it names. A failure time that is no time SHALL hold the item for no time. No setting SHALL change the wait, and the job SHALL NOT store the time it waits until.

#### Scenario: The delay has not passed
- **WHEN** the item failed 59 minutes ago with the class `provider`
- **THEN** the job leaves the item out and takes the next item

#### Scenario: The delay has passed
- **WHEN** the item failed 1 hour ago with the class `provider`
- **THEN** the job takes the item again

#### Scenario: A refused plan waits longer
- **WHEN** the item failed 1 hour ago with the class `plan_defect`
- **THEN** the job leaves the item out, and takes it again 6 hours after the failure

#### Scenario: An item that changed does not wait
- **WHEN** the item failed with the class `head_moved`
- **THEN** the job takes the item in the next round

#### Scenario: A record with no class
- **WHEN** the job record holds `stage.failed_at` of 59 minutes ago and no `stage.failed_class`
- **THEN** the job leaves the item out, and takes it 1 hour after the failure

#### Scenario: A class that is unknown
- **WHEN** the job record holds a `stage.failed_class` that is no failure class
- **THEN** the item waits as `ci_infra` and the selection does not fail

#### Scenario: A person names the item
- **WHEN** the item failed 1 minute ago and a run names it with `--item`
- **THEN** the job takes the item

#### Scenario: A stale setting
- **WHEN** a config file still holds `roadmap.stage.retry_hours`
- **THEN** the settings load without error and the stage settings hold no such field

### Requirement: The row fails only when no item was handled
The stage row SHALL fail a round with the items that failed only when the round tried at least one item and staged or stopped on the budget none of them. A round in which one item failed and another was handled SHALL succeed. A round that tried no item SHALL succeed. An error that belongs to no item, such as a failed read of the repository, SHALL fail the round.

#### Scenario: One item fails and another stages
- **WHEN** three rounds each fail the plan of one item and stage another item
- **THEN** no round fails and the row is not suspended

#### Scenario: Every item fails
- **WHEN** three rounds each try one item and plan none
- **THEN** each round fails and names the item, and the row is suspended

#### Scenario: A failure outside any item
- **WHEN** three rounds each fail with an error that belongs to no item
- **THEN** each round fails and the row is suspended

### Requirement: The stage reply has no return path
The reply schema of the stage job SHALL hold no key `premise_failed`, and SHALL require the keys `summary`, `pull_request_body`, `why`, `what_changes`, `skip_specs`, `feasibility`, `existing_tool` and `groups`. A reply that breaks the schema SHALL go back to the model once, and a second such reply SHALL fail the item with no change to its Status and no comment. No reply of the model SHALL return an item to New. The job itself returns an item to New only where another requirement says so.

#### Scenario: A reply with only premise_failed
- **WHEN** a reply is `{"premise_failed": "x"}`
- **THEN** the schema refuses it and names the key `premise_failed` as unknown

#### Scenario: A filler value of premise_failed
- **WHEN** a reply sets `premise_failed` to each of `placeholder`, `x`, `none`, `probe`, `__PROBE__` and "Not yet: I need to inspect the repository first." and holds a valid plan
- **THEN** the schema refuses each reply, and the job does not return the item

#### Scenario: A premise text that states the premise holds
- **WHEN** a reply sets `premise_failed` to the text of #3193, #3109 or #3255, and #3109 quotes a probe line
- **THEN** the schema refuses each reply, and the job does not return the item

#### Scenario: A reply with no plan
- **WHEN** a reply is `{}`
- **THEN** the schema refuses it and names each missing key

#### Scenario: The job returns no item
- **WHEN** the job plans an item and the model answers with a refused reply twice
- **THEN** the item fails, its Status is unchanged, and the job writes no comment on it

### Requirement: A placeholder text is one rule
`is_placeholder` SHALL be true for the texts `x`, `y`, `probe`, `placeholder` and `none`, for `__PROBE__`, and for a text that starts with "Not yet:", with no case and no punctuation around the text. `ReplyText` SHALL apply that rule as a validator and SHALL raise the error type `placeholder_text`.

#### Scenario: The filler words
- **WHEN** `is_placeholder` reads `x`, `y`, `probe`, `__PROBE__`, `placeholder` and `none`
- **THEN** it is true for each

#### Scenario: The refusal of a task
- **WHEN** `is_placeholder` reads "Not yet: I need to inspect the repository first."
- **THEN** it is true

#### Scenario: A real text
- **WHEN** `is_placeholder` reads "The probe shows the path" and "x-ray the cache"
- **THEN** it is false for both

### Requirement: The stage job plans with the model of the stage task
The stage command and the stage round of the Service SHALL give the planner the model of the task `stage` as its toolbox model, and the call that splits the groups SHALL use the client of the task `stage`.

#### Scenario: The command asks for the stage model
- **WHEN** `devops roadmap stage --plan` plans an item
- **THEN** the command asks for the model of the task `stage`, and the planner offers its tools to that model

#### Scenario: A round asks for the stage model
- **WHEN** a round of the Service plans an item
- **THEN** the round asks for the model of the task `stage`

### Requirement: Refuse a What Changes path that no group lists
The proposal check SHALL return a problem when a repository path in a code span of a What Changes item is in neither the changes nor the creates list of any task group, and the path is not under the living spec folder.

#### Scenario: What Changes names a path that no group lists
- **WHEN** A proposal has a What Changes item with the code span `src/devops_cli/lang/en/messages.py`, and no group lists that path in `changes` or `creates`
- **THEN** `check_proposal` returns a problem that names the unlisted path

#### Scenario: What Changes names a path that a group changes
- **WHEN** A proposal has a What Changes item with the code span `src/devops_cli/roadmap/stage/stage_change.py`, and a group lists that path in `changes`
- **THEN** `check_proposal` returns no problem for that path

#### Scenario: What Changes names a path that a group creates
- **WHEN** A proposal has a What Changes item with the code span `src/devops_cli/roadmap/new_check.py`, and a group lists that path in `creates`
- **THEN** `check_proposal` returns no problem for that path

### Requirement: Ignore a What Changes item with no unlisted path
The proposal check SHALL accept a What Changes item when it holds no repository path in a code span, when each code span that is a repository path is listed by a task group, or when the path is under the living spec folder that `openspec archive` writes.

#### Scenario: What Changes item describes behaviour only
- **WHEN** A proposal has a What Changes item with no code span that is a repository path
- **THEN** `check_proposal` returns no problem for that item

#### Scenario: What Changes names a command in a code span
- **WHEN** A proposal has a What Changes item with the code span `uv run devops ci test`
- **THEN** `check_proposal` returns no problem for that code span

#### Scenario: What Changes names a path that openspec archive writes
- **WHEN** A proposal has a What Changes item with the code span `openspec/specs/roadmap-stage/spec.md`, and no group lists that path
- **THEN** `check_proposal` returns no problem for that path

#### Scenario: The replay runs the What Changes check without git
- **WHEN** The replay calls `check_proposal` with a proposal and the `StagedTree` of its facts, and no checkout
- **THEN** The replay returns the unlisted-path problem and makes no git call

### Requirement: The job returns an item whose premise needs an open plan
The stage job SHALL return an item to New when a cited path is missing at the staging commit and an open plan creates it. The stage job SHALL record each such open item in `refine.blocked_by` of the item. The stage job SHALL plan no change for the returned item. The stage job SHALL make no model call for the returned item.

#### Scenario: A missing path that an open plan creates
- **WHEN** the issue cites `src/devops_cli/roadmap/stage_constants.py`, the staging commit lacks it, and open item #3308 has a plan on the default branch whose `tasks.md` marks that path `(new)`
- **THEN** the stage job records #3308 in `refine.blocked_by` of the item, sets the item to New, and plans no change for it

#### Scenario: No model call for the returned item
- **WHEN** the premise probe of an item finds a dependency on an open plan
- **THEN** the stage job makes no model call for that item

### Requirement: The stage selection leaves out an item with an open recorded blocker
The stage selection SHALL leave out an item whose `refine.blocked_by` record names an open item. The reason SHALL name each open item.

#### Scenario: The recorded blocker is open
- **WHEN** an item's job record holds `refine.blocked_by` with #3308, and #3308 is open
- **THEN** the stage selection leaves out the item, and the reason names #3308

#### Scenario: The recorded blocker is closed
- **WHEN** an item's job record holds `refine.blocked_by` with #3308, and #3308 is closed
- **THEN** the stage selection does not leave out the item for that record

### Requirement: The stage check refuses an overlapping create path
The stage check SHALL refuse a plan that lists a path in `creates` that another open plan also creates. The problem SHALL name the path and the open item. The reply SHALL go back to the model once.

#### Scenario: Two open plans create the same module
- **WHEN** open item #3308's `tasks.md` marks `src/devops_cli/roadmap/stage_constants.py` with `(new)`, and the reply of the item lists the same path in `creates`
- **THEN** the check returns a problem that names the path and #3308

### Requirement: A closed plan is no dependency
The stage job SHALL ignore the plan of a closed item when it finds a dependency or an overlapping create path. The stage job SHALL ignore the plan of an archived change in the same way.

#### Scenario: A closed item's plan names the same path
- **WHEN** a closed item's active change folder on the default branch lists the cited path as `(new)`
- **THEN** the stage job records no dependency on that item, and the check accepts a reply that lists the path in `creates`

#### Scenario: An archived change names the path
- **WHEN** the change folder of an open item is archived on the default branch, and it lists the cited path as `(new)`
- **THEN** the stage job records no dependency on that item, and the check accepts a reply that lists the path in `creates`

### Requirement: The missing-path message names both forms
The message of a path that the staged tree lacks SHALL name the `creates` list of a stage reply and the ` (new)` mark of the `Changes:` line of `tasks.md`.

#### Scenario: A group names a missing file
- **WHEN** `path_problems` judges a group that names `src/devops_cli/new_module.py` and no group creates it
- **THEN** the problem holds `creates`, ` (new)` and `Changes:`

#### Scenario: A plan omits the mark
- **WHEN** the plan check reads a change folder whose group 3 `Changes:` line names four new case files with no ` (new)` mark
- **THEN** each of the four problems holds ` (new)` and `Changes:`

### Requirement: The missing-path message keeps its hint
The missing-path message SHALL end with the hint that names the tracked files of the same name, or that states that no file has the name.

#### Scenario: A tracked file has the same name
- **WHEN** the tree holds `src/devops_cli/roadmap/stage/stage.py` and a group names `src/devops_cli/new/stage.py`
- **THEN** the problem ends with the text of `stage_path_same_name` for `stage.py`

#### Scenario: A later group creates the path
- **WHEN** group 1 names `src/devops_cli/new_module.py` and group 3 lists it in `creates`
- **THEN** the problem names group 3 and holds neither `creates` nor ` (new)`

### Requirement: The module docstring names both readers
The module docstring of `stage_paths.py` SHALL state that `path_problems` judges both the stage reply and the change folder.

#### Scenario: A reader opens the module
- **WHEN** a test reads the module docstring of `src/devops_cli/roadmap/stage/stage_paths.py`
- **THEN** the docstring holds `change folder` and `reply`

### Requirement: The tuicr bullet needs a source change
The task renderer SHALL add the tuicr review bullet only when at least one task group changes a path under `src/`.

#### Scenario: A plan that changes no source omits the bullet
- **WHEN** a plan has groups that change no path under `src/`
- **THEN** the rendered `tasks.md` holds no bullet that starts with `Pending a person: review the diff in tuicr`.

#### Scenario: A plan that changes source gets the bullet
- **WHEN** a plan has one group that changes `src/devops_cli/roadmap/stage/stage_change.py`
- **THEN** the rendered `tasks.md` holds the tuicr review bullet.

### Requirement: An empty workflow follow-up section is omitted
The task renderer SHALL write the `## Workflow follow-up` heading only when it holds a bullet.

#### Scenario: No follow-up bullet leaves no section
- **WHEN** a plan has no workflow follow-up bullet
- **THEN** the rendered `tasks.md` holds no `## Workflow follow-up` heading.

### Requirement: A document task starts with the Edit verb
The task renderer MUST prepend the fixed verb `Edit` to a documentation text whose first word is a path, and MUST write that path in a code span. A path is a word that holds `/` or ends in a dot and letters.

#### Scenario: A root document gets the Edit verb
- **WHEN** a group supplies the documentation text `SECURITY.md`
- **THEN** the rendered task starts with `Edit` and names `SECURITY.md` in a code span.

#### Scenario: A nested document in a code span gets the Edit verb
- **WHEN** a group supplies the documentation text `` `docs/TESTING.md` and `docs/SDLC.md` ``
- **THEN** the rendered task reads `Edit` followed by the two paths in code spans.

### Requirement: A document task keeps its own verb
The task renderer MUST keep a documentation text whose first word is not a path unchanged.

#### Scenario: An existing verb has no double verb
- **WHEN** a group supplies the documentation text `Document the fix in `docs/TESTING.md``
- **THEN** the rendered task starts with `Document` and holds no `Edit Document`.

### Requirement: The documentation field starts with an imperative verb
The stage prompt SHALL state that the `documentation` field starts with an imperative verb, names each document in a code span, and is `null` when the step changes no document.

#### Scenario: The prompt states the documentation rule
- **WHEN** a test reads the stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the prompt states the imperative verb rule, the rule that names each document, and the `null` rule for a step that changes no document.

### Requirement: A documentation task runs the regeneration step for a command change
A documentation task SHALL end with the command `uv run devops docs generate --sync-readme` only when the group changes a path under `src/devops_cli/commands/` or `src/devops_cli/lang/`. A documentation task of any other group SHALL hold the documentation text and no regeneration command.

#### Scenario: A group that changes a document only
- **WHEN** a group has a `documentation` task and changes only `SECURITY.md`
- **THEN** its last task holds the documentation text with no regeneration command, and its `Verification:` line holds `uv run devops ci docs`

### Requirement: The staged commit is the default branch of origin
A round SHALL take as the staged commit the commit of `origin/<default branch>` that it fetched, not the HEAD of the clone. Before it plans a selected item, the job SHALL move the clone to the staged commit with a fast-forward merge. A clone that does not hold the staged commit after that merge SHALL fail the run. The premise probe, the path check and the tools SHALL read the staged commit.

#### Scenario: A path that origin gains after the clone was made
- **WHEN** `origin` gains the file `src/devops_cli/new_role.py` after the clone was made, and the issue cites that path
- **THEN** the probe line for the path says that the path is a file of the staging commit

#### Scenario: The clone moves to the staged commit
- **WHEN** the job plans an item and the clone was made before the last commit of `origin/main`
- **THEN** HEAD of the clone equals the commit of `origin/main` after the run

#### Scenario: A clone that has diverged from origin
- **WHEN** the default branch of the clone holds a commit that `origin/main` lacks, and `origin/main` holds a commit that the clone lacks
- **THEN** the run fails with the reason of git, no item is staged, and the model is not called

#### Scenario: A clone that is ahead of origin
- **WHEN** the default branch of the clone holds a commit that `origin/main` lacks, and `origin/main` holds no commit that the clone lacks
- **THEN** the run fails, no item is staged, and the model is not called

#### Scenario: The report names the staged commit
- **WHEN** the job plans a round with a selected item
- **THEN** the report of the plan names the staged commit

#### Scenario: The dry run lists the move of the clone
- **WHEN** `devops roadmap stage --dry-run` runs
- **THEN** the git commands move the clone to the staged commit before the tracked files are read, and the worktree of each item starts at the staged commit

### Requirement: A staged branch starts at the staged commit
The job SHALL make the commit of a staged item on the staged commit of its round, so that the probe and the plan read one commit. Before it pushes, the job SHALL fetch the default branch and rebase the commit onto it, so that the pushed branch holds the default branch. A conflict SHALL abort the rebase and fail the item with nothing pushed. When the job takes over a pushed branch of the item, the branch SHALL keep its own tip.

#### Scenario: origin moves after the round read the default branch
- **WHEN** `origin/main` gains a commit after the round read it, and the job stages an item
- **THEN** the parent of the commit of the new branch is the tip of `origin/main`, and `main` has no commit that the new branch lacks

#### Scenario: The rebase conflicts
- **WHEN** `origin/main` gains a file with the path of a file of the plan
- **THEN** the job aborts the rebase, pushes no branch, opens no pull request, and records the item as failed

### Requirement: A plan that adds a text rule carries its self-acceptance test
A plan with a behavior group that changes `src/devops_cli/roadmap/stage/stage_change.py` SHALL give a group test text that names `StageProposal`, `content_problems` and no problem, so the plan holds no text that its own rule refuses.

#### Scenario: Plan without the test is refused
- **WHEN** `check_proposal` receives a valid proposal with a behavior group that changes `src/devops_cli/roadmap/stage/stage_change.py` and no group test text that names `StageProposal`, `content_problems` and no problem.
- **THEN** `check_proposal` returns one problem that names `StageProposal` and `content_problems`.

#### Scenario: Plan with the test is accepted
- **WHEN** `check_proposal` receives a valid proposal with a behavior group that changes `src/devops_cli/roadmap/stage/stage_change.py` and a group test text that names `StageProposal`, `content_problems` and no problem.
- **THEN** `check_proposal` returns no self-acceptance problem.

### Requirement: A plan that changes no plan check needs no self-acceptance test
A plan whose groups change no path in `src/devops_cli/roadmap/stage/stage_change.py` MUST NOT be refused by the self-acceptance rule.

#### Scenario: Plan that changes another file is accepted
- **WHEN** `check_proposal` receives a valid proposal whose groups change only `src/devops_cli/roadmap/stage/stage.py`.
- **THEN** `check_proposal` returns no self-acceptance problem.

#### Scenario: Plan that only refactors the plan check is accepted
- **WHEN** `check_proposal` receives a valid proposal with an other group that changes `src/devops_cli/roadmap/stage/stage_change.py`.
- **THEN** `check_proposal` returns no self-acceptance problem.

### Requirement: The staging prompt states the self-acceptance test rule
The staging prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` MUST state the self-acceptance test rule beside the other checks of a plan.

#### Scenario: Prompt names the self-acceptance test
- **WHEN** A test loads the prompt with `load_task_prompt`.
- **THEN** The prompt text contains `StageProposal`, `content_problems` and the self-acceptance test rule.

### Requirement: The stage job checks each literal of a negative search
The stage job SHALL record the staged hits of each `-e` literal of a negative-search verify command, and check_proposal SHALL apply the rules of the negative search to each literal, the rule of the staged hit and the rule of the created module alike.

#### Scenario: One literal has no staged hit
- **WHEN** A group gives the verify command `! git grep -n -e old_name -e gone_name -- src/ tests/`, and the staged tree holds `old_name` but no `gone_name`.
- **THEN** check_proposal returns one problem that names the literal `gone_name` and says that the search already passes before the change.

#### Scenario: A move group names a module with a second literal
- **WHEN** A move group for prefix `stage` gives the verify command `! git grep -n -e devops_cli.roadmap.stage.stage_ready -e devops_cli.roadmap.stage.stage -- src/ tests/`.
- **THEN** check_proposal returns two problems: the problem of the move and the problem of the created module, and each names the literal `devops_cli.roadmap.stage.stage`.

### Requirement: A plan run counts each tool call by outcome
A plan run of the toolbox SHALL add 1 to `devops_cli_roadmap_tool_calls_total` for each tool call of the toolset. The labels SHALL be `tool`, `row` (`stage`), `toolset` (`base` or `extended`) and `outcome` (`ok`, `empty` or `error`). A call that no tool answers SHALL count as `error`.

#### Scenario: One call of each outcome
- **WHEN** a plan run calls `read_file` for a file with text, calls `search_code` for a text that no file holds, and calls `read_file` for a path outside the repository
- **THEN** the counter holds one point for each of the outcomes `ok`, `empty` and `error`, and each point has the labels `tool`, `row` `stage` and `toolset`

#### Scenario: A call that no tool answers
- **WHEN** a tool call is rejected, the run no longer offers the tool, or a limit stops the call
- **THEN** the call counts with `outcome` `error`

#### Scenario: A tool that the toolset does not offer
- **WHEN** the model calls a name that is no tool of the toolset
- **THEN** the counter holds no point with that name as `tool`

### Requirement: The tool that answers a call sets its outcome
Each tool of the stage planner SHALL set the `outcome` of its answer: `ok` for the result that the call asked for, `empty` for a call that ran and found nothing, and `error` for a call that could not run. A tool that sets no outcome SHALL give `ok`, or `empty` for an answer with no non-whitespace character.

#### Scenario: Each tool sets its own outcome
- **WHEN** a test calls each tool of the toolset `extended` that can find nothing with an argument that finds nothing, and each tool that can refuse with an argument that it refuses
- **THEN** the answer of each first call has the outcome `empty` and the answer of each second call has the outcome `error`

#### Scenario: A tool that sets no outcome
- **WHEN** a tool of a run answers with text, and a tool answers with white space only, and neither sets an outcome
- **THEN** the first call counts as `ok` and the second as `empty`

### Requirement: A plan run measures the size of each answer
A plan run SHALL observe `devops_cli_roadmap_tool_answer_chars` once for each tool call that got an answer, with the labels `tool`, `row` and `toolset`. The value SHALL be the count of characters of the answer after the cut of the tool. A call with no answer SHALL add no observation. The text of an answer with the outcome `error` is an answer.

#### Scenario: A long answer is cut
- **WHEN** a plan run reads a file of 300 long lines and the tool cuts the answer
- **THEN** the histogram observes the length of the cut answer that the model read, and not the length of the file

### Requirement: Each plan run gives every tool of its toolset a series
A plan run SHALL add 0 to `devops_cli_roadmap_tool_calls_total` with `outcome` `ok` for each tool of its toolset, before its first model request.

#### Scenario: A run that calls no tool
- **WHEN** a plan run with the toolset `base` makes no tool call
- **THEN** the counter holds nine points with the value 0 and `outcome` `ok`, one for each tool

### Requirement: A plan run measures its calls and the limit that ended its tools
A plan run that ends with a plan or a stop SHALL observe `devops_cli_roadmap_tool_calls_per_run` once, with its count of tool calls and the labels `row` and `toolset`. A run that raises because a model call failed SHALL observe no count of calls. A run that ends its tools on a limit SHALL add 1, once, to `devops_cli_roadmap_tool_limit_hits_total` with the labels `row`, `toolset` and `limit`. The `limit` SHALL be `calls`, `requests` or `window`.

#### Scenario: The three limits
- **WHEN** a plan run ends its tools because fewer calls are left than a turn needs, because one request is left, or because the messages fill the context window
- **THEN** the limit counter holds one point with `limit` `calls`, `requests` or `window` in that order

#### Scenario: A run stops at the call limit
- **WHEN** a plan run makes calls until the request that offers no tool because the call budget is spent
- **THEN** the histogram observes one run, and the limit counter holds one point with `limit` `calls`

#### Scenario: A run fills the context window
- **WHEN** a plan run reads a large file in each turn, with a context window of 12000 tokens
- **THEN** the limit counter holds one point with `limit` `window`

#### Scenario: One reply over the call limit
- **WHEN** one reply of the model holds one more parallel tool call than `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS`
- **THEN** the run fails, and the limit counter holds one point with `limit` `calls`

#### Scenario: A run whose model call fails
- **WHEN** the first call of a plan run is a tool call, and its second model request fails
- **THEN** the counter of calls holds the first call, and the histogram of calls per run holds no observation

### Requirement: The comment of a staged item counts the calls of each tool
The comment of an item that the toolbox planned SHALL add one line after the list of tool calls. The line SHALL name each tool that the plan runs called, in alphabetical order, with its count of calls and its count of empty answers, as `Tool calls: read_file=3 (empty=0), search_code=2 (empty=1)`. The comment SHALL hold no such line when the plan runs made no tool call.

#### Scenario: Two tools and one empty answer
- **WHEN** a plan run calls `read_file` twice and `search_code` once for a text that no file holds
- **THEN** the comment holds the line `Tool calls: read_file=2 (empty=0), search_code=1 (empty=1)`

#### Scenario: An item with two plan runs
- **WHEN** the first plan of an item is refused and each of the two plan runs calls `read_file` once
- **THEN** the line of the comment holds `read_file=2 (empty=0)`

#### Scenario: A run that made no tool call
- **WHEN** a plan run makes no tool call
- **THEN** the comment holds no line that starts with `Tool calls:`

### Requirement: A git command that runs out of time is an error
A tool of the stage planner whose git command runs out of time SHALL answer with the outcome `error` and a text that says so. It SHALL NOT answer that nothing was found.

#### Scenario: Each tool that runs git
- **WHEN** every git command of `search_code`, `list_files`, `read_file`, `git_log`, `git_show`, `callers` and `references` runs out of time
- **THEN** each answer has the outcome `error`, and its text says that the command ran out of time

### Requirement: The verification request fits the window of its task
The request and the run of the verifier SHALL use the context window of the task `verification`. With its instructions, the request SHALL stay `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` tokens below the point where the run offers no more tools.

#### Scenario: A request that does not fit the window
- **WHEN** the cited files of a plan do not fit the limit of the window of the task `verification`
- **THEN** the request keeps the cited files in plan order up to that limit, and drops the others

#### Scenario: A full request gets the tools
- **WHEN** the window of the task `verification` is 65536 tokens and a plan cites more files than fit
- **THEN** the first request of the run is offered the read tools

#### Scenario: The two tasks have different windows
- **WHEN** the task `stage` has a window of 262144 tokens and the task `verification` a window of 12000 tokens
- **THEN** the request of the verifier and the tool limit of its run follow the window of 12000 tokens

### Requirement: The comment lists every finding of each repair round
After the last repair round, the plan SHALL keep each open finding of the last review, and the comment SHALL list every finding of each round.

#### Scenario: The second repair round still has a finding
- **WHEN** the plan still has a return finding after the second repair round
- **THEN** the planner makes no further request, the job keeps the draft with the label `plan/needs-fix`, and the issue receives a comment with the findings

#### Scenario: The comment lists each repair round
- **WHEN** the verifier returns a return finding on each of the first two reviews, and no finding on the third
- **THEN** the planner makes two repair requests, and the comment of the item lists the two return findings

#### Scenario: A mixed first round
- **WHEN** the first review returns a `false_premise`, a `spec_delta_wrong` and a `contrived_test` finding with quotes, and the second review finds nothing
- **THEN** the planner gets the `false_premise` and the `spec_delta_wrong` finding, the comment lists all three, and no finding is open

### Requirement: The verifier reads the repository with the read-only tools
The verifier SHALL check the paths, the premise, the scope against the criteria, the task order, the spec delta and the verify commands of a plan with the read-only tools of the toolset of the run. It SHALL hold no tool that writes a file or runs a shell command. Each read of a verification run SHALL be recorded in the `RunTrace` of that run, and the comment of the staged item SHALL list each read with its path.

#### Scenario: The tool set of the verifier
- **WHEN** a verification run is built for a checkout and a commit with the toolset `base`
- **THEN** its tools are exactly the nine read tools of the toolset `base`

#### Scenario: A read is listed in the comment
- **WHEN** the verifier reads `src/devops_cli/roadmap/stage/stage_verify.py` during a run
- **THEN** the trace of the item holds that read, and the comment of the staged item lists the path

### Requirement: A review run has its own row in the metrics of the tool calls
A verification run SHALL send the metrics of its tool calls with the label `row` value `stage_verify`, and a plan run SHALL keep the value `stage`, so the reads of the verifier do not hide a tool that the planner does not use.

#### Scenario: A verification run calls a tool
- **WHEN** a verification run reads a file
- **THEN** `devops_cli_roadmap_tool_calls_total` holds that call with `row` `stage_verify`, and no point with `row` `stage`

### Requirement: A review run that stops names itself
When a verification run ends with no reply, the failure of the item SHALL name the verification run and SHALL NOT say that no plan was given.

#### Scenario: A verification run hits a limit
- **WHEN** the replies of a verification run pass `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS`
- **THEN** the job raises `RoadmapStageError` with the message of a stopped verification run

### Requirement: A title shows a tag as text
`staging_title` and `delivery_title` SHALL keep each tag of the summary as it is, because a title is plain text. GitHub shows a tag word in a title as text, and the check `Semantic PR title` counts its characters. They SHALL still change the `<` of a comment opener into `&lt;`. They SHALL still put a handle or a link in a code span. The schema SHALL count the summary as the title shows it.

#### Scenario: A word in angle brackets in a title
- **WHEN** `staging_title` receives item 3 and the summary `Reject <section>.<option> keys`, and `delivery_title` receives `fix(config): reject <section>.<option> keys`
- **THEN** the titles are `docs(openspec): plan #3 Reject <section>.<option> keys` and `fix(config): reject <section>.<option> keys`

#### Scenario: A comment opener in a title
- **WHEN** `staging_title` receives item 3 and the summary `Block <!-- hidden`
- **THEN** the title is `docs(openspec): plan #3 Block &lt;!-- hidden`

#### Scenario: A summary of the most characters with a tag
- **WHEN** the model gives a summary of the most characters that the schema accepts, and the summary ends with ` <b>`
- **THEN** the schema accepts the reply, and the title passes the form check

### Requirement: A plan that changes the stage prompt or a stage gate gives the eval replay task
The stage job SHALL refuse a plan whose groups change `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_form.py`, `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/roadmap/stage/stage_criteria.py` or `src/devops_cli/roadmap/stage/stage_eval_gates.py` unless one group task holds the command `uv run devops roadmap eval stage --replay` and the words `score`, `before` and `after`.

#### Scenario: Prompt change without a replay task
- **WHEN** A plan changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` and no group task holds the replay command with the before and after score.
- **THEN** `check_proposal` returns a problem that names the changed path and the replay command.

#### Scenario: Gate change without a replay task
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_eval_gates.py` and no group task holds the replay command with the before and after score.
- **THEN** `check_proposal` returns a problem that names the changed path and the replay command.

#### Scenario: Check module change without a replay task
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_paths.py` and no group task holds the replay command with the before and after score.
- **THEN** `check_proposal` returns a problem that names the changed path and the replay command.

#### Scenario: Replay command without the score
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_change.py` and one group task holds `uv run devops roadmap eval stage --replay` but not the words `score`, `before` and `after`.
- **THEN** `check_proposal` returns a problem that asks for the before and after score.

#### Scenario: Trigger path with a replay task
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_change.py` and one group task holds `uv run devops roadmap eval stage --replay`, `score`, `before` and `after`.
- **THEN** `check_proposal` returns no problem for the eval replay rule.

#### Scenario: Unrelated source change
- **WHEN** A plan changes only `src/devops_cli/roadmap/stage/stage.py`.
- **THEN** `check_proposal` returns no problem for the eval replay rule.

### Requirement: A plan pull request closed with no merge leaves a comment on the issue
In each run the job SHALL read the pull request that `stage.pr` names for each open New or Ready item whose plan is not on the default branch. For a pull request that is closed and not merged, the job SHALL post one comment on the issue with the marker of the stage job, the marker of a rejected plan, the number of the pull request and the reason. For an open or merged pull request it SHALL post none. With `--item` it SHALL read only the pull request of the named item.

#### Scenario: The pull request is merged or open
- **WHEN** the plan pull request of an item is merged, or is open
- **THEN** the job posts no comment on the issue and writes no `stage.rejected`

#### Scenario: The pull request closed with no merge
- **WHEN** the plan pull request of a Ready item is closed and not merged
- **THEN** the job posts one comment on the issue that holds both markers, the number of the pull request and the reason

#### Scenario: The item is named
- **WHEN** a person runs the job with `--item` for one item
- **THEN** the job reads the pull request of that item and of no other item

### Requirement: The reason is the last long comment of a person
The reason SHALL be the text of the last comment on the closed pull request that has more than `EVIDENCE_MIN_CHARS` characters, that a person with write access wrote, and that the Service bot did not write. The job SHALL mask secrets in the reason and cut it to `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS` tokens. When no comment qualifies, the comment on the issue SHALL say that no comment gives a reason, and the job SHALL still record the rejection.

#### Scenario: The last comment is one word
- **WHEN** a closed plan pull request holds a long comment of the owner and then the comment `rejected` of the owner
- **THEN** the comment on the issue holds the long comment and not the word `rejected`

#### Scenario: The newest long comment is not a reason
- **WHEN** the newest long comment on a closed plan pull request was written by the Service bot or by an account with no write access
- **THEN** the comment on the issue holds the newest long comment of a person with write access

#### Scenario: No comment gives a reason
- **WHEN** a closed plan pull request holds only the comment `rejected` of the owner
- **THEN** the comment on the issue says that no comment gives a reason, and the job still records the rejection

#### Scenario: The reason holds a secret
- **WHEN** the last long comment holds a token
- **THEN** the comment on the issue holds the masked text

### Requirement: A rejected plan returns the item to New
After the comment, the job SHALL clear every key of the stage record, write `stage.rejected` as JSON, and set a Ready item to New. An item that the same run stages again SHALL keep its Status. The job SHALL make each write for one item in the order: the delete of the branch, the comment, the Status with the record.

#### Scenario: A Ready item with a rejected plan
- **WHEN** a Ready item has a plan pull request that closed with no merge
- **THEN** the item is New, its record holds no `stage.branch`, no `stage.pr` and no `stage.ready`, and `stage.rejected` holds the number of the pull request, the hash of the text that the plan came from, the time of the close and the files that the reason names

#### Scenario: A person already returned the item
- **WHEN** an item that is New has a plan pull request that closed with no merge
- **THEN** the job posts the comment and writes the record, and the Status stays New

#### Scenario: A named Ready item is planned again
- **WHEN** a person runs the job with `--item` for a Ready item whose plan pull request closed with no merge, and the run stages a new plan for it
- **THEN** the item is still Ready, the record holds the new `stage.pr`, and the record holds no `stage.rejected`

### Requirement: A rejected plan loses its staged branch when only the Service wrote to it
For a rejected plan the job SHALL delete the staged branch of the record with the rule of a closed item: every commit of the branch past `origin/<default branch>` has the identity of the session as author or is a clean merge. When any other commit exists, the job SHALL keep the branch and say so in the plan. The job SHALL delete the branch only while it ends at the commit that the plan judged. A branch that is gone needs no delete.

#### Scenario: Only the Service wrote to the branch
- **WHEN** a plan pull request closed with no merge and its branch holds one commit by the session identity
- **THEN** the job deletes the branch from `origin`, and the item is no longer held by a pushed branch

#### Scenario: A person added a commit
- **WHEN** a plan pull request closed with no merge and its branch holds a commit by another author
- **THEN** the job keeps the branch, the plan lists it with its reason, and the comment and the record are still written

#### Scenario: A person pushed a commit after the plan
- **WHEN** a person pushes a commit to the branch after the plan judged it and before the job deletes it
- **THEN** the job keeps the branch, and the comment and the record are still written

#### Scenario: A named run with the branch pushed
- **WHEN** a person runs the job with `--item` for an item whose branch holds only commits of the session identity
- **THEN** the run deletes the branch, and the same run can stage the item

### Requirement: The job leaves out an item whose plan was rejected until its text or a named file changes
The job SHALL leave out an item that holds a `stage.rejected` record, and the reason SHALL name the pull request. The leave-out SHALL end when the hash of the text outside the refine section differs from the recorded hash, or when a commit on the default branch changed a file of the record after the close. The recorded hash SHALL be `stage.text_hash`. The rule SHALL apply to the rejections that the same run finds. `--item` SHALL overrule the rule.

#### Scenario: Nothing changed
- **WHEN** an item is Ready again, holds a `stage.rejected` record, its text hashes as recorded and no named file changed
- **THEN** the job leaves it out and the reason names the pull request

#### Scenario: A person edits the text
- **WHEN** a person edits the body of that item, and the pushed branch of the rejected plan was deleted
- **THEN** the job takes the item and the branch of the closed pull request holds nothing

#### Scenario: A named file changes
- **WHEN** a commit on the default branch changed a file that the reason names, after the pull request closed
- **THEN** the job takes the item

#### Scenario: A person edited the text before the job read the closed pull request
- **WHEN** a person edits the body of an item, and then closes its plan pull request, and the job reads the closed pull request in its next round
- **THEN** the job takes the item after the rejection, and does not wait for a second edit

#### Scenario: A refine round rewrites its section
- **WHEN** refine writes its section in the body and the text outside the section is the same
- **THEN** the job still leaves the item out

#### Scenario: The item is named
- **WHEN** a person runs the job with `--item` for that item
- **THEN** the job takes the item

#### Scenario: The same run finds the rejection
- **WHEN** a run finds a rejected plan whose branch a person deleted before the run
- **THEN** the run does not select the item

### Requirement: The plan request holds the reason of a rejected plan
The request of a plan call SHALL hold the key `rejected_plan` for an item whose record holds `stage.rejected`: the text of the newest comment that holds the marker of a rejected plan and that a trusted author wrote, without either marker and cut to `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS` tokens. A request for any other item SHALL hold no such key. The prompt SHALL say that the key holds the reason of a person and that the plan must not state again the premise that the reason shows to be false.

#### Scenario: An item that was rejected and then edited
- **WHEN** the job plans an item that holds `stage.rejected` after a person edited its body
- **THEN** the request holds `rejected_plan` with the reason and with no marker

#### Scenario: A named item whose rejection the same run finds
- **WHEN** a person runs the job with `--item` for an item whose plan pull request closed with no merge and the record has no `stage.rejected` yet
- **THEN** the request holds `rejected_plan` with the reason that the run copies to the issue

#### Scenario: An item that was never rejected
- **WHEN** the job plans an item with no `stage.rejected` record
- **THEN** the request holds no `rejected_plan` key

### Requirement: A staged item records the hash of its text
When the job stages an item, it SHALL record `stage.text_hash`: the hash of the text of the item outside the refine section that the plan came from. A rejected plan SHALL clear it, and a record that holds none SHALL take the hash of the text at the time of the read.

#### Scenario: The job stages an item
- **WHEN** the job stages a Ready item
- **THEN** the record holds `stage.text_hash` with the hash of the body outside the refine section

### Requirement: The verification prompt separates a dropped criterion from a test-only group that delivers its criterion
The prompt of the verification pass SHALL define `criterion_dropped` for a criterion whose group changes only test files while no group of the plan changes the code or the data that the criterion needs, and SHALL say that a group which changes only test files and tests code of an earlier group is no `criterion_dropped`.

#### Scenario: The prompt names the test-only group
- **WHEN** The prompt of the verification pass is read.
- **THEN** The line of `criterion_dropped` names a group that changes only test files, names the earlier group that changes the code, and says that such a group is no `criterion_dropped`.

### Requirement: Refuse a stale line citation
The plan check SHALL refuse a `path:line:text` citation when the cited line of the staged file does not hold the cited text.

#### Scenario: The line holds another text
- **WHEN** `feasibility` holds `src/sample.py:4:def f():` and line 4 of the staged `src/sample.py` holds `def g():`.
- **THEN** `check_proposal` returns a problem that names `feasibility` and `src/sample.py`.

### Requirement: Accept a true line citation
The plan check SHALL accept a `path:line:text` citation when the cited line of the staged file holds the cited text.

#### Scenario: The line holds the cited text
- **WHEN** `feasibility` holds `src/sample.py:4:def f():` and line 4 of the staged `src/sample.py` holds `def f():`.
- **THEN** `check_proposal` returns no problem that names `src/sample.py`.

### Requirement: Refuse a citation of an absent line
The plan check MUST refuse a citation when the reader returns no such path or the file holds no such line.

#### Scenario: The line number is past the end of the file
- **WHEN** `feasibility` holds `src/sample.py:99:def f():` and the reader returns the 10 lines of `src/sample.py`.
- **THEN** `check_proposal` returns a problem that names `feasibility` and `src/sample.py`.

### Requirement: Resolve a symbol citation
The plan check SHALL accept a `path:def name` or a `path:class name` citation when the staged file defines the symbol at any line.

#### Scenario: The definition moved
- **WHEN** `feasibility` holds `src/sample.py:def f` and the staged `src/sample.py` defines `def f(` at line 7.
- **THEN** `check_proposal` returns no problem that names `src/sample.py`.

### Requirement: Refuse an absent symbol
The plan check MUST refuse a symbol citation when the staged file holds no definition of the symbol.

#### Scenario: The file defines another symbol
- **WHEN** `feasibility` holds `src/sample.py:def f` and the staged `src/sample.py` defines only `def g(`.
- **THEN** `check_proposal` returns a problem that names `feasibility` and `src/sample.py`.

### Requirement: Scan the three evidence fields
The plan check SHALL scan `feasibility`, `why` and each line of `what_changes` for citations.

#### Scenario: A stale citation sits in what_changes
- **WHEN** a line of `what_changes` holds a citation of a line that holds other text.
- **THEN** `check_proposal` returns a problem that names `what_changes` and the cited path.

### Requirement: Judge no citation without file text
The plan check SHALL judge no citation when it holds no reader of the staged files.

#### Scenario: The check holds no reader
- **WHEN** `check_proposal` runs with no `read_text` callable and the plan holds a stale citation.
- **THEN** `check_proposal` returns no problem for that citation.

### Requirement: Compare a citation with collapsed white space
The plan check SHALL compare the cited text with the staged line after it collapses white space in both.

#### Scenario: The spacing differs
- **WHEN** `feasibility` holds `src/sample.py:4:def f():` and line 4 holds `def f():`.
- **THEN** `check_proposal` returns no problem that names `src/sample.py`.

### Requirement: The stage job reads the text of a cited file at the staged commit
The stage job SHALL pass `check_proposal` a reader that returns the text of a cited file at the staged commit, and the replay MUST pass no reader.

#### Scenario: The job holds the checkout and the commit
- **WHEN** the stage job holds the checkout and the staged commit, and a plan cites `src/sample.py`, and the reader is asked for its text.
- **THEN** the reply holds the lines of `src/sample.py` at that commit.

#### Scenario: The replay passes no reader
- **WHEN** the replay of the golden set calls `check_proposal` with no reader, and a plan cites `src/sample.py`.
- **THEN** the check judges no citation.

### Requirement: The stage prompt prefers a symbol citation
The stage prompt MUST tell the planner to cite a symbol instead of a line number when a line is not needed.

#### Scenario: The prompt states the symbol form
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** the text holds the `path:def name` form and the instruction to prefer it.

### Requirement: Two tasks of a plan state different work
`check_proposal` SHALL refuse two tasks whose normalized work text is the same, and SHALL name both task numbers and the group or groups of those tasks.

#### Scenario: Duplicate task in one group
- **WHEN** group 2 holds task 2.1 and task 2.3 with the same normalized work text
- **THEN** `check_proposal` returns a problem that names task 2.1, task 2.3 and group 2

#### Scenario: Duplicate task across two groups
- **WHEN** group 2 task 2.1 and group 4 task 4.2 hold the same normalized work text
- **THEN** `check_proposal` returns a problem that names task 2.1, task 4.2, group 2 and group 4

#### Scenario: Two tasks share a verification command
- **WHEN** group 3 task 3.1 and task 3.2 hold different work text and the same `Verification:` command
- **THEN** `check_proposal` returns no duplicate-task problem for task 3.1 and task 3.2

#### Scenario: A documentation task repeats an implementation task
- **WHEN** an `other` group 3 holds task 3.1 that adds a paragraph and task 3.2 that adds the same paragraph with the docs command
- **THEN** `check_proposal` returns a duplicate-task problem that names task 3.1 and task 3.2

#### Scenario: Work text that differs only in spacing and case
- **WHEN** group 1 task 1.1 and task 1.2 hold the same words with different runs of spaces and different case
- **THEN** `check_proposal` returns a duplicate-task problem for task 1.1 and task 1.2

### Requirement: The comment lists the named paths that moved
The stage job SHALL list each path that a group of the plan names under `reads` or `changes` and that a commit on the default branch changed after the plan's base.

#### Scenario: A named plan path changes on main
- **WHEN** The plan names `src/devops_cli/roadmap/stage/stage_change.py` under `reads` and a later commit on the default branch changes that file.
- **THEN** The comment of the staged item names `src/devops_cli/roadmap/stage/stage_change.py` and the commit that changed it.

#### Scenario: An unnamed path changes on main
- **WHEN** A commit after the base changes a file that no group of the plan names under `reads` or `changes`.
- **THEN** The comment of the staged item does not name that file.

### Requirement: A moved path gives its commits in log order
The stage job SHALL give the short hash and the subject of each commit that changed a listed path, in log order.

#### Scenario: Two commits change one named path
- **WHEN** Two commits after the base change a path that the plan names under `changes`.
- **THEN** The comment lists the two short hashes and subjects under that path in log order.

#### Scenario: No commit changes a named path
- **WHEN** No commit after the base changes a path that the plan names under `reads` or `changes`.
- **THEN** The comment of the staged item has no moved-file section.

### Requirement: The comparison reads the latest default branch
The stage job MUST fetch the default branch before it compares the plan's base with the default branch.

#### Scenario: The remote default branch advances
- **WHEN** A remote commit changes a named path after the stage job fetched the base.
- **THEN** The comment of the staged item lists that path and commit.

### Requirement: The prompt asks for the preconditions of a called function
The stage prompt SHALL ask for one `feasibility` line for each called function whose arguments need a checkout, a client or a network.

#### Scenario: The stage prompt loads
- **WHEN** The stage job loads `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** The prompt text names a checkout, a client and a network as preconditions to state in `feasibility`.

### Requirement: The plan body passes the plan form before the draft opens
The stage job SHALL build the body of the draft pull request with `build_plan_body` and SHALL NOT write a body that `plan_body_problems` refuses. A refused body SHALL go back to the model with the other problems of the reply, once, and a second refusal SHALL stop the item as a reply that fails its checks. A text with a closing keyword SHALL keep its own stop.

#### Scenario: The plan body passes
- **WHEN** the model gives a `pull_request_body` of 100 characters for issue 42
- **THEN** the draft pull request gets a body that `plan_body_problems` accepts

#### Scenario: A short body is returned once
- **WHEN** the first reply has a `pull_request_body` of 5 characters and the second reply has a text of 100 characters
- **THEN** the second request holds the problem of the short body, and the draft opens with the second body

#### Scenario: A second refusal stops the item
- **WHEN** both replies have a `pull_request_body` of 5 characters
- **THEN** the job stops the item, opens no draft pull request and pushes nothing

### Requirement: The comment states that the model chose no tool
The comment of a staged item whose plan runs made no tool call SHALL say on how many of the requests tools were offered, and that the model called none.

#### Scenario: A run that offered tools
- **WHEN** a plan run offers tools in its one request and the model gives its plan with no tool call
- **THEN** the comment says that the run offered tools on 1 of 1 request(s) and the model called none

### Requirement: A plan run whose window ends the tools too soon fails the item
When the context window ends the tools of a plan run or of a review run before the run made `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` tool calls, the run SHALL raise `RoadmapStageError`, whatever its reply is. The message SHALL name the window, the count of calls and the setting to raise. The job SHALL record that error for the item.

#### Scenario: The window ends the tools after one call
- **WHEN** a plan run has a window of 12000 tokens, reads a big file, and the window takes the tools after fewer calls than the least number
- **THEN** the run raises `RoadmapStageError` that names the window, `ai.tasks.stage.context_window` and the parent `ai.tasks.analysis.context_window`, though the model gave a valid plan

#### Scenario: The window ends the tools after the least number of calls
- **WHEN** a plan run has a window that ends the tools after `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` calls or more, and the model gives its plan
- **THEN** the run returns the plan

#### Scenario: A review run
- **WHEN** a review run has a window of 12000 tokens that ends its tools after fewer calls than the least number, and the model gives no finding
- **THEN** the run raises `RoadmapStageError` that names the window and `ai.tasks.verification.context_window`, and not `ai.tasks.stage.context_window`

#### Scenario: A review run whose window ends the tools after the least number of calls
- **WHEN** a review run has a window that ends the tools after `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` calls or more, and the model gives its findings
- **THEN** the run returns the findings

#### Scenario: The job records the window
- **WHEN** the stage job runs an item with a window of 8192 tokens, and the model answers a plan after one call
- **THEN** the item fails with `RoadmapStageError` and the reason names `ai.tasks.stage.context_window`

### Requirement: The planner window of the example ConfigMap fits a plan run
The context window of the task `analysis` in `k8s/devops/configmap.example.yaml` SHALL leave room, below the point where the run ends its tools, for the first plan request and `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` tool answers of the longest size.

#### Scenario: The example window
- **WHEN** a test reads the window of the task `analysis` in the example ConfigMap
- **THEN** the point where the run ends its tools is at least the tokens of the first request plus the tokens of the least number of long tool answers, and the window of 65536 tokens is below that point

### Requirement: The stage writes the mark before each verification command
The stage job SHALL write the code span of each `Verification:` line it writes as `$ ` followed by the command, for a task that tests, a task that implements and a task that documents, so that the implement step reads the command.

#### Scenario: A staged group
- **WHEN** the stage job writes the tasks of a `behavior` group with the `verify` command `uv run devops ci test tests/test_sample.py`
- **THEN** the `Verification:` line of each of its first two tasks holds the code span `$ uv run devops ci test tests/test_sample.py`, and `parse_task_groups` reads the command without the mark

### Requirement: The review window of the example ConfigMap fits a review run
The context window of the task `verification` in `k8s/devops/configmap.example.yaml` SHALL leave room, below the point where the run ends its tools, for the first review request with no cited file and `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` tool answers of the longest size. The task SHALL name its window, so it does not take the default window of the `ai` settings.

#### Scenario: The example window
- **WHEN** a test reads the window of the task `verification` in the example ConfigMap
- **THEN** the point where the run ends its tools is at least the tokens of the first review request plus the tokens of the least number of long tool answers, and the default window of 32768 tokens is below that point

### Requirement: The plan lists the registry and ratchet places that its changes need
The stage job SHALL build the registry and ratchet table from the module-level `REGISTRY_COUNTS` declarations of the test modules, and MUST NOT read a hand-copied table. The plan context SHALL list each matching entry with its `path:line`, and `check_proposal` MUST refuse a plan that adds a counted item and has no task whose text names the declared path.

#### Scenario: A new declaration appears in the table
- **WHEN** A test module adds a `REGISTRY_COUNTS` entry for a counted prefix, enum or table name.
- **THEN** The table builder returns that entry with its test path and line, and no hand-written table changes.

#### Scenario: New roadmap limit without a ratchet task
- **WHEN** A plan adds `DEFAULT_ROADMAP_EXAMPLE_LIMIT` and has no task for `tests/roadmap/test_roadmap_limit_classes.py`.
- **THEN** The context names `tests/roadmap/test_roadmap_limit_classes.py` and `check_proposal` returns a missing-path problem for it.

#### Scenario: New job write without one registry task
- **WHEN** A plan adds a write method and has no task for `tests/support/fakes/roadmap_store.py`.
- **THEN** The context names `tests/roadmap/test_roadmap_dry_runs.py`, the `WRITES` table in `tests/support/fakes/roadmap_store.py`, `tests/roadmap/test_roadmap_store_contract.py` and `src/devops_cli/roadmap/request_plan.py`, and `check_proposal` returns a problem for the fault-test path.

#### Scenario: A plan that names every listed place passes
- **WHEN** A plan adds a counted item and holds a task whose text names each declared path.
- **THEN** `check_proposal` returns no registry problem for that plan.

### Requirement: A test path in a docstring or a spec names a file of the commit
`check_proposal` SHALL fail when a test file path named in a Python docstring or in a spec names no file of the commit, and MUST add each such path to its refusal list.

#### Scenario: A spec names a missing test file
- **WHEN** A spec contains `tests/test_missing_example.py` and that file is absent from the commit.
- **THEN** The check reports `tests/test_missing_example.py` as a missing path.

#### Scenario: A plan changes a docstring with a stale test path
- **WHEN** A plan changes a Python file whose docstring names a test file that the commit does not hold.
- **THEN** `check_proposal` returns a problem that names the missing test path.

#### Scenario: A docstring that names a test file of the commit passes
- **WHEN** A Python file names `tests/roadmap/test_roadmap_limit_classes.py` in its docstring and the commit holds that file.
- **THEN** The check reports no missing path.

### Requirement: The planner prompt names the issue form of a dependency
The planner prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL state that a `dependencies` entry which starts with `#<number>:` names an issue that must be delivered first, and MUST keep the rule that names each overlap and each metric sender.

#### Scenario: The prompt-rules test reads the form
- **WHEN** the prompt-rules test reads the dependencies rule of `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the test finds the form `#<number>:` and the rule of the overlaps, and it passes

### Requirement: The stage prompt requires a modified requirement for a removed command
The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL require a `modified` requirement for each base requirement that names a command or an option that the issue removes or renames.

#### Scenario: The prompt states the rename rule
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the text holds a rule that names `modified`, a command or option that the issue removes or renames, and each base requirement that names the old name

### Requirement: The path gate names every caller of a function that a task changes
The path gate SHALL refuse a plan whose task clause adds a parameter, an argument or a keyword to a function, or adds one code span in parameter shape, and that leaves out a file under `src/` that calls the function. A clause ends at a `.`, a `:` or a `;` outside a code span. A decorator, an option or a constant in capitals is no parameter. A name that no module under `src/` defines with `def` is no function, and a call is a call of the name itself, as `ast` reads it.

#### Scenario: A task adds a parameter to a function
- **WHEN** A task text of a group holds the words Add a probes parameter to `check_proposal`
- **THEN** The caller check reads the function name `check_proposal`

#### Scenario: A task adds an argument to two functions
- **WHEN** A task text holds the words add the keyword-only argument `base_scenarios` to `check_gates` and `check_proposal`
- **THEN** The caller check reads the function names `check_gates` and `check_proposal`

#### Scenario: A task adds one code span in parameter shape
- **WHEN** A task text holds the words Add `known` to `build_import_graph`, or add `sampling: CallSampling | None = None` to `_build_anthropic_kwargs` and `_claude_messages`
- **THEN** The caller check reads `build_import_graph` from the first text, and `_build_anthropic_kwargs` and `_claude_messages` from the second

#### Scenario: A decorator or an option is no parameter
- **WHEN** A task text holds the words Add `@dry_run_class("request-plan")` to `run_benchmark`, or Add `--take-ownership` to `_build_helm_upgrade_cmd`
- **THEN** The caller check reads no function name

#### Scenario: A field of a model has no caller
- **WHEN** A task text holds the words add `constant_claims` to `StageProposal`, `StageProposal` is a class, and a file under `src/` calls `StageProposal()`
- **THEN** `path_problems` returns no problem about a caller of `StageProposal`

#### Scenario: A task adds a member to a class
- **WHEN** A task text holds the words Add `REVIEW = "review"` to `FailureClass`, or Add the property `added_names` to `TaskGroup`
- **THEN** The caller check reads no function name

#### Scenario: A name in the next clause
- **WHEN** A task text holds the words Add the method `_repair_scope` to the run: it takes the folder, and pass the same log to `_fix`
- **THEN** The caller check reads no function name

#### Scenario: Two files call the function
- **WHEN** The checkout holds `src/a.py` and `src/b.py`, each calls `check_proposal`, and a module defines it with `def`
- **THEN** The caller search returns `src/a.py` and `src/b.py`

#### Scenario: A longer name and a string are no call
- **WHEN** A file holds `scan_fix(log)` and a docstring that holds `_fix(log)`
- **THEN** The caller search for `_fix` does not return that file

#### Scenario: A class has no caller
- **WHEN** The function name is the name of a class, as `TaskGroup` is, and a file calls `asyncio.TaskGroup()`
- **THEN** The caller search returns no file

#### Scenario: The plan omits a caller file
- **WHEN** A plan changes `check_proposal` and its `changes` lists hold `src/devops_cli/roadmap/stage_eval_gates.py` and no `src/devops_cli/roadmap/stage.py`
- **THEN** `path_problems` returns a problem that names `check_proposal` and `src/devops_cli/roadmap/stage.py`

#### Scenario: The plan lists every caller file
- **WHEN** A plan changes `check_proposal` and its `changes` lists hold every file that the caller search returns
- **THEN** `path_problems` returns no problem about a caller of `check_proposal`

#### Scenario: The tree holds no checkout
- **WHEN** The path gate runs on a tree of a replay case, which holds no checkout
- **THEN** `path_problems` returns no problem about a caller

### Requirement: A prompt change lists the prompt-rule test
A task group that changes a path of the form `src/devops_cli/ai/tasks/roadmap_stage_*.md` SHALL list `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` in its `reads` or its `changes`, and `check_proposal` SHALL refuse a group that lists it in neither.

#### Scenario: A prompt change omits the prompt-rule test
- **WHEN** a group changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` and lists `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` in neither `reads` nor `changes`
- **THEN** `check_proposal` returns one problem that names the prompt path and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

#### Scenario: A prompt change reads the prompt-rule test
- **WHEN** a group changes `src/devops_cli/ai/tasks/roadmap_stage_change.md`, lists `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` in `reads`, and gives `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` as `verify`
- **THEN** `check_proposal` returns no problem about the prompt-rule test

#### Scenario: A change of another file is not refused
- **WHEN** a group changes `src/devops_cli/roadmap/stage/stage_change.py` and no group changes a `roadmap_stage_*.md` prompt
- **THEN** `check_proposal` returns no problem about the prompt-rule test

### Requirement: A prompt change verifies the prompt-rule test
A task group that changes a path of the form `src/devops_cli/ai/tasks/roadmap_stage_*.md` SHALL give a `verify` command that names `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. A group that gives `process` in place of `verify` SHALL get one problem that names the prompt path and the test path.

#### Scenario: A prompt change verifies another command
- **WHEN** a group changes `src/devops_cli/ai/tasks/roadmap_stage_split.md`, lists `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` in `reads`, and gives `uv run devops ci docs` as `verify`
- **THEN** `check_proposal` returns one problem that names the prompt path and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

#### Scenario: A prompt change gives a process
- **WHEN** a group changes `src/devops_cli/ai/tasks/roadmap_stage_change.md`, lists `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` in `changes`, and gives `process` with `verify` as `null`
- **THEN** `check_proposal` returns one problem that names the prompt path and the prompt-rule test path

### Requirement: The stage prompts name the prompt-rule test
Each prompt of the form `src/devops_cli/ai/tasks/roadmap_stage_*.md` SHALL state that a group which changes a prompt lists `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` and gives it as `verify`.

#### Scenario: The prompt-rule test pins the sentence
- **WHEN** `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` reads `roadmap_stage_change.md` and `roadmap_stage_split.md`
- **THEN** each prompt holds a sentence that names `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

### Requirement: A task group has the kind manifest
The stage group schema SHALL accept a group of kind `manifest` that has a `test`, an `implementation` and a `verify`, and no `process`.

#### Scenario: A manifest group validates
- **WHEN** A group has `kind: manifest`, a `test` that names `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml` in a code span, an `implementation`, and `verify: uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`.
- **THEN** `StageGroup.model_validate` returns a group whose `kind` is `manifest` and whose `process` is `None`.

#### Scenario: A manifest group has no case task
- **WHEN** A group has `kind: manifest` and `test: null`.
- **THEN** the validation error names the kind `manifest` and the missing `test`.

### Requirement: A manifest group renders its case first
`group_text` SHALL render the case task of a `manifest` group first, with `fails on the base` under it, and the work of the group second.

#### Scenario: The case comes before the work
- **WHEN** `group_text` renders a `manifest` group whose `test` names `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml` and whose `verify` is `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`.
- **THEN** the first task line holds the case text and a `Verification:` line that ends with `fails on the base`, and the second task line holds the work.

### Requirement: A case path forces the manifest kind
The stage form check MUST refuse a group of kind `other` that creates or changes a case path, and MUST name the kind `manifest` in the problem.

#### Scenario: An other group changes a promtool case
- **WHEN** An `other` group lists `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml` in `changes`.
- **THEN** `form_problems` returns one problem that names `other`, `manifest` and the path.

#### Scenario: A manifest group changes the case
- **WHEN** A `manifest` group lists that path in `changes`, its `test` names the path in a code span, and its `verify` is `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`.
- **THEN** `form_problems` returns no problem for the group.

### Requirement: The manifest verify runs a case of the group
The stage form check MUST refuse a `manifest` verify command that is not `uv run devops ci test ` followed by a path of the group.

#### Scenario: A devops command that runs no case
- **WHEN** A `manifest` group gives `uv run devops ci mutate tests/prometheus` as its verify command.
- **THEN** `form_problems` returns one problem that names the command and the `uv run devops ci test` form.

### Requirement: The planner prompt names the manifest kind
The planner prompt SHALL name the `manifest` kind, its case-first rule and its verify rule.

#### Scenario: Prompt and kinds agree
- **WHEN** the prompt-vs-rules test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md` and the names of `GroupKind`.
- **THEN** the test finds `manifest` in both and passes.

### Requirement: A plan number beside a constant matches the staged value
The plan check SHALL refuse a plan when a sentence names one known module-level integer constant of the staged tree, holds one candidate decimal number, and that number differs from the value of the constant.

#### Scenario: Summary bound mismatch
- **WHEN** A spec scenario says `SUMMARY_MAX_CHARS` is 40, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns one problem that names `SUMMARY_MAX_CHARS`, 40 and 60.

#### Scenario: Summary bound match
- **WHEN** A design decision says `SUMMARY_MAX_CHARS` is 60, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: A bound after the constant name
- **WHEN** A requirement says `SUMMARY_MAX_CHARS` holds 60 characters, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: A note reference beside the constant
- **WHEN** A requirement says `SUMMARY_MAX_CHARS` is 60 (#2714), and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: Two numbers in one sentence
- **WHEN** A design decision says `SUMMARY_MAX_CHARS` is 40, while the staged tree sets it to 60.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`, because the sentence is ambiguous.

### Requirement: A constant that the staged tree does not define is ignored
The plan check MUST skip a constant name that the staged tree does not define as a module-level integer assignment.

#### Scenario: New plan constant
- **WHEN** A design decision names `PLAN_SUMMARY_MAX_CHARS = 47`, and the staged tree does not define `PLAN_SUMMARY_MAX_CHARS`.
- **THEN** The check returns no problem about `PLAN_SUMMARY_MAX_CHARS`.

#### Scenario: Non-literal assignment
- **WHEN** A staged module sets `SUMMARY_MAX_CHARS` from a call, and the plan says `SUMMARY_MAX_CHARS` is 40.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: Ambiguous definition
- **WHEN** Two staged modules set `SUMMARY_MAX_CHARS` to different integers, and the plan says `SUMMARY_MAX_CHARS` is 40.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`, because the tree holds no one value.

### Requirement: The check reads constants without running staged code
The plan check MUST read the constant values with the Python `ast` module and MUST NOT import or execute a staged file.

#### Scenario: A staged module with a side effect
- **WHEN** A staged Python module writes a file at import, and the plan says `SUMMARY_MAX_CHARS` is 60.
- **THEN** The check writes no file and returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: An alias to another constant
- **WHEN** A staged module sets `BODY_MAX_CHARS = CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS` and another staged module sets `CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS = 1000`, and the plan says `BODY_MAX_CHARS` is 1000.
- **THEN** The check returns no problem about `BODY_MAX_CHARS`.

### Requirement: The task commands carry no constant claim
The plan check MUST NOT compare a number in `tasks.md` with a constant.

#### Scenario: Task command number
- **WHEN** `tasks.md` holds `SUMMARY_MAX_CHARS` and 40 in one command, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

### Requirement: The replay passes recorded constants
The stage eval replay MUST pass the constants of a case to the plan check and MUST read no git.

#### Scenario: Recorded constants
- **WHEN** A case records `SUMMARY_MAX_CHARS` as 60, and its spec scenario says 40.
- **THEN** The replay refuses the plan with the problem that names the constant, 40 and 60.

#### Scenario: A case with no constants
- **WHEN** A case records no constants.
- **THEN** The replay runs the check with an empty mapping and keeps the result it gives today.

### Requirement: The prompt asks for the staged value of a constant
The plan stage prompt SHALL tell the model to cite the staged value of each constant that the plan relies on, and to give no new name to the bound of a constant that the staged tree defines.

#### Scenario: Prompt rule
- **WHEN** The prompt rules test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** The text holds an instruction to cite the staged value of each constant that the plan relies on.

### Requirement: A stage round writes each item when the item is done
A stage round SHALL plan one selected item, write its result, and only then plan the next item. The result is the publish of a ready change, the return of a blocked item, or the stop comment of an item over the budget. A kill of the worker SHALL lose at most the item in progress.

#### Scenario: Kill between item 1 and item 2
- **WHEN** a round selects 3 items and the model call of item 2 raises a `BaseException` that no handler catches
- **THEN** item 1 has its pushed branch, its draft pull request, its record and its comment, and items 2 and 3 have no branch, no record and no comment

### Requirement: A stop ends a stage round after it records the finished items
A stop of the Service or rejected GitHub credentials SHALL end a stage round. The round SHALL record the failure of each item that failed before the stop, and SHALL keep the written result of each finished item. Any other error SHALL be the failure of one item, and the round SHALL go on.

#### Scenario: Stop of the Service in item 3
- **WHEN** item 1 is staged, the plan of item 2 fails, and the Service stops in the plan of item 3 of 4 items
- **THEN** item 1 stays staged, item 2 has a failure record, items 3 and 4 have no record and no comment, and the round ends with the stop

### Requirement: A stage round writes the unselected items first
A stage round SHALL write the removals of closed items and the rejections of items that it does not select before its first plan call. A rejection of a selected item SHALL be written after the plan of that item and before its publish. The round SHALL read the moved paths of an item just before it publishes that item.

#### Scenario: Removal and rejection of unselected items
- **WHEN** a round has a closed item with a staged branch, an item with a rejected plan that the round leaves out, and one item to plan
- **THEN** the removal and the rejection are written before the first plan call

#### Scenario: Rejection of a selected item
- **WHEN** a person names an item whose plan pull request was closed with no merge
- **THEN** the rejection is written after the plan of the item and before its publish, the staged branch of the rejected plan is deleted before the new push, and the Status of the item stays Ready

#### Scenario: A commit lands during the plan of item 2
- **WHEN** a commit that changes a path named by both plans lands on the default branch during the plan of item 2
- **THEN** the comment of item 1 lists no moved path and the comment of item 2 lists the path

### Requirement: A stage plan makes no GitHub write
`devops roadmap stage --plan` SHALL make no write to GitHub or to the remote repository, also when the round holds a removal or a rejection. It SHALL write at most the plan file of each item that it plans.

#### Scenario: Plan only
- **WHEN** the command runs with `--plan` on a roadmap that holds a removal, a rejection and a ready item
- **THEN** the store receives no write, no branch is pushed or deleted, no GitHub write request is sent, and the plan file of the ready item exists

### Requirement: A security trigger needs a security section
The proposal check SHALL refuse a plan that names a security trigger and holds no non-blank `security` text, and SHALL name the matched path or word in the refusal. A trigger word SHALL match as a word, with an optional plural ending, and SHALL NOT match inside a longer word.

#### Scenario: A plan changes SECURITY.md with no security text
- **WHEN** `check_proposal` receives a proposal whose group changes `SECURITY.md` and whose `security` field is empty
- **THEN** it returns a problem that names `SECURITY.md` and asks for a non-blank `## Security` section

#### Scenario: A task names a trigger word with no security text
- **WHEN** `check_proposal` receives a proposal whose task text names `credential` and whose `security` field is empty
- **THEN** it returns a problem that names `credential`

#### Scenario: A plan with security text passes
- **WHEN** the same proposal holds non-blank `security` text
- **THEN** it returns no security problem

#### Scenario: A plan with no trigger needs no security text
- **WHEN** `check_proposal` receives a proposal whose Changes, group paths and task texts name no trigger
- **THEN** it returns no security problem

#### Scenario: A trigger word inside a longer word is no trigger
- **WHEN** `check_proposal` receives a proposal whose task text says "Add a regression test" and whose `security` field is empty
- **THEN** it returns no security problem

#### Scenario: A trigger word as a whole word is a trigger
- **WHEN** `check_proposal` receives a proposal whose task text says "Change the egress policy of the pod" and whose `security` field is empty
- **THEN** it returns a problem that names `egress`

### Requirement: The security triggers are a fixed list of paths and words
The trigger paths MUST be the named constant `SECURITY_TRIGGER_PATHS` with a docstring, and every entry MUST be a path of the repository.

#### Scenario: The trigger paths exist
- **WHEN** a test resolves each entry of `SECURITY_TRIGGER_PATHS` from the repository root
- **THEN** every entry is a file or a directory of the commit

#### Scenario: A trigger path is missing
- **WHEN** an entry of `SECURITY_TRIGGER_PATHS` names no file and no directory
- **THEN** the test fails

### Requirement: The design file holds the security section
`render_change` SHALL write a non-blank `security` field as a `## Security` section of `design.md`, and SHALL write no such section when the field is blank.

#### Scenario: A plan with security text is rendered
- **WHEN** `render_change` renders a proposal whose `security` field holds non-blank text
- **THEN** `design.md` holds a `## Security` section with that text

#### Scenario: A plan with no security text is rendered
- **WHEN** `render_change` renders a proposal whose `security` field is empty
- **THEN** `design.md` holds no `## Security` section

### Requirement: The stage prompt names the security rule
The stage prompt MUST name the `security` key, the `## Security` section and the security trigger.

#### Scenario: The prompt and the reply agree
- **WHEN** a test reads `roadmap_stage_change.md` and the fields of `StageProposal`
- **THEN** the prompt names `security` and the trigger, and the keys of the reply are the fields of the proposal

### Requirement: The stage prompt asks for a count of a claimed set
The stage prompt SHALL ask the plan to give a count of the set that a claim about every member covers, from the `references` tool or from a probe line, and it SHALL ask the proposal rule of `openspec/config.yaml` to hold the same phrase.

#### Scenario: A claim about a set
- **WHEN** the test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the prompt holds `gives a count from a tool of the plan run or from a probe line`

#### Scenario: No tool counts the set
- **WHEN** the test reads the stage prompt
- **THEN** the prompt holds `the count is unverified`, `census command` and `verify` of the first group

#### Scenario: A member has no decision
- **WHEN** the test reads the stage prompt
- **THEN** the prompt holds `removed, restricted, or allowlisted with a reason` and `a member with no decision`

#### Scenario: The count of a claim of no members is above zero
- **WHEN** the test reads the stage prompt
- **THEN** the prompt holds `narrows the claim` and `follow-up issue`

#### Scenario: The issue gives examples of a larger set
- **WHEN** the test reads the stage prompt
- **THEN** the prompt holds `the set that the issue names` and `not the set of its examples`

#### Scenario: The prompt and the config keep one phrase
- **WHEN** the test reads `openspec/config.yaml` and the stage prompt
- **THEN** both files hold `gives a count from a tool of the plan run or from a probe line`

### Requirement: The plan check refuses no word of a requirement text
The plan check SHALL NOT refuse a plan for the word `every`, `all` or `no` in a requirement text, so a claim about a set is judged by its count and never by a word.

#### Scenario: A requirement text holds every
- **WHEN** the test builds a plan whose requirement text holds `every` and whose paths exist at the staged commit
- **THEN** `check_proposal` returns no problem that names the word

### Requirement: A split reply is judged by every gate of the first reply
The job SHALL judge the proposal that a split gives with the same call as the first reply, with the same arguments. A gate that finds a problem in the new groups SHALL send the reply back to the model with that problem, as it does for the first reply.

#### Scenario: A split changes a trigger path and runs no replay
- **WHEN** The first reply passes the gates, one group is over the budget, and the split gives a group that changes `src/devops_cli/roadmap/stage/stage_form.py` with no task that runs the replay of the stage job
- **THEN** the job sends the reply back with the problem of the `eval-replay` gate and makes three model calls

#### Scenario: A split drops a path of What Changes
- **WHEN** The first reply names a source file in What Changes and in a group, and the split gives groups that list that file nowhere
- **THEN** the job sends the reply back with the problem of the `what-changes` gate

#### Scenario: A split moves one module of a prefix
- **WHEN** The split gives a group that moves one module of a prefix to a subpackage and no group names the other module of the prefix in `changes`
- **THEN** the job sends the reply back with the problem of the `move-prefix` gate

#### Scenario: A split names a registry item and not its test module
- **WHEN** The split gives a group whose task names a registry item that a test module declares, and no task names the declared test module
- **THEN** the job sends the reply back with the problem of the `registry` gate

### Requirement: A staged item records its intent before the push
The job SHALL write the mark `stage.pending`, the branch name and the time as JSON, with one write of marks before it pushes the branch of an item. The write of the marks after the draft SHALL clear `stage.pending` with the other keys.

#### Scenario: The request cost of a staged item
- **WHEN** a round stages one item
- **THEN** the round writes the marks twice for that item, and the record holds no `stage.pending` at the end

### Requirement: An old intent mark with no recorded pull request gives an orphan
In each run the job SHALL look at the open items that hold `stage.pending` and no `stage.pr`, and SHALL use the branch name of the mark. A mark younger than 1 hour SHALL give no action. A branch that is not on `origin` SHALL give only the clear of the record.

#### Scenario: The marks write fails
- **WHEN** the write of the marks after the draft fails, and a later round runs after the mark is 1 hour old
- **THEN** the round closes the draft, deletes the branch and clears the record, and a following round plans the item again

#### Scenario: The worker dies after the push
- **WHEN** the worker dies after the push and before the draft, and a later round runs after the mark is 1 hour old
- **THEN** the round deletes the branch, makes no request to close a draft and clears the record

#### Scenario: A retitle changes the slug
- **WHEN** a person changes the title of the item between the failure and the next round
- **THEN** the round still finds the orphan by the branch name of the mark

#### Scenario: A young mark
- **WHEN** the mark is younger than 1 hour
- **THEN** the job makes no request and keeps the mark, and a round that runs when the mark is 1 hour old judges it

#### Scenario: The branch is gone
- **WHEN** the branch of the mark is not on `origin`
- **THEN** the job clears the record and makes no request

### Requirement: The job removes an orphan only when it wrote the branch alone
When every commit of the pushed branch of an orphan past the default branch is by the identity of the clone or is a clean merge, the job SHALL close the open pull request whose head is the branch, delete the branch and clear the record. The job SHALL read the open pull requests once in a round, and only when such a branch exists. When any other commit exists, the job SHALL keep the branch and the draft and say so in the plan.

#### Scenario: A person added a commit
- **WHEN** the pushed branch of the mark holds a commit by another author
- **THEN** the job keeps the branch and the draft, makes no request and the plan says why

#### Scenario: The request cost of a removal
- **WHEN** a round removes two orphans
- **THEN** the round reads the open pull requests once

### Requirement: A branch with no intent mark is never touched
The job SHALL NOT close, delete or change a pushed branch or a pull request whose item holds no `stage.pending`.

#### Scenario: A branch with no mark
- **WHEN** a person or an agent pushed a branch for another item that holds no `stage.pending`
- **THEN** the job does not touch the branch or its pull request

### Requirement: A failed stage item records its failure class and step
When the stage job records a failure in the job record of an item, it SHALL write `stage.failed_class`, the failure class of the exception, and `stage.failed_step`, the step, in the same write as `stage.failed_at` and `stage.failed_error`. The step SHALL be `plan` for a failure of the plan and `apply` for a failure of a write. A staged item and an item stopped on the budget SHALL clear both keys with `stage.failed_at` and `stage.failed_error`.

#### Scenario: A provider error in the plan
- **WHEN** the model call of an item fails with a provider error
- **THEN** the job record holds the class `provider` and the step `plan`

#### Scenario: A refused plan
- **WHEN** the plan of an item breaks a rule of the stage job
- **THEN** the job record holds the class `plan_defect` and the step `plan`

#### Scenario: A failed write
- **WHEN** a write of an item fails
- **THEN** the job record holds the step `apply`

#### Scenario: An item that changed during the job
- **WHEN** a write fails with the error that the item changed
- **THEN** the job record holds the class `head_moved`

#### Scenario: A staged item
- **WHEN** a round stages an item whose record holds a failure
- **THEN** the record holds no `stage.failed_at`, `stage.failed_error`, `stage.failed_class` or `stage.failed_step`

#### Scenario: The request count
- **WHEN** a round records a failure
- **THEN** the round writes the four keys with the one write that it made before

### Requirement: The plan check refuses a path of its own change folder
`check_proposal` SHALL refuse a path under `openspec/changes/<change>/` in a group `changes` or in a code span of a task when `change` is the plan's own change folder.

#### Scenario: A group lists the plan proposal
- **WHEN** A behavior group lists `openspec/changes/3321-plan-check/proposal.md` in `changes`, and `check_proposal` receives `change='3321-plan-check'`.
- **THEN** `check_proposal` returns one problem that names the path and the own change folder.

#### Scenario: A task names the plan tasks file
- **WHEN** A behavior group's `implementation` names `openspec/changes/3321-plan-check/tasks.md` in a code span, and `check_proposal` receives `change='3321-plan-check'`.
- **THEN** `check_proposal` returns one problem that names the group and the path.

#### Scenario: A group names another change folder
- **WHEN** A behavior group changes `openspec/changes/3307-other/proposal.md`, and `check_proposal` receives `change='3321-plan-check'`.
- **THEN** `check_proposal` returns no own-change problem.

### Requirement: A scenario that names code has a behavior test
`check_proposal` SHALL refuse a spec scenario that names a function or a file when no behavior group's `test` or `verify` names it and the scenario names no command. It SHALL judge the code spans of the `then`, and the code spans of the `when` that are no path or whose path a behavior group changes, creates or reads. It SHALL NOT judge a path of the `when` that no behavior group touches, because that path is input data.

#### Scenario: A scenario names `_loki_mode` and no task tests it
- **WHEN** A spec scenario's `then` names `_loki_mode` in a code span, and no behavior group's `test` or `verify` names `_loki_mode`.
- **THEN** `check_proposal` returns one problem that names the scenario and `_loki_mode`.

#### Scenario: A scenario that cites `helm template`
- **WHEN** A spec scenario's `then` names `_loki_mode` and `helm template` in code spans, and no behavior group's `test` names `_loki_mode`.
- **THEN** `check_proposal` returns no scenario problem.

#### Scenario: A behavior test names the function
- **WHEN** A spec scenario's `then` names `_loki_mode` in a code span, and a behavior group's `test` names `_loki_mode`.
- **THEN** `check_proposal` returns no scenario problem.

#### Scenario: A data file in the condition
- **WHEN** A spec scenario's `when` says `.github/labels.yml` declares no `scope/floor`, and no behavior group changes, creates or reads `.github/labels.yml`, and no test names it.
- **THEN** `check_proposal` returns no scenario problem.

#### Scenario: A file that a behavior group reads
- **WHEN** A spec scenario's `when` names `.github/labels.yml`, a behavior group reads it, and no behavior group's `test` or `verify` names it.
- **THEN** `check_proposal` returns one problem that names the scenario and `.github/labels.yml`.

#### Scenario: A file in the result
- **WHEN** A spec scenario's `then` names `.github/labels.yml` and no behavior group's `test` or `verify` names it.
- **THEN** `check_proposal` returns one problem that names the scenario and `.github/labels.yml`.

### Requirement: A quoted reference search names only covered files
`check_proposal` SHALL refuse each file that a quoted `References to` answer lists outside `openspec/changes/archive/` and that no group `changes` or `creates` path and no design decision names.

#### Scenario: A quoted search lists an untouched test file
- **WHEN** `feasibility` holds `References to 'SingleBinary': files 1, lines 1.` and `tests/commands/k8s/test_k8s.py: 1 (line 12)`, and no group or design decision names `tests/commands/k8s/test_k8s.py`.
- **THEN** `check_proposal` returns one problem that names `tests/commands/k8s/test_k8s.py`.

#### Scenario: A design decision names the test file
- **WHEN** The same `feasibility` lines are given, and a decision names `tests/commands/k8s/test_k8s.py` as left unchanged.
- **THEN** `check_proposal` returns no reference problem.

#### Scenario: An archived plan is skipped
- **WHEN** `feasibility` lists `openspec/changes/archive/2026-10-24-1000-old/proposal.md` in a quoted `References to` answer.
- **THEN** `check_proposal` returns no reference problem.

### Requirement: A plan that names a defect type member passes
`check_proposal` MUST NOT return a problem for a plan that names a `DefectType` member, including a member that the plan adds.

#### Scenario: A plan adds a member and names it
- **WHEN** `check_proposal` runs on a valid plan whose group changes `src/devops_cli/roadmap/stage_eval_cases.py` and whose test text names `DefectType.PROMPT_KEY_MISSING`
- **THEN** `check_proposal` returns an empty list

### Requirement: A plan that adds a StageProposal field names the reply key of the prompt
The stage job SHALL refuse a plan that adds a field to `StageProposal` and does not change `src/devops_cli/ai/tasks/roadmap_stage_change.md` with the reply key of that field.

#### Scenario: Missing reply key
- **WHEN** A plan has a group that changes `src/devops_cli/roadmap/stage/stage_change.py` and names a new field of `StageProposal`, and no group changes `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** The job returns a problem that names `src/devops_cli/ai/tasks/roadmap_stage_change.md` and the missing reply key, and the reply returns to the model once.

#### Scenario: Reply key and rule present
- **WHEN** A plan has a group that adds a field to `StageProposal` and another group that changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` with the new reply key bullet and its rule.
- **THEN** The job returns no problem for the prompt keys.

#### Scenario: A change to the file that adds no field
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_change.py` in a group whose text names no new field of `StageProposal`.
- **THEN** The job returns no problem for the prompt keys.

### Requirement: The job probes each reference of a moved module
The stage job SHALL take the old path and the dotted name of each Python module that a group moves from the old path in `changes` and the new path in `creates`, and SHALL run `git grep` on the staging commit for both names with no cap on the files. It SHALL give the path of each hit to `check_proposal`. It SHALL read no test module and no `conftest.py` as a moved module.

#### Scenario: A string literal names the old module
- **WHEN** the staging commit holds `devops_cli.roadmap.store` in a string literal of `tests/roadmap/test_store.py`, and a group moves `src/devops_cli/roadmap/store.py` to `src/devops_cli/roadmap/db/store.py`.
- **THEN** the probe gives `tests/roadmap/test_store.py` to `check_proposal`.

#### Scenario: A move names more hits than the tool keeps
- **WHEN** the old dotted name of a moved module is in 70 files, and the `references` tool keeps at most 60.
- **THEN** `reference_files` returns the path of all 70 files.

#### Scenario: A snapshot path names the old module
- **WHEN** a group moves a test module, and a snapshot file is keyed by the old test path.
- **THEN** the probe gives the path of the snapshot file to `check_proposal`.

#### Scenario: A test module is no moved module
- **WHEN** a group moves `tests/roadmap/test_store.py`.
- **THEN** the probe gives no path to `check_proposal`.

### Requirement: A reference is covered by a group or left unchanged
`check_proposal` SHALL refuse a probed path that no group lists in `changes` and that the reply does not mark unchanged with a reason.

#### Scenario: A reference is missing from the plan
- **WHEN** a probed path is `tests/roadmap/test_x.py`, no group lists that path in `changes`, and the reference is not unchanged.
- **THEN** `check_proposal` returns a problem that names `tests/roadmap/test_x.py`.

#### Scenario: A group changes the reference file
- **WHEN** a probed path is `tests/roadmap/test_x.py` and one group lists that path in `changes`.
- **THEN** `check_proposal` returns no reference problem for that path.

#### Scenario: An unchanged reference has no reason
- **WHEN** a reply marks a reference unchanged and gives no reason.
- **THEN** The schema refuses the reply with a problem that names the path.

#### Scenario: The reply lists a hit that the job does not probe
- **WHEN** a reply lists a reference that is in none of the probed paths.
- **THEN** `check_proposal` returns no problem for that reference.

### Requirement: The design records each unchanged reference
`_design_file` SHALL write the path, the kind and the reason of each unchanged reference into the rendered `design.md`.

#### Scenario: A snapshot stays keyed by the old module
- **WHEN** A reply marks `tests/snapshots/roadmap/test_x.ambr` unchanged with the kind `snapshot file` and a reason.
- **THEN** The rendered `design.md` holds that path, that kind and that reason.

### Requirement: The prompt names the references that an import rewrite misses
The stage prompt SHALL name a quoted target, a logger name and a snapshot file as references that an import rewrite does not update, and SHALL ask a move plan for a `! git grep` check on the old dotted name over `src/` and `tests/`. For a move by name prefix, the check SHALL name the old dotted prefix and no single module.

#### Scenario: The prompt lists the reference kinds
- **WHEN** The stage prompt is read.
- **THEN** It holds the words `quoted target`, `logger name` and `snapshot file`.

#### Scenario: The prompt states the verification of a direct move
- **WHEN** The stage prompt is read.
- **THEN** It holds the `! git grep` form, the old dotted name and both `src/` and `tests/`.

#### Scenario: The prompt states the verification of a prefix move
- **WHEN** The stage prompt is read.
- **THEN** It holds the old dotted prefix with no single module, and it says that a literal of one module is refused.

#### Scenario: The prompt names both searches
- **WHEN** The stage prompt is read.
- **THEN** It holds the `references` tool, the old module path and the dotted name.

#### Scenario: The prompt tells a planner to narrow a search that leaves files out
- **WHEN** The stage prompt is read.
- **THEN** It tells the planner to search a narrower name when the `references` answer leaves files out.

### Requirement: A read of a model attribute that the model lacks is refused
The stage proposal check SHALL refuse a plan that names an attribute that the Pydantic model of the staged commit does not define, and SHALL name the reference and the module of the model in the problem.

#### Scenario: PullStatus lacks labels
- **WHEN** A plan names `PullStatus.labels`, and the recorded `PullStatus` of `src/devops_cli/github/client.py` defines no `labels` field.
- **THEN** `check_proposal` returns a problem that names `PullStatus.labels` and `src/devops_cli/github/client.py`.

#### Scenario: A model field that exists passes
- **WHEN** A plan names `PullStatus.state`, and the recorded `PullStatus` of `src/devops_cli/github/client.py` defines `state`.
- **THEN** `check_proposal` returns no problem for that reference.

#### Scenario: A name that is no model class is left alone
- **WHEN** A plan names `stage_ready.item`, and no Pydantic model class of the staged commit is named `stage_ready`.
- **THEN** `check_proposal` returns no problem for that reference.

#### Scenario: A caller gives no model map
- **WHEN** `check_proposal` runs with no `models` argument on a plan that names `PullStatus.labels`.
- **THEN** `check_proposal` returns no problem for that reference.

### Requirement: The module of a model that a plan extends is in changes
The stage proposal check SHALL return a problem that names the module of a model when a plan reads an attribute that the model lacks and no group lists that module in `changes`, and SHALL return no such problem when a group lists it.

#### Scenario: The plan omits the model module
- **WHEN** A plan reads `PullStatus.labels` and no group lists `src/devops_cli/github/client.py` in `changes`.
- **THEN** `check_proposal` returns a problem that tells the model to add `src/devops_cli/github/client.py` to a group's `changes`.

#### Scenario: The plan lists the model module
- **WHEN** A plan reads `PullStatus.labels` and a group lists `src/devops_cli/github/client.py` in `changes`.
- **THEN** `check_proposal` returns no problem for the model attribute.

#### Scenario: A second reply with the same gap stops the item
- **WHEN** The first and the second reply both read `PullStatus.labels` and both omit `src/devops_cli/github/client.py` from `changes`.
- **THEN** The stage job records a failure of the item with `RoadmapStageError`, and the plan holds no ready change.

### Requirement: A plan that passes the gates is kept as a file
The planner SHALL write the plan that passes the gates, with its `StageRequest`, to the file `roadmap/stage/<owner>/<repo>/<number>.json` under the data directory, atomically, before the model review. The file SHALL hold a key: the sha256 of the item number, the hash of its title, the hashes of its body from `body_hashes`, the model name of the task `stage`, the name of the toolset and the prompt version. The prompt version SHALL be the sha256 of the texts of the prompts that the planner reads.

#### Scenario: The key follows the input
- **WHEN** the title or the body of an item, the model name, the toolset or the text of a prompt changes
- **THEN** the key is a new value
- **WHEN** only the staged commit moves
- **THEN** the key is the same value

### Requirement: A kept plan with the same key sends the planner no request
When the file of an item holds the key of the current input, the planner SHALL send the model of the task `stage` no request for the plan. It SHALL run the gates again on the current staged commit from the kept plan and the kept request, and it SHALL run the model review again.

#### Scenario: A failed review and a rerun
- **WHEN** the model review of an item fails and the stage job plans the item again with the same input
- **THEN** the second run sends the planner no request and plans the item from the file

#### Scenario: A plan, then a confirm
- **WHEN** `devops roadmap stage --plan` and then `--confirm` plan the same item with a stub model
- **THEN** the planner gets one request in total, and the run of `--plan` made no GitHub write

#### Scenario: The commit moves
- **WHEN** the staged commit moves between two runs and the input is the same
- **THEN** the second run sends the planner no request and measures the groups on the new commit

### Requirement: An unreadable plan file stops the item with its name
A plan file that is no JSON object with a key, or that holds the current key and does not match its model, SHALL raise an error that names the file. The job SHALL NOT plan the item from a new model request in its place. A file with another key is no error: it is a miss.

#### Scenario: A corrupt file
- **WHEN** the plan file of an item holds text that is no JSON
- **THEN** the item fails with an error that names the file, and the planner gets no request

#### Scenario: A file of another key
- **WHEN** the plan file of an item holds another key and text that does not match the model
- **THEN** the job deletes the file and plans the item with a new request

### Requirement: A staged item or a changed key deletes the plan file
The stage job SHALL delete the plan file of an item when it stages the item, and when the key of the input differs from the key in the file. A write that fails SHALL leave the file.

#### Scenario: A staged item
- **WHEN** the job stages an item
- **THEN** the plan file of the item does not exist

#### Scenario: A changed input
- **WHEN** the body of an item changes and the job plans the item again
- **THEN** the old file is deleted before the planner is asked, and a new file with a new key replaces it after the plan passes

### Requirement: Each use of the plan file counts by its result
The planner SHALL add 1 to `devops_cli_roadmap_stage_plan_record_total` with the label `result`: `hit` for a plan taken from the file, `miss` for a plan that the file did not hold, and `written` for a file that the planner wrote. The counter SHALL have 3 series.

#### Scenario: A miss, a write and a hit
- **WHEN** the job plans an item twice with the same input
- **THEN** the counter has 1 point for `miss`, 1 for `written` and 1 for `hit`

### Requirement: A manifest plan names the tests that reference it
The stage job SHALL refuse a plan that changes a YAML manifest under `k8s/` and lists no test file that references that manifest, because the implement job cannot edit a test outside the `Changes:` list of the plan.

#### Scenario: The plan of the logging egress rule omits the logging test
- **WHEN** the plan changes `k8s/logging/networkpolicy.yaml`, the job records `tests/commands/k8s/test_k8s_logging_stack.py` as a reference to it, and the plan lists no such test
- **THEN** the problem names `k8s/logging/networkpolicy.yaml` and `tests/commands/k8s/test_k8s_logging_stack.py`, and it asks for the test in `Changes:`

#### Scenario: The plan of the logging egress rule names the logging test
- **WHEN** the plan changes `k8s/logging/networkpolicy.yaml` and lists `tests/commands/k8s/test_k8s_logging_stack.py`
- **THEN** the path gate reports no problem that names either path

#### Scenario: The test builds the manifest path from its parts
- **WHEN** a test file holds the literals `logging` and `networkpolicy.yaml` in separate strings
- **THEN** the record names that test as a reference to `k8s/logging/networkpolicy.yaml`

#### Scenario: The test holds only the folder name
- **WHEN** a test file holds `logging` but not `networkpolicy.yaml`
- **THEN** the record names no reference to `k8s/logging/networkpolicy.yaml` for that file

#### Scenario: The job records no reference
- **WHEN** the gate gets no record, as a replay of a case with none does
- **THEN** the check reports no missing reference

### Requirement: A test-only other group names its test function
The stage plan SHALL refuse an other task group that changes only test modules and whose implementation names no test function in a code span. It SHALL accept an other group with one changed path that is no test module. A test module is a path under `tests/` whose base name starts with `test_` and ends with `.py`. A code span names a test function when its text after the last `::`, or the whole span, starts with `test_`, with optional parentheses.

#### Scenario: Conditional test-only group
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/roadmap/stage/test_roadmap_stage_content.py` and whose `implementation` holds no code span with a `test_` function
- **THEN** the returned problems hold the refusal sentence for that group

#### Scenario: Named test function
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/roadmap/stage/test_roadmap_stage_content.py` and whose `implementation` holds a code span with `test_conditional_group`
- **THEN** the returned problems hold no refusal sentence for that group

#### Scenario: Named test function after a path
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/roadmap/stage/test_roadmap_stage_content.py` and whose `implementation` holds a code span with `tests/roadmap/stage/test_roadmap_stage_content.py::test_conditional_group`
- **THEN** the returned problems hold no refusal sentence for that group

#### Scenario: Group with a source path
- **WHEN** `content_problems` reads an other group whose `changes` lists `tests/roadmap/stage/test_roadmap_stage_content.py` and `src/devops_cli/roadmap/stage/stage_change.py` and whose `implementation` names no test function
- **THEN** the returned problems hold no refusal sentence for that group

#### Scenario: Refusal names the group
- **WHEN** `content_problems` refuses an other group with the title `Keep the roadmap stage tests green`
- **THEN** the returned sentence holds `Keep the roadmap stage tests green`

#### Scenario: Test helper group
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/support/builders.py` and whose `implementation` names no test function
- **THEN** the returned problems hold no refusal sentence for that group

#### Scenario: Test file path with no function
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/roadmap/stage/test_roadmap_stage_content.py` and whose `implementation` holds the code span `tests/roadmap/stage/test_roadmap_stage_content.py` and no other code span
- **THEN** the returned problems hold the refusal sentence for that group

### Requirement: The planner prompt asks for one exact change and its test
The stage prompt SHALL state that a task group gives one exact change and names the failing test that it updates in a code span.

#### Scenario: The stage prompt loads
- **WHEN** the stage job loads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the prompt text states that a group gives one exact change and names the failing test in a code span

### Requirement: Feasibility cites only what the plan run did
The stage job SHALL refuse a feasibility line that names a toolbox tool, or states that a code-span path was read, when the plan runs of the item hold no call that supports it, and SHALL accept a line that negates the claim.

#### Scenario: A read claim with no tool call
- **WHEN** The trace holds zero calls and the feasibility section says `read `src/x.py``.
- **THEN** `check_proposal` returns a problem that names `src/x.py` and the absent read.

#### Scenario: A read claim that the trace supports
- **WHEN** The trace holds a `read_file` call for `src/x.py` and the feasibility section says `read `src/x.py``.
- **THEN** `check_proposal` returns no problem for that line.

#### Scenario: A tool name that the trace lacks
- **WHEN** The trace holds no `search_code` call and the feasibility section says `search_code` returned a result.
- **THEN** `check_proposal` returns a problem that names `search_code`.

#### Scenario: A stated gap
- **WHEN** The trace holds zero calls and the feasibility section says `not read `src/x.py``.
- **THEN** `check_proposal` returns no problem for that line.

#### Scenario: A caller with no run
- **WHEN** `check_proposal` gets no trace facts and the feasibility section says `read `src/x.py``.
- **THEN** `check_proposal` returns no trace problem, and its other checks run as before.

#### Scenario: A claim of the first run after a return
- **WHEN** The first plan run called `read_file` for `src/x.py`, its reply was returned for another problem, the second plan run called no tool, and the second reply says `read `src/x.py``.
- **THEN** The second reply passes the trace gate.

### Requirement: Trace facts of a run
`TraceFacts.of` SHALL hold the tool name of each call of a `RunTrace` and the `path`, `directory` and `paths` values of an argument that parses as JSON, and the stage job SHALL pass to `check_proposal` the facts of the combined trace of every plan run of the item so far. A review run SHALL NOT be a plan run.

#### Scenario: A trace with two calls
- **WHEN** The trace holds a `read_file` call for `src/x.py` and a `search_code` call for `needle`.
- **THEN** The facts hold the tools `read_file` and `search_code`, and the path `src/x.py`.

#### Scenario: The stage job calls the check
- **WHEN** The planner gets a reply from a toolbox run that called `read_file` for `src/x.py`.
- **THEN** The `check_proposal` call for that reply holds the facts with the tool `read_file` and the path `src/x.py`.

#### Scenario: The facts hold every plan run
- **WHEN** The first plan run called `read_file` for `src/x.py` and the second plan run called no tool.
- **THEN** The facts hold the tool `read_file` and the path `src/x.py`.

#### Scenario: A review run supports no claim
- **WHEN** A review run called `read_file` for `src/x.py` and no plan run called it.
- **THEN** The facts hold no tool and no path.

### Requirement: The planner prompt cites only the run
The planner prompt and `docs/roadmap/stage.md` SHALL state that a plan cites only the tools and the paths that its run used, and that a premise that the run did not check is written as `not checked`.

#### Scenario: The prompt rule is present
- **WHEN** The stage prompt and `docs/roadmap/stage.md` are read.
- **THEN** Both hold the same sentence of the rule, and the tests in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` pass.

### Requirement: Research toolset adds search_web
The stage toolbox SHALL add `search_web` when the toolset is `research`.

#### Scenario: Research adds one tool
- **WHEN** the stage toolset is `research`
- **THEN** the toolbox holds every `extended` tool and `search_web`, and no other tool.

### Requirement: Base and extended omit search_web
The stage toolbox SHALL NOT include `search_web` when the toolset is `base` or `extended`.

#### Scenario: Network-free toolsets stay network-free
- **WHEN** the stage toolset is `base` or `extended`
- **THEN** the toolbox holds no `search_web` tool.

### Requirement: Search query is guarded before the call
The search tool SHALL build the query from the short term that the model gives and SHALL apply the secret masker and private-data rules before it calls the search service.

#### Scenario: Secret and internal host are stopped
- **WHEN** the short term holds a secret or an internal host
- **THEN** the tool masks the secret and refuses the internal host before it calls the search service.

### Requirement: Search result is data
The search tool SHALL return only titles, URLs and cut snippets, and the prompt SHALL state that a result is data and not an instruction.

#### Scenario: Result text is cut and marked as data
- **WHEN** the search service returns a long snippet and an instruction in its title
- **THEN** the tool returns the title, URL and a cut snippet, and the prompt marks the result as data.

### Requirement: Search limit and outcome counter
A plan run SHALL stop calling `search_web` at the stage search limit and SHALL count each search by its outcome.

#### Scenario: Excess search is refused and counted
- **WHEN** the model asks for more searches than the limit, with one success and one refusal
- **THEN** the tool refuses the excess call and the run records the counts by outcome.

### Requirement: removal-reference scan
The stage job SHALL scan `tests/` and `src/` for each name that the change folder declares as removed, before the draft pull request opens.

#### Scenario: a test file references a removed name
- **WHEN** a temporary repository holds a change folder that names `valkey_set` as removed and `tests/example_test.py` references it
- **THEN** the scan reports `tests/example_test.py` as an unhandled reference to `valkey_set`.

### Requirement: removed names come from a removal verb
The scan SHALL take each backticked identifier that a removal verb governs in `proposal.md` or `design.md` as a removed name.

#### Scenario: a removal sentence names two identifiers
- **WHEN** a fixture `proposal.md` holds the sentence `removes `valkey_set` from `CONST_MCP_EXPOSURE_TABLE``
- **THEN** the scan searches for `valkey_set` and does not search for `CONST_MCP_EXPOSURE_TABLE`.

### Requirement: a task that names the file accounts for the reference
The scan SHALL treat a reference as accounted for only when the change's `tasks.md` names the file that holds it.

#### Scenario: tasks.md names the test file
- **WHEN** a fixture `tasks.md` names `tests/example_test.py` and that file references the removed name
- **THEN** the scan reports no unhandled reference for `tests/example_test.py`.

### Requirement: stage fails on an unhandled test reference
`devops roadmap stage` MUST exit non-zero with each unhandled test reference and MUST open no draft pull request.

#### Scenario: an unhandled test reference stops the stage
- **WHEN** the scan finds an unhandled reference in `tests/`
- **THEN** the command exits non-zero, the message names the file and the removed name, and the stage opens no draft pull request.

### Requirement: a source reference is a warning
The scan SHALL report an unhandled reference in `src/` as a warning and SHALL NOT fail the stage for it.

#### Scenario: only a source file references the removed name
- **WHEN** a fixture `src/example.py` references the removed name and `tasks.md` does not name it
- **THEN** the stage succeeds and its comment names `src/example.py` as a warning.

### Requirement: a change with no removal passes
A change folder that names no removed entity SHALL pass the scan with no finding.

#### Scenario: a plan removes nothing
- **WHEN** no sentence in `proposal.md` or `design.md` has a removal verb and a backticked identifier
- **THEN** the scan reports no finding and the stage proceeds.

### Requirement: Resolve cited command spans
The plan check SHALL resolve every `devops` command span in the Feasibility text and the task text against the real command tree.

#### Scenario: Unknown subcommand is refused
- **WHEN** A plan cites `uv run devops ai ast-graph --help`.
- **THEN** The check returns a problem that names `ai ast-graph` and refuses the plan.

### Requirement: Accept a resolved command span
The plan check SHALL accept a `devops` command span that resolves to a leaf command with valid options.

#### Scenario: Known subcommand is accepted
- **WHEN** A plan cites `uv run devops ai ast graph --help`.
- **THEN** The check returns no command-resolution problem for that span.

### Requirement: Resolve cited option flags
The plan check SHALL resolve each option flag in a cited `devops` command span against that command.

#### Scenario: Unknown option is refused
- **WHEN** A plan cites `uv run devops gh pages verify --root_dir .`.
- **THEN** The check returns a problem that names `--root_dir` and refuses the plan.

#### Scenario: Known option is accepted
- **WHEN** A plan cites `uv run devops gh pages verify --dir .`.
- **THEN** The check returns no command-resolution problem for that span.

### Requirement: Resolve cited MCP exposure keys
The plan check SHALL resolve each quoted tuple key that a plan cites against `CONST_MCP_EXPOSURE_TABLE`. It SHALL read a quoted tuple as a cited key only when the sentence that holds the tuple names `CONST_MCP_EXPOSURE_TABLE` or the words "exposure table".

#### Scenario: Unknown MCP exposure key is refused
- **WHEN** A plan cites the exposure table key `("ai", "ast-graph")`.
- **THEN** The check returns a problem that names `("ai", "ast-graph")` and refuses the plan.

#### Scenario: Known MCP exposure key is accepted
- **WHEN** A plan cites the exposure table key `("ai", "ast", "graph")`.
- **THEN** The check returns no MCP exposure problem for that key.

#### Scenario: A quoted tuple of another table is no key
- **WHEN** A plan says that the fixture table of `tests/conftest.py` lists `("reset_logfire_bridge",)`.
- **THEN** The check returns no MCP exposure problem.

#### Scenario: The sentence of the tuple decides
- **WHEN** A plan names the exposure table in one sentence and quotes the tuple `("ai", "ast-graph")` in the next sentence.
- **THEN** The check returns no MCP exposure problem.

### Requirement: Failure taxonomy in staging context
Staging context SHALL include the failure class table and action rules from `failure.py` when the plan cites retry, review, stop, tier or failure.

#### Scenario: Retry plan gets class table
- **WHEN** A staging run gets a plan that cites `retry`.
- **THEN** The planner context contains the class table and `ACTION_BY_CLASS` rules read from `failure.py` at the staged commit.

### Requirement: Runner capability facts in staging context
Staging context SHALL include the runner image tools, `NOT_IN_RUNNER` entries and pod security settings when the plan cites a command or tool name.

#### Scenario: Review command gets runner facts
- **WHEN** A staging run gets a plan that adds `devops review` to the Job.
- **THEN** The planner context contains the image tool list, the `NOT_IN_RUNNER` entry for each review tool and the pod security settings.

### Requirement: Repository-derived facts
The context builder MUST read the failure classes, runner tools and pod security settings from repository files at the staged commit. It MUST NOT copy them into a static prompt.

#### Scenario: Source move fails the test
- **WHEN** A test moves or renames `failure.py`, `runner_tools.py` or the pod security manifest.
- **THEN** The context builder test fails and names the moved source.

### Requirement: Planner Feasibility instruction
The planner prompt SHALL tell the planner to state each needed failure class and runner capability in `## Feasibility`.

#### Scenario: Prompt names Feasibility
- **WHEN** The staging prompt includes failure or runner capability facts.
- **THEN** The prompt contains the instruction to state those facts in `## Feasibility`.

### Requirement: Gate refuses unsupported Job command
The staging gate SHALL refuse a plan that adds a command to the Job when its `## Feasibility` section names no runner capability for that command.

#### Scenario: Unsupported Job command is refused
- **WHEN** A plan adds `devops review` to the Job and its Feasibility section names no review tool from `NOT_IN_RUNNER`.
- **THEN** The gate returns a refusal that names `devops review` and the missing runner capability.

### Requirement: Gate refuses unsupported verify program
The staging gate SHALL refuse a plan whose task verify runs a `NOT_IN_RUNNER` program without a `## Feasibility` line that names its runner capability.

#### Scenario: Helm verify is refused
- **WHEN** A plan has a task verify that runs `helm template` and its Feasibility section names no runner capability for `helm`.
- **THEN** The gate returns a refusal that names `helm` and the missing runner capability.

### Requirement: Docker verify is refused
The staging gate SHALL refuse a medium-effort plan whose task verify runs `docker` without a `## Feasibility` line that names its runner capability.

#### Scenario: Medium-effort Docker verify is refused
- **WHEN** A medium-effort plan has a task verify that runs `docker build` and its Feasibility section names no runner capability for `docker`.
- **THEN** The gate returns a refusal that names `docker` and the missing runner capability.

### Requirement: Replay case in golden set
The golden set MUST include one replay case from #3183 or #3225 that exercises the failure taxonomy and runner capability context.

#### Scenario: Replay case runs offline
- **WHEN** The golden-set test runs the #3183 or #3225 replay case.
- **THEN** The case passes with the expected context facts and the expected gate result.

### Requirement: Gate plan quotes the refused defect
A plan that changes a gate file SHALL quote the defective text that the gate must refuse in its Feasibility.

#### Scenario: A gate plan without the defect quote
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_eval_gates.py`, and its Feasibility holds no code span.
- **THEN** `content_problems` returns the message that the Feasibility must quote the defective text.

### Requirement: Gate plan tests the defect on the base
A plan that changes a gate file SHALL give a test task that holds the quoted text and the phrase `fails on the base`.

#### Scenario: A gate plan with the quote and the failing test
- **WHEN** A plan changes a gate file, its Feasibility quotes the defective text, and its test task holds that text and the phrase `fails on the base`.
- **THEN** `content_problems` returns no gate defect problem.

### Requirement: Gate plan without the failing test is refused
A plan that changes a gate file and gives a test task with no `fails on the base` phrase SHALL be refused.

#### Scenario: A gate plan with the quote and no failing test
- **WHEN** A plan changes a gate file and quotes the defective text, and its test task omits `fails on the base`.
- **THEN** `content_problems` returns the message that the test task must fail on the base.

### Requirement: Gate plan states a skipped case as a non-goal
A plan whose gate test says that the rule skips a case SHALL state that non-goal in its design decisions, its rejected alternatives or its spec delta.

#### Scenario: A gate plan that skips a case without a non-goal
- **WHEN** A plan changes a gate file, its test text holds `skip`, and no decision, rejected alternative or spec delta text holds `non-goal`.
- **THEN** `content_problems` returns the message that the plan must state the skipped case as a non-goal.

### Requirement: Gate plan accepts a stated non-goal
A plan that states the non-goal for a skipped gate case MUST pass the non-goal rule.

#### Scenario: A gate plan with the non-goal
- **WHEN** A plan changes a gate file, its test text holds `skip`, and a decision text holds `non-goal`.
- **THEN** `content_problems` returns no non-goal problem.

### Requirement: The gate quote rule runs in the shared check
The gate quote rule MUST run from `content_problems`, which `check_proposal` and the replay call.

#### Scenario: The stage job and the replay report the same message
- **WHEN** A plan changes a gate file and quotes no defective text.
- **THEN** `check_proposal` and `_content_gate` both return the same `RoadmapMessages` text.

### Requirement: The gate quote rule has offline tests
`tests/roadmap/stage/test_roadmap_stage_plan.py` SHALL hold one test that refuses a gate plan with no defect quote and one test that accepts a gate plan with the quote and the failing test task.

#### Scenario: The gate quote tests run
- **WHEN** The test module runs.
- **THEN** The refusing test and the accepting test both pass.

### Requirement: A plan with no gate change is not refused
A plan that changes no gate file MUST pass the gate defect quote rule.

#### Scenario: A plan with no gate change
- **WHEN** A plan changes only `src/devops_cli/sample.py`.
- **THEN** `content_problems` returns no gate quote problem.

### Requirement: A cited class field is probed at the staging commit
The premise probe SHALL read a cited `Class.field` reference as a class field when the staging
commit defines the class, and SHALL name the file and line of the field when the class defines it.

#### Scenario: A class that defines the cited field
- **WHEN** The issue body cites `PullStatus.labels` and `PullStatus` at the staging commit defines `labels`
- **THEN** The probe text says that `PullStatus` defines `labels` at its file and line, and the reference is not in the probe's missing list

#### Scenario: A class without the cited field
- **WHEN** The issue body cites `PullStatus.unknown_field` and `PullStatus` at the staging commit defines no `unknown_field`
- **THEN** The probe text says that `PullStatus` defines no `unknown_field`, and the reference is in the probe's missing list

#### Scenario: The cited dotted reference names a class
- **WHEN** The issue body cites `PullStatus.labels` and the staging commit defines the class `PullStatus`
- **THEN** The probe text holds no line that says the path `PullStatus.labels` is no file of the staging commit

### Requirement: A false absence returns the item
The stage job SHALL return an item to New with the probe evidence when the issue body states that a
cited class field is absent and the staging commit defines it, and SHALL make no model call for the
item.

#### Scenario: The body says a field is absent while the class defines it
- **WHEN** The body says that `PullStatus` defines no `labels` and `PullStatus` at the staging commit defines `labels`
- **THEN** The stage job returns the item to New, and its comment quotes the probe line that names the file and line of `labels`

#### Scenario: The item waits on a body edit
- **WHEN** The body states that a cited class field is absent and the staging commit defines it
- **THEN** The stage job records `refine.next_step` as `edit` for the item

### Requirement: Bounded read-only field probe
The field probe MUST count each git command against `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS` and
MUST leave the checkout unchanged.

#### Scenario: A probe of cited fields
- **WHEN** The probe reads a cited class field at the staging commit
- **THEN** The probe reports its command count against `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS`, and `git status --porcelain` of the checkout stays empty

### Requirement: A plan summary is no placeholder
The stage plan SHALL refuse a `summary` whose whole text is a placeholder word through `is_placeholder` of `src/devops_cli/roadmap/pull_form.py`. The refusal SHALL use the existing `stage_problem_text_placeholder` message with the field `summary`.

#### Scenario: A summary of one placeholder word
- **WHEN** A reply gives a `summary` of `x`.
- **THEN** The schema refuses the reply, and the problem names `summary`, the placeholder rule and the text `x`.

#### Scenario: A placeholder summary message
- **WHEN** A reply gives a `summary` of `todo`.
- **THEN** The error text is the rendered `stage_problem_text_placeholder` message for the field `summary` and the text `todo`.

#### Scenario: A real summary is accepted
- **WHEN** A reply gives a `summary` of `Refuse a placeholder plan summary`.
- **THEN** The schema returns no problem for `summary`.

### Requirement: A reference reason may be null
The schema of a reference in the reply of the stage job SHALL accept `null` or a string as `reason`. A reference with `unchanged` true SHALL have a reason that is a non-blank string, and the schema SHALL refuse `null` there. The prompt of the stage job SHALL give `reason` the value that the schema accepts when `unchanged` is false.

#### Scenario: A changed reference with a null reason
- **WHEN** a reply holds a reference with `unchanged` false and `reason` null
- **THEN** the reply passes the schema

#### Scenario: An unchanged reference with a null reason
- **WHEN** a reply holds a reference with `unchanged` true and `reason` null
- **THEN** the schema refuses the reply and names the path of the reference

#### Scenario: A reply built from the prompt
- **WHEN** a reply holds a reference with `unchanged` false and the `reason` that the prompt states for that case
- **THEN** the reply passes the schema

### Requirement: A reply cut by the output token limit names the limit
A plan run or a review run of the stage job whose last model reply ends with the finish reason `length` SHALL fail with a `RoadmapStageError` that names the output token limit and `max_tokens`. The failure SHALL NOT be a schema failure, and the record of the failed item SHALL NOT show a count of schema violations for it.

#### Scenario: A plan reply cut by the limit
- **WHEN** the model of a plan run answers with the finish reason `length` and no part
- **THEN** the run raises a `RoadmapStageError` whose message names the output token limit and `max_tokens`
- **AND** the error is not a `StructuredOutputValidationError`

#### Scenario: A review reply cut by the limit
- **WHEN** the model of a review run answers with the finish reason `length` and no part
- **THEN** the run raises the same error

#### Scenario: A stop that the limit did not cause
- **WHEN** a run ends because the reply broke the schema, or because a budget limit was spent
- **THEN** the stop is not marked as a stop by the output token limit

### Requirement: A tool call with invalid arguments names the cause
A plan run or a review run of the stage job that ends because a tool call of its last model reply holds arguments that are not valid JSON SHALL fail with a `RoadmapStageError` that names the tool call with invalid arguments. The failure SHALL NOT be a schema failure, and the record of the failed item SHALL NOT show a count of schema violations for it.

#### Scenario: A plan call with joined arguments
- **WHEN** the last reply of a plan run holds a call to a tool with arguments of two JSON objects joined in one text
- **THEN** the run raises a `RoadmapStageError` whose message names a tool call with invalid arguments
- **AND** the error is not a `StructuredOutputValidationError`

#### Scenario: A review call with invalid arguments
- **WHEN** the last reply of a review run holds a call with arguments that are not valid JSON
- **THEN** the run raises the same error

#### Scenario: A stop that invalid arguments did not cause
- **WHEN** a run ends because the reply broke the schema with valid JSON, or because a budget limit was spent
- **THEN** the stop is not marked as a stop by invalid arguments

### Requirement: A refused reply is logged
The stage job SHALL log one line `stage reply refused` for each reply of the model that it refuses, with the number of the item, the number of the last request of the plan run, the input of that request in tokens, whether that request offered a function tool, the number of tool calls of the run, the limit that ended its tools, the stop reason and the model name of the last reply, and the result `refused` or `degenerate`. A fact that the run does not hold SHALL be written as `none`.

#### Scenario: A reply that the gates refuse
- **WHEN** the gates refuse the reply of item 1 in the second request of a plan run, and that request offered a tool
- **THEN** the log holds one line with `item=#1`, `request=2`, the input of the request in tokens, `tools_offered=True` and `result=refused`

#### Scenario: A degenerate reply that a provider stopped at its length
- **WHEN** the reply of item 1 is a placeholder in every text, after one tool call, and its stop reason is `length` and its model name is `fallback-model`
- **THEN** the log holds one line with `tool_calls=1`, `limit=none`, `finish_reason=length`, `answered=fallback-model` and `result=degenerate`

#### Scenario: A plan with no run
- **WHEN** the gates refuse a kept plan that no toolbox run made
- **THEN** the log holds one line with `tool_calls=0`, `limit=none`, `finish_reason=none` and `answered=none`

### Requirement: A failed item keeps its refused replies
When a plan fails, the stage job SHALL write the refused replies and their problems to the file `<n>.refused.json` beside the plan file of item `<n>`, under the key of the plan input. A new failed plan SHALL replace the file, and the staging of the item SHALL delete it. A reply over the byte bound SHALL be dropped with its size kept, and a problem SHALL be masked for secrets and cut to the character bound.

#### Scenario: The gates refuse a plan twice
- **WHEN** the gates refuse the first reply and the reply after the return of item 1
- **THEN** the file `1.refused.json` holds the key and both replies, each with its problem, and no plan file exists

#### Scenario: The item is staged
- **WHEN** a later round stages item 1
- **THEN** the file `1.refused.json` is deleted

### Requirement: A reply of placeholders ends the item
The stage job SHALL end an item at once, with no second request, when a reply is a placeholder in `why`, `existing_tool`, each line of `feasibility` and each task of each group. The item SHALL fail with the error `RoadmapStageDegenerateError`, the job SHALL keep the reply as a refused reply, and `devops_cli_roadmap_stage_total` SHALL count the item under the result `degenerate`. A reply with one text that is no placeholder SHALL go back to the model once.

#### Scenario: The first reply is all placeholders
- **WHEN** the first reply of item 1 holds `x` or `placeholder` in every text of the plan
- **THEN** the model gets one request, the item fails with `RoadmapStageDegenerateError`, and the result of the item is `degenerate`

#### Scenario: A reply with one real text
- **WHEN** the first reply holds `x` in `why` and in `feasibility` and a real text in `existing_tool`
- **THEN** the reply goes back to the model once, as for any refused reply, and the result stays `failed` if the second reply is refused

### Requirement: A schema failure names its violations
A plan run of the stage job whose model reply breaks the schema past its retries SHALL fail with an error whose failure line and log line name the count of violations, the stop reason (`validation` or `no tool call`) and at most 3 violations, each with its location, its pydantic error type and its message. Each text SHALL be masked for secrets and cut to 200 characters. The text SHALL NOT hold the input value of a violation.

#### Scenario: Two violations
- **WHEN** a plan reply breaks the schema with two violations, one at `references.0.reason`
- **THEN** the failure text holds `references.0.reason`, its error type, the stop reason and the count 2

#### Scenario: Five violations
- **WHEN** a plan reply breaks the schema with 5 violations
- **THEN** the failure text names 3 of them and the count 5

#### Scenario: A long message
- **WHEN** a violation message has 300 characters
- **THEN** the text holds the first 200 characters of it

#### Scenario: A secret in a message
- **WHEN** a violation message holds a token-shaped secret
- **THEN** the failure text, the log line and the kept file hold the masked value

### Requirement: A schema failure is kept in the refused file
When a plan fails because its reply broke the schema, the stage job SHALL write the stop reason, the count and the texts of the first violations in the field `schema_failure` of the file `<n>.refused.json`, with the replies that the checks refused before it. The staging of the item SHALL delete the file.

#### Scenario: A schema failure
- **WHEN** the plan of item 1 fails with two violations
- **THEN** the file `1.refused.json` holds the stop reason, the count 2 and both violations with their location, type and message

#### Scenario: The item stages later
- **WHEN** the item stages after a schema failure
- **THEN** the file `1.refused.json` is deleted

### Requirement: A kept plan holds the trace facts of its run
The plan file SHALL hold the facts of the plan runs that made the plan: the names of the tools that they called, and the paths that they read and that the Feasibility section of the plan cites. A kept plan SHALL be gated with these facts, joined with the facts of each later plan run of the item, so the trace gate neither skips a kept plan nor refuses a claim that the first run supported.

#### Scenario: A revision of a kept plan
- **WHEN** the plan file of an item holds a Feasibility sentence that names `read_issue` and facts with `read_issue`, another gate refuses the kept plan, and the planner revises it with a run that calls no tool
- **THEN** the trace gate accepts the revision

#### Scenario: A claim that the facts lack
- **WHEN** the plan file holds a Feasibility sentence that names `read_issue` and facts without it
- **THEN** the trace gate refuses the kept plan

#### Scenario: The facts are bounded
- **WHEN** the plan runs read many paths and the Feasibility section cites one of them
- **THEN** the plan file holds that path and no other

#### Scenario: A new planner model
- **WHEN** the model of the task `stage` changes
- **THEN** the key is a new value and the kept plan is a miss

### Requirement: A kept plan without facts is planned again
A plan file that holds the current key and no trace facts (the format of an older job) SHALL load, and the planner SHALL count it as a miss, delete it and ask the planner model for a new plan.

#### Scenario: A file in the old format
- **WHEN** the plan file of an item holds the current key, a plan and a request, and no facts
- **THEN** the planner sends the model a request, writes a new file with facts, and counts one `miss` and one `written`

### Requirement: A build cost states its time in minutes, hours, days or weeks
The stage job SHALL accept a time in `existing_tool` of a plan that sets `builds_own` to true when it is a number of minutes, hours, days or weeks, written with digits or with a number word from one to twelve, `a` or `an`. It SHALL still refuse a text that gives no count of tokens or no count of time.

#### Scenario: A time in days with a number word
- **WHEN** `builds_own` is true and `existing_tool` is `Cost: 80k tokens and about two days of elapsed time.`
- **THEN** `check_proposal` returns no cost problem.

#### Scenario: A time in weeks with digits
- **WHEN** `builds_own` is true and `existing_tool` is `Cost: 120k tokens, 1.5 weeks.`
- **THEN** `check_proposal` returns no cost problem.

#### Scenario: A time with no count
- **WHEN** `builds_own` is true and `existing_tool` is `Cost: 80k tokens and some days.`
- **THEN** `check_proposal` returns a problem that names the cost rule.

### Requirement: A move needs the module in another place
The stage job SHALL treat a Python module as moved only when a task group lists it in `changes` and creates, in `creates`, a module of the same name or a module under the sub-package that the name prefix of the module gives. A group that creates only a test, a document or a module of another name SHALL move no module, and the job SHALL probe no reference for it.

#### Scenario: A group edits a module and creates a test
- **WHEN** a group lists `src/devops_cli/roadmap/stage_probe.py` in `changes` and creates `tests/roadmap/test_stage_probe.py`.
- **THEN** the group moves no module.

#### Scenario: A group moves a module into a sub-package
- **WHEN** a group lists `src/devops_cli/roadmap/stage_probe.py` in `changes` and creates `src/devops_cli/roadmap/stage/probe.py`.
- **THEN** the group moves `src/devops_cli/roadmap/stage_probe.py`, with the dotted name `devops_cli.roadmap.stage_probe`.

### Requirement: A reference in a file of a tool or a record needs no task group
The stage job SHALL accept a probed reference to a moved module with no task group and no `unchanged` entry when the file is of class `tool-owned` or `record` in the inventory of the documents. It SHALL refuse any other probed file that no group changes and that the reply does not mark unchanged.

#### Scenario: The changelog names a moved module
- **WHEN** the probe lists `CHANGELOG.md`, and no group changes it.
- **THEN** `check_proposal` returns no problem for `CHANGELOG.md`.

#### Scenario: The folder of another change names a moved module
- **WHEN** the probe lists `openspec/changes/3253-map-all-issue-requirements-to-a/proposal.md`, and no group changes it.
- **THEN** `check_proposal` returns no problem for that path.

#### Scenario: A hand-written document names a moved module
- **WHEN** the probe lists `docs/ROADMAP_WORKFLOW.md`, and no group changes it.
- **THEN** `check_proposal` returns a problem that names `docs/ROADMAP_WORKFLOW.md`.

### Requirement: A line citation may hold its text in the code span that follows it
The stage job SHALL read the text of a citation `path:line:` from the code span that follows it when no text stands between the citation and the next backtick. The closing backtick of the citation and white space MAY stand between them. It SHALL compare that text with the cited line as it compares the text of a citation in one span, and SHALL refuse a text of fewer than 3 characters or a text that the line does not hold.

#### Scenario: The text stands in its own span
- **WHEN** the feasibility section says `src/x.py:4:` followed by the line `def f(): pass` in a code span, and line 4 of `src/x.py` holds `def f(): pass`.
- **THEN** `check_proposal` returns no citation problem for `src/x.py`.

#### Scenario: The span holds another text
- **WHEN** the feasibility section says `src/x.py:4:` followed by `def g(): return 1` in a code span, and line 4 of `src/x.py` holds `def f(): pass`.
- **THEN** `check_proposal` returns a problem that names `src/x.py`.

#### Scenario: The span holds too little text
- **WHEN** the feasibility section says `src/x.py:4:` followed by `de` in a code span.
- **THEN** `check_proposal` returns a problem that names `src/x.py`.

### Requirement: The Service asks Jev about the criteria of a green stage draft
With the setting `roadmap.stage.jev_completeness` true, the row `stage_ready` SHALL ask TypeSafe Jev, after the check runs of a draft passed and before it marks the draft ready, whether the plan delivers each acceptance criterion of the item. It SHALL send one request with a Noul question for each criterion and a Score question for the tests. Otherwise it SHALL send no request to Jev.

#### Scenario: The setting is off
- **WHEN** the setting is false
- **THEN** the round sends no request to Jev

#### Scenario: A check did not pass
- **WHEN** a check run of the draft failed or is running
- **THEN** the round sends no request to Jev

#### Scenario: Jev does not doubt
- **WHEN** every criterion has a probability at or above `CONST_ROADMAP_JEV_CRITERION_THRESHOLD` and the tests score at least `CONST_ROADMAP_JEV_MIN_TEST_SCORE`
- **THEN** the round marks the pull request ready as it does without the check, and the record holds no `stage.jev`

### Requirement: A doubt or an error of Jev only holds the draft
A criterion below the threshold, a test score below the minimum, or an error of Jev SHALL keep the pull request a draft and post one note that lists the points in doubt. The round SHALL record `stage.jev` with the head commit and the outcome. It SHALL NOT ask again for a head commit that it held on doubt, SHALL ask again for a new head commit and after an error, and SHALL post no second note for one head commit. The check SHALL NOT mark a pull request ready, merge or close.

#### Scenario: Jev doubts a criterion
- **WHEN** a green draft is read with the setting true and Jev gives a probability below the threshold for a criterion
- **THEN** the pull request stays a draft, one note names the criterion, and `stage.jev` holds the head commit with `held`
- **AND** a second round for the same head commit sends no request to Jev and posts no second note

#### Scenario: Jev gives no answer
- **WHEN** the request to Jev fails
- **THEN** the pull request stays a draft and one note says that Jev gave no answer
- **AND** the next round asks again and posts no second note for the same head commit

#### Scenario: A new head commit
- **WHEN** a person pushes a commit to a held draft
- **THEN** the next round asks Jev again for the new head commit

### Requirement: The check skips what it cannot judge and counts its outcome
A diff over `CONST_ROADMAP_JEV_MAX_DIFF_TOKENS`, an item with no criterion, and an item with more than `CONST_ROADMAP_JEV_MAX_CRITERIA` criteria SHALL skip the check with a logged reason and no request. The check SHALL count each outcome in `devops_cli_roadmap_jev_completeness_total` with the label `outcome` of four values: `passed`, `held`, `error` and `skipped`.

#### Scenario: A diff over the bound
- **WHEN** the diff holds more tokens than the bound
- **THEN** the check sends no request, logs the reason, and counts `skipped`

### Requirement: Code that reads a file is no claim of the run
The stage job SHALL NOT take `reads` or `reading` as a claim that the run read a path when a code span, `it` or `which` is its subject. It SHALL still refuse a claim of the run or of the author, such as `I read` or `the run read`, when the plan runs hold no call for the path.

#### Scenario: A function reads a file
- **WHEN** the trace holds no call and the feasibility section says `because it reads `.github/labels.yml` of the default branch`.
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: The author reads a file
- **WHEN** the trace holds no call and the feasibility section says `I read `src/x.py` and found the function`.
- **THEN** `check_proposal` returns a problem that names `src/x.py`.

### Requirement: A Jev screen may skip the model review of a plan
The screen before the model review of a plan SHALL be the decision point `stage.verify_screen`, with its mode in `roadmap.decisions`. With the mode `on` and `ai.decision_model` set, the stage job SHALL ask the decision model nine yes/no questions about a digest of the input of the review in one request, and SHALL skip the review when no probability reaches its fitted cut. With any other mode or band, or with `ai.decision_model` empty, the review SHALL run.

#### Scenario: The setting is off
- **WHEN** the stage job reviews a plan and `stage.verify_screen` is not in `roadmap.decisions`
- **THEN** the reviewer runs and no request goes to the decision model

#### Scenario: No decision model is configured
- **WHEN** `stage.verify_screen` has the mode `on` and `ai.decision_model` is empty
- **THEN** the reviewer runs, no request goes to the decision model, and the counter `devops_cli_decision_point_total` has no series

#### Scenario: Mode on and the band continue
- **WHEN** the mode is `on` and every probability is under its cut
- **THEN** the reviewer is not called and the plan has no finding

#### Scenario: Mode on and a probability at its cut
- **WHEN** the mode is `on` and one probability is at or above its cut
- **THEN** the reviewer runs

#### Scenario: Mode shadow
- **WHEN** the mode is `shadow`
- **THEN** the reviewer runs, one counter point names the point, the resolver `model`, the band and the mode, and one decision record and one outcome record share an identifier and name the band and the result of the reviewer

### Requirement: The screen fails open
The screen SHALL run the review when the request to the decision model raises an error, times out or leaves a question unanswered, or when the digest holds a secret. It SHALL log the cause and count the resolver `fallback` with the band `none`.

#### Scenario: Jev fails
- **WHEN** the mode is `on` and the request to the decision model `typesafe/jev-1.14` fails with HTTP 503
- **THEN** the reviewer runs, one warning names the error, and the counter counts the resolver `fallback` with the band `none`

### Requirement: The cuts of the screen are fitted data
The cuts of the screen SHALL be read from `jev_screen_cuts.json`, which SHALL hold the Jev model, the day of the fit, the number of cases and the numbers of the check on the other half. The file SHALL have a cut for each question of the screen.

#### Scenario: The data file
- **WHEN** a test loads the cuts of the screen
- **THEN** each of the nine questions has a cut, and the file names the model and the cases of its fit

#### Scenario: MODIFIED of an unknown requirement
- **WHEN** a MODIFIED block names a requirement that the base spec does not hold
- **THEN** the block is unchanged and the validation problem still reaches the model

### Requirement: A cut tool answer says so
The answer of a read-only tool of a roadmap job SHALL end at a whole line when the character limit shortens it, and a single line over the limit SHALL be cut. An answer that lost text to the line limit or to the character limit SHALL end with the line `(more lines are left out)`. An answer under both limits SHALL have no notice.

#### Scenario: The character limit drops lines
- **WHEN** a tool answers with 100 lines of 100 characters and the character limit is 8,000
- **THEN** the answer holds whole lines only, and its last line is `(more lines are left out)`

#### Scenario: An answer under both limits
- **WHEN** a tool answers with 10 lines of 100 characters
- **THEN** the answer is those lines and has no notice

#### Scenario: One line over the limit
- **WHEN** a tool answers with one line of 8,500 characters
- **THEN** the answer is the first 8,000 characters of the line and the notice

### Requirement: A failed model call names its reason
The stage job SHALL name the reason of an item that fails with `AIClientError`: the error code with the HTTP status or the timeout, then the message of the error with each quoted part hidden. It SHALL log one warning line `stage model call failed` with the number of the item, the class of the error, its code, its HTTP status and whether it timed out, and no text of the message. The reason SHALL NOT hold the text that a provider quotes from the model.

#### Scenario: A gateway error
- **WHEN** the model call of item 1 fails with `AIClientError("gateway returned 502", status=502)`
- **THEN** the failure of item 1 has the error `AIClientError`, and its reason holds `HTTP 502` and `gateway returned 502`, and the log holds one line with `item=#1` and `status=502`

#### Scenario: A provider that quotes the model
- **WHEN** the message of the error is `Ollama returned HTTP 500. Response: 'the reply of the model'`
- **THEN** the reason holds `Ollama returned HTTP 500` and does not hold `the reply of the model`

### Requirement: A run has a call budget
From call `CONST_ROADMAP_STAGE_PLAN_CALLS_NOTICE` of a stage plan run, and from call `CONST_ROADMAP_STAGE_REVIEW_CALLS_NOTICE` of a review run, the answer of each tool SHALL end with a notice that names the call number and tells the model to read no more and give its reply. The tools SHALL stay on, and each run SHALL start its count at zero.

#### Scenario: A plan run past its budget
- **WHEN** a plan run makes three calls and the budget of a plan run is 2
- **THEN** the answer of the first call has no notice, and the answers of the second and third calls end with the notice

#### Scenario: A review run
- **WHEN** a review run makes three calls, the budget of a plan run is 1 and the budget of a review run is 3
- **THEN** only the answer of the third call ends with the notice

#### Scenario: A new run
- **WHEN** a second run starts after a run that passed its budget
- **THEN** the first answers of the second run have no notice

### Requirement: The prompts of a run name its call budget
The prompt of a stage plan run SHALL say that a plan needs about `CONST_ROADMAP_STAGE_PLAN_CALLS_ADVISED` tool calls, and the prompt of a review run SHALL say that a review needs about `CONST_ROADMAP_STAGE_REVIEW_CALLS_ADVISED`. Each prompt SHALL name the call from which the answers carry the notice. The prompt of a plan run SHALL say that a request with `problem` needs a tool call only to check what the problem names.

#### Scenario: The prompts
- **WHEN** the prompts of the plan run and the review run are read
- **THEN** they name the advised calls and the call of the notice that the constants hold

### Requirement: A refused revision of a repair round returns
A revision of a repair round that the checks refuse SHALL go back to the planner with the refused revision as `previous` and the problem as `problem`, `CONST_ROADMAP_STAGE_GATE_RETURNS` times (one) for each repair round, as a refused first reply does. A revision that the checks accept SHALL cause no extra planner call. A revision that is a placeholder in every text SHALL end the item with no return.

#### Scenario: The first revision is refused and the second passes
- **WHEN** the checks refuse the first revision of a repair round and accept the second
- **THEN** the planner gets a third request with `previous` set to the refused revision and `problem` set to the problem of the checks, and the job stages the second revision

#### Scenario: The revision passes
- **WHEN** the checks accept the first revision of a repair round
- **THEN** the planner gets no return for the round

### Requirement: A revision that stays refused ends the item and is kept
When the checks refuse the returned revision of a repair round, the item SHALL fail with a text that names the review and the problem, the planner SHALL make no further request, and `<n>.refused.json` SHALL hold each refused reply of the item with its problem, the refused revisions included.

#### Scenario: Both revisions are refused
- **WHEN** the checks refuse the revision and the returned revision of a repair round
- **THEN** the item fails, the planner has made three requests, and the failure text holds the problem of the second refusal

#### Scenario: The file holds the earlier replies
- **WHEN** the checks refuse the first reply, accept the reply after the return, and refuse both revisions of the repair round
- **THEN** the file `1.refused.json` holds the refused first reply and both refused revisions, each with its problem

### Requirement: Refuse a behavior group that omits the test of its module
The stage plan validation SHALL refuse a behavior group that changes an existing Python module under `src/` and names no test file of the staged tree that imports that module, imports a package whose `__init__.py` imports it, or imports another module that the plan changes and that imports it.

#### Scenario: A source change names only a new test
- **WHEN** a behavior group changes `src/devops_cli/roadmap/stage/stage_paths.py` and names only the test file it creates, while `tests/roadmap/stage/test_roadmap_stage_paths.py` imports that module
- **THEN** `existing_test_problems` returns one problem that names the group, the module and that test

### Requirement: Accept a behavior group that names the test of its module
The stage plan validation SHALL accept a behavior group that changes an existing Python module under `src/` and names at least one test file of the staged tree that imports that module, imports a package whose `__init__.py` imports it, or imports another module that the plan changes and that imports it.

#### Scenario: The named test imports the module and its file name differs from the module name
- **WHEN** a behavior group changes `src/devops_cli/roadmap/stage/stage_paths.py` and lists `tests/roadmap/stage/test_roadmap_stage_paths.py` in its `reads`
- **THEN** `existing_test_problems` returns no problem for that group

#### Scenario: The named test imports the package of the messages
- **WHEN** a behavior group changes `src/devops_cli/lang/en/messages.py` and reads a test that holds `from devops_cli.lang import MESSAGES`
- **THEN** `existing_test_problems` returns no problem for that group

#### Scenario: The named test runs the messages through a changed module
- **WHEN** a behavior group changes `src/devops_cli/roadmap/follow.py`, which imports the messages, and `src/devops_cli/lang/en/messages.py`, and reads the test that imports `devops_cli.roadmap.follow`
- **THEN** `existing_test_problems` returns no problem for that group

### Requirement: Exempt a module that has no existing test
The stage plan validation SHALL accept a behavior group that changes an existing Python module under `src/` when the staged tree holds no test file that imports that module, a package whose `__init__.py` imports it, or another module that the plan changes and that imports it.

#### Scenario: An existing module has no existing test
- **WHEN** a behavior group changes a module of `src/` and the staged tree holds no test file of that module
- **THEN** `existing_test_problems` returns no problem for that group

### Requirement: Leave out the test files that the plan creates
The stage plan validation MUST leave out every test path that a group lists in `creates`, so that a test file that the plan creates is no existing test.

#### Scenario: The plan creates the only test of a module it also changes
- **WHEN** a behavior group changes an existing module and creates the only test file that imports it
- **THEN** the created test is no existing test, and `existing_test_problems` returns no problem for that group

### Requirement: Report one problem for each group that omits its test
The stage plan validation SHALL report one problem for each behavior group that omits an existing test file of a module it changes.

#### Scenario: Two groups omit their existing tests
- **WHEN** two behavior groups each change an existing module of `src/` and name no existing test of it
- **THEN** `existing_test_problems` returns one problem for each group

### Requirement: The allow-list holds the read-only rows of the exposure table
The builder SHALL hold each command path whose row of `CONST_MCP_EXPOSURE_TABLE` is read-only and whose permitted parameters hold no path parameter, with the permitted parameter names as its value.

#### Scenario: A read-only command with no path parameter
- **WHEN** the builder runs and the row of `gh labels list` is read-only and its permitted parameters hold no path parameter
- **THEN** the table holds `('gh', 'labels', 'list')` with `repo` among its parameters

### Requirement: A path parameter keeps its command out of the allow-list
The builder SHALL leave out each command path whose permitted parameters hold a path parameter: a parameter that Typer types as a path, or a parameter that `PATH_CONFINEMENTS` names for the command.

#### Scenario: A restricted command with a path parameter
- **WHEN** the allowed set of `tf plan` holds a directory parameter that Typer types as a path
- **THEN** the table holds no entry for `('tf', 'plan')` and the validator returns the reason `path option`

#### Scenario: An unrestricted command with a path parameter
- **WHEN** the repository parameter of `ai read` has a path type
- **THEN** the table holds no entry for `('ai', 'read')` and the validator returns the reason `path option`

#### Scenario: A text parameter that holds a path
- **WHEN** the builder runs and `scan sast` permits `config`, which holds a path and which no type shows
- **THEN** the table holds no entry for `('scan', 'sast')` and the validator returns the reason `path option`

### Requirement: A restricted command permits only its allowed options
The builder SHALL take the permitted options of a command that `_PATH_PARAM_RESTRICTIONS` names from that entry's `allowed` set.

#### Scenario: A restricted command with no path parameter
- **WHEN** the builder runs and the entry of `telemetry profile` allows one option
- **THEN** the table holds `('telemetry', 'profile')` with that option as its only one

### Requirement: The help form of a command path is permitted
The validator SHALL permit the `--help` form of each command path that the Click tree resolves and SHALL return no reason for it.

#### Scenario: Help of a write command
- **WHEN** the validator checks `valkey flush` with the `--help` option
- **THEN** it permits the run and returns no reason

### Requirement: A refused run names the path and one reason
The validator SHALL return the command path and one reason from `unknown command`, `not read-only`, `path option` and `option not permitted` for a run that it refuses, and SHALL name the option for `option not permitted`.

#### Scenario: A command path that no row names
- **WHEN** the validator checks `config unset`
- **THEN** it refuses the run with the reason `unknown command` and names the path `('config', 'unset')`

#### Scenario: An option outside the permitted set
- **WHEN** the validator checks `ai benchmark` with the `output` option
- **THEN** it refuses the run with the reason `option not permitted` and names `output`

### Requirement: Each read tool description shows its answer format whole
The description that the stage planner and the refine investigation send for each read tool SHALL hold the answer format of the tool whole, such as `path:line:content` for `search_code` and `callers` and `line: signature` for `file_symbols`. No description SHALL hold a `<returns>` part that the docstring parser makes.

#### Scenario: The model reads the search tool
- **WHEN** the stage planner or the refine investigation builds the definition of `search_code`
- **THEN** its description holds `path:line:content` whole and has no `<returns>` part

#### Scenario: The model reads the symbol tool
- **WHEN** the stage planner builds the definition of `file_symbols`
- **THEN** its description holds `line: signature` whole and has no `<returns>` part

### Requirement: The trace gate reads the path of each citation form
The stage job SHALL judge a Feasibility read claim by the path of its code span: the path of a `path:N`, `path:N-M`, `path:N:text` or `path:def name` citation, without a toolbox tool name before it, a leading `./` or a trailing `/`. It SHALL remove each sentence of the probe lines that the plan quotes before it reads the claim. It SHALL still refuse a claim of a path that the plan runs did not read, and name that path.

#### Scenario: A line range of a read file
- **WHEN** the trace holds a `read_file` call for `src/x.py` and the feasibility section says `the run read `src/x.py:10-20``.
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A tool name before a read path
- **WHEN** the trace holds a `read_file` call for `src/x.py` and the feasibility section says `the run read `read_file src/x.py``.
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A listed directory with a trailing slash
- **WHEN** the trace holds a `list_files` call for the directory `tests/telemetry` and the feasibility section says `the run read `tests/telemetry/``.
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A line range of an unread file
- **WHEN** the trace holds a `read_file` call for `src/x.py` and the feasibility section says `the run read `src/y.py:10-20``.
- **THEN** `check_proposal` returns a problem that names `src/y.py`.

#### Scenario: A quoted probe line
- **WHEN** the trace holds no call, the probe lines hold `The path `src/x.py` is a file of the staging commit.`, and the feasibility section says `The probe line reads: The path `src/x.py` is a file of the staging commit.`
- **THEN** `check_proposal` returns no trace problem.

### Requirement: A test that holds the name of a module in text is no test of it
The stage plan validation SHALL NOT count a test file as a test of a module when the test holds the path or the dotted name of the module only in a string, in a comment or in an import for types only.

#### Scenario: The scaffold test holds the path of the messages module
- **WHEN** a behavior group changes `src/devops_cli/lang/en/messages.py`, and `tests/commands/test_new.py` holds the string `src/devops_cli/lang/en/messages.py` and imports no module of `devops_cli.lang`
- **THEN** `record_module_tests` does not name `tests/commands/test_new.py` for that module

#### Scenario: The search reads a dotted name as fixed text
- **WHEN** `grep_at` searches for `devops_cli.lang.en.messages`, and one test holds that dotted name while another holds only the path `src/devops_cli/lang/en/messages.py`
- **THEN** `grep_at` returns only the test that holds the dotted name

### Requirement: A left-out item counts and logs its reason
A stage round SHALL count a skipped item in `devops_cli_roadmap_stage_total` with the label `reason`, a bounded kind of the rule that left it out, such as `title_type`, `held`, `returned` or `rejected`, and `none` for another result. The Service SHALL log the kind and the text of the reason of a left-out item once, and again only when its kind changes.

#### Scenario: Each result carries a reason label
- **WHEN** a round leaves one item out for its title type, stages one, returns one and finds one rejected
- **THEN** the counter has one point each for `title_type`, `returned` and `rejected` under `skipped`, and one for `none` under `staged`

#### Scenario: A reason logs once until it changes
- **WHEN** three rounds leave one item out, the first two for its title type and the third for the label `needs-split`
- **THEN** each round counts the item, and two log lines name the item, one with `title_type` and one with `needs_split`

### Requirement: Refused plans count on their body
When the stage job records a `plan_defect` failure, it SHALL write in the same write `stage.plan_defects`, the count of such failures on the body, and `stage.plan_defects_body`, the hash of the body without the block of the alternatives job. A body that hashes differently SHALL start the count at 1. A failure of another class SHALL keep both keys and its own `RETRY_AFTER` wait.

#### Scenario: A second refused plan on the same body
- **WHEN** the job records the second `plan_defect` failure of an item whose body did not change
- **THEN** the job record of the item holds `stage.plan_defects` 2, and the item stays Ready

#### Scenario: An edited body starts a new count
- **WHEN** an item has 2 `plan_defect` failures, a person edits its body, and the job records a `plan_defect` failure
- **THEN** the job record holds `stage.plan_defects` 1, and the item stays Ready with no comment of the job

#### Scenario: A provider failure does not count
- **WHEN** an item has 2 `plan_defect` failures and the job records a `provider` failure
- **THEN** the job record holds `stage.plan_defects` 2 and `stage.failed_class` `provider`

### Requirement: The limit of refused plans returns the item to New
The `plan_defect` failure that brings the count to `CONST_ROADMAP_STAGE_PLAN_DEFECT_LIMIT` (3) SHALL return the item to New in the same round. The job SHALL post one comment that lists in sequence, one line each and with no handle that pings, the problems of the refused replies of the last plan and then the reason of the failure, unless the checks refused the last reply. It SHALL then set New with the failure keys and clear both count keys.

#### Scenario: The third refused plan
- **WHEN** an item has 2 `plan_defect` failures on its body and a round of the Service refuses its plan again
- **THEN** the item is New, one comment of the stage job lists the problems of the refused replies, and the job record holds no `stage.plan_defects`

#### Scenario: A failure with no refused reply
- **WHEN** the failure at the limit holds no problem of a refused reply
- **THEN** the comment lists the reason of the failure

#### Scenario: A plan run that stops after a refused reply
- **WHEN** the checks refuse the first reply of the last plan and the second plan run stops
- **THEN** the comment lists the problem of the refused reply and then the reason of the stop

#### Scenario: A problem that names a handle
- **WHEN** a problem at the limit holds a handle and a line break
- **THEN** the comment shows the problem on one line with the handle in a code span

### Requirement: A staged item clears the count of refused plans
A run that stages an item SHALL clear `stage.plan_defects` and `stage.plan_defects_body` in the write of its stage record.

#### Scenario: A staged item after a refused plan
- **WHEN** a round stages an item whose job record holds a count of refused plans
- **THEN** the job record of the item holds neither count key

### Requirement: The stale test path problem names the same-name files
The problem of a test path that names no file of the commit SHALL end with the same hint as the missing-path message: the text of `stage_path_same_name` for the files of the staged tree with that file name, or the text of `stage_path_no_same_name` when no file has the name.

#### Scenario: One file has the same name
- **WHEN** a changed docstring names `tests/test_item_grounding.py` and the staged tree holds `tests/github/test_item_grounding.py`
- **THEN** the problem ends with the text of `stage_path_same_name` for `tests/github/test_item_grounding.py`

#### Scenario: No file has the same name
- **WHEN** a changed docstring names `tests/test_absent.py` and no file of the staged tree has the name `test_absent.py`
- **THEN** the problem ends with the text of `stage_path_no_same_name`

### Requirement: Refuse a requirement text over the OpenSpec limit
`check_proposal` SHALL refuse each ADDED and MODIFIED requirement of a spec delta whose text is longer than `REQUIREMENT_MAX_CHARS`, the 500 characters that the strict OpenSpec validation of a spec allows. It SHALL count UTF-16 code units, as OpenSpec does. The problem SHALL name the requirement, its length and the limit, and `devops roadmap plan-check` SHALL report it with the rule `stage`.

#### Scenario: An ADDED requirement of 543 characters
- **WHEN** a spec delta ADDs a requirement whose text has 543 characters
- **THEN** `check_proposal` returns one problem that names the requirement, the length 543 and the limit 500

#### Scenario: The MODIFIED requirement of the #3462 plan
- **WHEN** a spec delta modifies a requirement with the text of 543 characters of the #3462 plan
- **THEN** `check_proposal` returns one problem that names the requirement and the length 543

#### Scenario: A requirement at the limit
- **WHEN** a spec delta holds a requirement text of exactly 500 characters
- **THEN** `check_proposal` returns no problem

#### Scenario: A character outside the Basic Multilingual Plane
- **WHEN** a requirement text holds 499 other characters and one emoji
- **THEN** `check_proposal` returns a problem with the length 501

#### Scenario: plan-check on a long requirement
- **WHEN** `devops roadmap plan-check` reads a change folder with a requirement text of 543 characters
- **THEN** the result holds one problem with the rule `stage` that names the requirement and the length 543

### Requirement: The trace gate reads the subject and the object of a read word
The stage job SHALL take a read word as a claim of the run only when it is `read_file`, a passive or participle, a noun read, a read with no subject, or a read whose subject or list subject names the run or its author. A subject that is the plan, a group, the probe or code, and `read-only` SHALL be no claim. The gate SHALL judge the path that the read takes: the subject of a passive, else the first path of its object up to a result verb unless a pronoun starts it, else the last path before it.

#### Scenario: The plan is the subject
- **WHEN** the trace holds no path and the feasibility section says `` This plan reads `tests/x.py` in group 2. ``
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A read-only root
- **WHEN** the trace holds no path and the feasibility section says `` `k8s/x.yaml` runs the pod with a read-only root. ``
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A path in another clause
- **WHEN** the trace holds the tools `read_file` and `search_code` and no path, and the feasibility section says `` `read_file` of that prompt shows the rule, and `search_code` returned one hit in `src/tf.py`. ``
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A path in the result of a read
- **WHEN** the trace holds the tool `read_file` and the path `docs/a.md`, and the feasibility section says `` `docs/a.md` is a file, and `read_file` on it showed the text "see `src/b.py`". ``
- **THEN** `check_proposal` returns no trace problem, and with only the path `src/b.py` in the trace it returns a problem that names `docs/a.md`.

#### Scenario: A claim of the run
- **WHEN** the trace holds no path and the feasibility section says `` I read `src/missing.py` and found the function. ``
- **THEN** `check_proposal` returns a problem that names `src/missing.py`.

#### Scenario: A passive read
- **WHEN** the trace holds no path and the feasibility section says `` `src/missing.py` was read on the base. ``
- **THEN** `check_proposal` returns a problem that names `src/missing.py`.

#### Scenario: A verb of a list
- **WHEN** the trace holds no path and the feasibility section says `` I listed the folder, opened the test and read `src/missing.py`. ``
- **THEN** `check_proposal` returns a problem that names `src/missing.py`.

#### Scenario: A noun read
- **WHEN** the trace holds no path and the feasibility section says `` A quick read of `src/missing.py` shows the seam. ``
- **THEN** `check_proposal` returns a problem that names `src/missing.py`.

#### Scenario: A participle
- **WHEN** the trace holds no path and the feasibility section says `` The file `src/missing.py`, read at the base, shows the seam. ``
- **THEN** `check_proposal` returns a problem that names `src/missing.py`.

#### Scenario: A pronoun object
- **WHEN** the trace holds the tool `read_file` and the path `docs/a.md`, and the feasibility section says `` `docs/a.md` is a file, and `read_file` on it revealed the text "see `src/b.py`". ``
- **THEN** `check_proposal` returns no trace problem, and with only the path `src/b.py` in the trace it returns a problem that names `docs/a.md`.

### Requirement: A search match supports a citation of its line
`TraceFacts.of` SHALL hold the `path:line` of each match line of a `search_code` or `callers` answer, and the kept plan file SHALL hold those that its Feasibility section cites. The trace gate SHALL accept a read whose object is a `path:line` or `path:line:text` citation of such a line. It SHALL still refuse `read_file`, a read that takes the line through a pronoun, a claim of the whole file, of another line or of a line range, and it SHALL give a path of a probe line no support.

#### Scenario: A search answer
- **WHEN** a `search_code` call of a plan run gets the answer `tests/a.py:5:import x`
- **THEN** `TraceFacts.of` holds the line `tests/a.py:5`.

#### Scenario: A citation of a match line
- **WHEN** the trace holds the match line `tests/a.py:5` and no path, and the feasibility section says `` The run read `tests/a.py:5:import x`. ``
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A claim of the whole file
- **WHEN** the trace holds the match line `tests/a.py:5` and no path, and the feasibility section says `` The run read `tests/a.py`. ``
- **THEN** `check_proposal` returns a problem that names `tests/a.py`.

#### Scenario: A pronoun read of a match line
- **WHEN** the trace holds the match line `tests/a.py:5` and no path, and the feasibility section says `` `search_code` returned `tests/a.py:5:import x`, and `read_file` on it showed the imports. ``
- **THEN** `check_proposal` returns a problem that names `tests/a.py`.

### Requirement: The record orders a module's tests nearest first
`record_module_tests` SHALL order the tests of each module by closeness: the mirror test, then a test that imports the dotted name of the module, then a test in the mirror folder, then the rest, each class in path order. It SHALL keep every test that imports the module or an exporting package. A module at the top of the package SHALL have no mirror rank.

#### Scenario: The mirror test comes first
- **WHEN** the record of `src/devops_cli/lang/en/messages.py` holds `tests/lang/en/test_messages.py` and `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`, and both import `devops_cli.lang`
- **THEN** `record_module_tests` returns `tests/lang/en/test_messages.py` first

#### Scenario: A direct import beats a package import
- **WHEN** one test imports `devops_cli.lang.en.messages` and another, first in path order, imports only `devops_cli.lang`
- **THEN** the test that imports the module itself comes first

#### Scenario: Equal tests keep path order
- **WHEN** every test of the record imports `devops_cli.lang` and none is the mirror test
- **THEN** `record_module_tests` returns each test once, in path order

### Requirement: A test of another changed module ranks last
`record_module_tests` SHALL list a test that only another module of the plan imports after every test that imports the changed module itself.

#### Scenario: The module's own test comes first
- **WHEN** a plan changes `stage_paths.py` and `step_files.py`, which imports it, and only the second has a test that imports it
- **THEN** the test of `stage_paths.py` comes first in its record

### Requirement: The problem names the nearest test
`existing_test_problems` SHALL name the first test of the record of the module in the problem sentence, and no later test.

#### Scenario: The problem names the mirror test
- **WHEN** a behavior group changes `src/devops_cli/lang/en/messages.py` and names no test of it, and the record starts with `tests/lang/en/test_messages.py`
- **THEN** the sentence holds `tests/lang/en/test_messages.py` and no other test of the record
