# roadmap-stage Specification

## Purpose
Defines how `devops roadmap stage` makes a Ready roadmap item Staged: which items it takes, how it plans the OpenSpec change in task groups that fit a context budget, and what it writes to git and GitHub, so a later implementation step starts from a branch and a draft pull request.

## Requirements

### Requirement: The label filter names the items to stage
`devops roadmap stage` SHALL take the open items whose labels match the `--filter family=value` options. The families are `status`, `priority`, `type`, `value` and `effort`. Values of one family SHALL be alternatives, and the families SHALL all apply. With no `--filter`, the filter SHALL be `status=ready`, `priority=p0-critical`, `priority=p1-high` and `type=bug`. A family that is not in the list SHALL be refused.

#### Scenario: The default filter
- **WHEN** the roadmap holds a Ready P1 bug, a Ready P2 bug, a New P1 bug and a Ready P1 feature, and the command runs with no filter
- **THEN** the plan holds only the Ready P1 bug

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
The job SHALL open a draft pull request whose title is `docs(openspec): plan #<issue> <summary>` and whose body starts with `Plans #<issue>` and holds no closing keyword. The part of the title after the colon SHALL have at most 60 characters. The job SHALL NOT mark the pull request ready.

#### Scenario: The draft opens
- **WHEN** the job stages a Ready bug
- **THEN** a draft pull request opens with a body that starts with `Plans #<issue>`

#### Scenario: The body names no closing keyword
- **WHEN** the plan of the model holds the text `Closes #12` in its description of the change
- **THEN** the job stops that item with a failure that names the closing keyword, and pushes nothing

#### Scenario: The title of a bug and of a feature
- **WHEN** the job stages item 12, a bug, and item 13, a feature
- **THEN** the title of each draft starts with `docs(openspec): plan #12 ` and `docs(openspec): plan #13 `, and the branch of each keeps the type of its issue

#### Scenario: A long summary
- **WHEN** the model gives a summary of 60 characters for item 2656
- **THEN** the title after the colon has at most 60 characters, and the summary is cut at a word

### Requirement: A staged item gets one comment and a record
The job SHALL post one comment on the issue with the marker `<!-- devops roadmap stage -->` that names the branch, the pull request, the groups with their measures and the budget. The job SHALL record `stage.branch`, `stage.pr`, `stage.sha` and `stage.groups` in the job record. The job SHALL NOT change the Status of the item.

#### Scenario: The comment and the record
- **WHEN** the job stages a Ready bug
- **THEN** the issue gets one comment with the marker, the record holds the four keys, and the Status is still Ready

#### Scenario: A title with no type
- **WHEN** the title of the item has no Conventional Commit type
- **THEN** the plan leaves the item out and says that its title has no type

### Requirement: The job measures each task group
The job SHALL measure each task group with tiktoken. The measure SHALL be the tokens of the group's instructions, the item, the change folder and the group's named files, packed with the context packer. The budget SHALL be `roadmap.stage.step_tokens`, default 40000, and `--step-tokens` SHALL override it for one run.

#### Scenario: A group is measured
- **WHEN** the model gives a group that names a file of the repository
- **THEN** the comment on the issue gives the group's measure, and that measure is more than the tokens of the file packed

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
The settings `roadmap.stage.filter`, `roadmap.stage.limit` and `roadmap.stage.step_tokens` SHALL set what the stage job takes. Each SHALL have the variable `DEVOPS_CLI_ROADMAP_STAGE_FILTER`, `DEVOPS_CLI_ROADMAP_STAGE_LIMIT` or `DEVOPS_CLI_ROADMAP_STAGE_STEP_TOKENS`. The defaults SHALL be the filter `status=ready`, `priority=p0-critical`, `priority=p1-high` and `type=bug`, the limit 3 and the step budget 40000.

#### Scenario: The defaults
- **WHEN** no config file and no variable sets a `roadmap.stage` setting
- **THEN** the filter, the limit and the step budget are the defaults above

#### Scenario: A config file and a variable
- **WHEN** the config file sets `roadmap.stage.limit` to 1 and the variable `DEVOPS_CLI_ROADMAP_STAGE_FILTER` holds `status=ready,type=feature`
- **THEN** the limit is 1 and the filter is `status=ready` and `type=feature`

#### Scenario: A round uses the settings
- **WHEN** the filter is `type=feature` and the limit is 1, and the roadmap holds two Ready features and a Ready bug
- **THEN** a round of the `stage` row plans the first feature only

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
