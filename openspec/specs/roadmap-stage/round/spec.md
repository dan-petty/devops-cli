# roadmap-stage/round Specification

## Purpose
The work of a stage round on each item: the staged branch, its one commit and its draft pull request, the comment and the job record of the item, the writes and the metrics of the round, and how a failure stops one item.

## Requirements

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

### Requirement: The comment and the record of a staged item
The job SHALL post one comment on the issue with the marker `<!-- devops roadmap stage -->` that names the branch, the pull request, the groups with their measures and the budget. The job SHALL record `stage.branch`, `stage.pr`, `stage.sha` and `stage.groups` in the job record. The job SHALL NOT change the Status of the item.

#### Scenario: The comment and the record
- **WHEN** the job stages a Ready bug
- **THEN** the issue gets one comment with the marker, the record holds the four keys, and the Status is still Ready

#### Scenario: A title with no type
- **WHEN** the title of the item has no Conventional Commit type
- **THEN** the plan leaves the item out and says that its title has no type

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

### Requirement: A failed item is recorded in its job record
When the plan or a write of an item fails, the job SHALL record the time (`stage.failed_at`) and the class of the error (`stage.failed_error`) in the job record of the item. A run that stages the item or stops it on the budget SHALL clear both keys.

#### Scenario: A failure is recorded
- **WHEN** the model call fails for an item with the error class `AIClientError`
- **THEN** the job record of the item holds the time of the round and `AIClientError`

#### Scenario: The item is staged
- **WHEN** a run stages an item whose job record holds a failure
- **THEN** the job record of the item holds neither key afterwards

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

### Requirement: A staged item records the hash of its text
When the job stages an item, it SHALL record `stage.text_hash`: the hash of the text of the item outside the refine section that the plan came from. A rejected plan SHALL clear it, and a record that holds none SHALL take the hash of the text at the time of the read.

#### Scenario: The job stages an item
- **WHEN** the job stages a Ready item
- **THEN** the record holds `stage.text_hash` with the hash of the body outside the refine section

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
