# roadmap-implement-job/stops Specification

## Purpose
How an implement item stops: the Blocked state, the stop comment and its failure class, the clears of a stop, the amendments, the returns to New, and the conflict and premise stops.

## Requirements

### Requirement: A stopped item is Blocked and the job does not retry it
When a step, the rebase, the documentation, the archive, a push or the checks stop the item, the job SHALL post a comment that starts with the marker and names the step, the reason and the last message of the agent, SHALL set Status to Blocked, and SHALL record `implement.stopped` with the step. It SHALL push the commits of the steps that passed, unless a rebase stopped. The job SHALL NOT run the item again until a clear rule removes the record. The job SHALL go on to the next selected item.

#### Scenario: A step stops
- **WHEN** the step of group 2 reports stopped
- **THEN** Status is Blocked, `implement.stopped` is `group 2`, the comment holds the reason, `origin` holds the commit of group 1, and the pull request is still a draft

#### Scenario: A conflict on the rebase before a push
- **WHEN** the default branch gains a change that conflicts with the branch after the last group, or after the fix step
- **THEN** the job aborts the rebase, `origin` holds only the commits that a checkpoint pushed, Status is Blocked, and `implement.stopped` is `push`

### Requirement: The stop comment cuts a long reason
The job SHALL cut the reason of a stop to `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters after it masks secrets in it, so that the stop comment stays below the limit of GitHub.

#### Scenario: A reason that is too long
- **WHEN** a step stops with a reason longer than `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters
- **THEN** the comment holds the first `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters of the reason

### Requirement: The stop comment of a step holds the diff of the discarded work
When a step stops the item, the comment of the job SHALL also hold the masked diff of the work that the step discarded, in one fenced block, with a note when the diff was cut. The fence SHALL be longer than the longest run of backticks in the diff, and at least three backticks. A stop that is not a step SHALL post no diff.

#### Scenario: A step stops and leaves a diff
- **WHEN** the step of group 1 reports stopped with a diff that holds a token in the form of a GitHub token and a line of three backticks
- **THEN** the comment holds the diff in one fenced block, the fence is four backticks long, the block ends only at the closing fence, the comment holds no token, and the text of the comment after the block is the text of the job

#### Scenario: A cut diff
- **WHEN** the diff of the step was cut
- **THEN** the comment says that the diff is cut to `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS` characters

#### Scenario: A stop that is not a step
- **WHEN** the rebase stops the item
- **THEN** the comment holds no diff

### Requirement: A new runner image clears a stop of a retry class
A round SHALL clear the stop of an item that the Service set Blocked, and that no Job and no agent or person holds. The digest in the template of CronJob `devops-cli-runner` must differ from `implement.job_digest`. The class in `implement.failure` must have the action `retry` in `ACTION_BY_CLASS`. A clear SHALL remove `implement.stopped`, set the Status to Ready or Planned, and comment the rule and both digests.

#### Scenario: The digest changed
- **WHEN** an item is Blocked with class `provider` and `implement.job_digest` A and the template names digest B
- **THEN** the round removes `implement.stopped` and sets the Status to Ready
- **AND** the round records the class `provider` and the digest B in `implement.digest_clears` and comments the digest rule with A and B
- **AND** the round creates a Job that records B

#### Scenario: The digest is the same
- **WHEN** an item is Blocked with `implement.job_digest` A and the template names A, no continuation applies, and ten rounds run
- **THEN** the item stays Blocked and the API receives no Job create

#### Scenario: A second stop on the new digest
- **WHEN** the Job that the digest rule started stops the item, no continuation applies, and the template still names B
- **THEN** the item stays Blocked and later rounds create no Job

#### Scenario: A stop with no digest on record
- **WHEN** an item is Blocked with `implement.stopped` and no `implement.job_digest`
- **THEN** the digest rule does not clear it

### Requirement: A clear by digest keeps its record and stays within limits
A clear by digest SHALL append the class, the new digest and the time to `implement.digest_clears`. A stop with no class on record, or with a class of another action, SHALL stay Blocked. The round SHALL NOT clear by digest when the entries for the class reach `roadmap.implement.digest_clears_per_class` (default 1) or the entries of the item reach `roadmap.implement.digest_clears_per_item` (default 3), and SHALL read no content of the runner image.

#### Scenario: A class that a new image cannot fix
- **WHEN** an item is Blocked with class `plan_defect`, `refused_tool`, `premise_false` or `test`, and the template names a new digest
- **THEN** the item stays Blocked, the round reads no template for it, and `implement: retry` still clears it

#### Scenario: A stop with no class
- **WHEN** an item is Blocked with a digest on record and no `implement.failure`, and the template names a new digest
- **THEN** the digest rule does not clear it

#### Scenario: The class limit
- **WHEN** an item is Blocked with class `ci_infra`, `implement.digest_clears` holds one entry of class `ci_infra`, and the template names a new digest
- **THEN** the item stays Blocked until a trusted `implement: retry`

#### Scenario: A second retry class
- **WHEN** an item is Blocked with class `timeout`, `implement.digest_clears` holds one entry of class `provider`, and the template names a new digest
- **THEN** the round clears the stop and the list holds two entries

#### Scenario: The item limit
- **WHEN** an item is Blocked with class `provider`, `implement.digest_clears` holds three entries of other classes, and the template names a new digest
- **THEN** the item stays Blocked until a trusted `implement: retry`

#### Scenario: A record that does not parse
- **WHEN** `implement.digest_clears` is not a valid list
- **THEN** the digest rule does not clear the stop and `implement: retry` still does

### Requirement: A clear by digest writes one comment in a day
The round SHALL write no comment for a clear by digest on an item when `implement.digest_clear_commented_at` is less than 24 hours old, and SHALL still record the clear.

#### Scenario: One clear comment in a day
- **WHEN** a digest clear of an item runs less than 24 hours after `implement.digest_clear_commented_at`
- **THEN** the round clears the stop, records the entry, and writes no comment

#### Scenario: A clear comment after a day
- **WHEN** a digest clear of an item runs 24 hours or more after `implement.digest_clear_commented_at`
- **THEN** the round writes the comment and sets the time to now

### Requirement: A retry from a person clears a stop at once
A comment `implement: retry` of the owner, a member or a collaborator, made after the last comment of the job, SHALL clear the stop of a Blocked item in the next round, whatever the digest. The comment of the Service SHALL name the retry rule.

#### Scenario: A retry on the same digest
- **WHEN** an item is Blocked and its digest is unchanged, and the owner comments `implement: retry`
- **THEN** the round clears the stop, comments the retry rule, and creates a Job

#### Scenario: A retry from a stranger
- **WHEN** a user who is not the owner, a member or a collaborator comments `implement: retry`
- **THEN** the item stays Blocked

### Requirement: A stop that no rule clears lists its comments only after a change
The round SHALL list the comments of a Blocked stop only when the `updated_at` of the issue is not the one of the last listing that the process holds for it, and SHALL read the issue again only when a rule holds. It SHALL read the template at most one time, also when the read fails.

#### Scenario: Three stops that nothing clears
- **WHEN** three items are Blocked and no rule clears them, in the first round of a process
- **THEN** the round sends three listings of comments and reads no issue

#### Scenario: A later round with no change
- **WHEN** a later round finds the same three stops with the same `updated_at`
- **THEN** the round sends no listing of comments

#### Scenario: A retry after the first round
- **WHEN** the owner comments `implement: retry` on one of the stops
- **THEN** the next round lists the comments of that issue only, and clears its stop

### Requirement: The stop comment names the failure class
The stop comment of the job SHALL name the failure class, the action taken and the action left, before the reason. The job SHALL record the class in `implement.failure` with `implement.stopped`, and SHALL write one line with the class and the action left to its log. A retry of a person and a clear rule of the Service SHALL remove `implement.failure` with `implement.stopped`.

#### Scenario: A step that changed no file
- **WHEN** the step of group 2 stops with the reason "The agent changed no file."
- **THEN** the comment holds `Failure class: `plan_defect`.`, `Action taken: none.` and the action left `amend`, `implement.failure` is `plan_defect`, and the log of the job holds the class and `amend`

#### Scenario: Fix rounds that did not pass a check
- **WHEN** the scoped check `pre-push` fails after 3 fix rounds and its log names `ruff`
- **THEN** the comment holds the class `lint`, the action taken `repair` with 3 rounds, and the action left `wait`

#### Scenario: A retry
- **WHEN** a trusted person comments `implement: retry` on a stopped item and the job takes it
- **THEN** `implement.failure` is removed with `implement.stopped`

### Requirement: The Service counts the failures by class
When a round reports a Job that left a stop, the Service SHALL add 1 to `devops_cli_service_implement_failures_total` with the labels `class` and `repo`, where `repo` is the repository of the round. A Job that left the item without a result SHALL get the class of the tail of its log, recorded in `implement.failure` and named, with the action left, in the report. A Job that ended with a result SHALL add nothing.

#### Scenario: A stop of the runner
- **WHEN** a round of `example/app` reports a Job whose item holds the stop with the class `parser`
- **THEN** the counter for `parser` and `example/app` grows by 1, the counter for `oom` does not change, and a second round adds nothing

#### Scenario: A Job with no result
- **WHEN** a round of `example/app` reports a Job that failed and left the item In Progress, and its log holds "out of memory"
- **THEN** the item is Blocked with `implement.failure` `oom`, the report names the class and the action left `raise_limit`, and the counter for `oom` and `example/app` grows by 1

#### Scenario: A Job with a result
- **WHEN** a round reports a Job that succeeded and left the item In Review
- **THEN** no counter changes

### Requirement: The stop comment shows a table of the steps
The stop comment SHALL hold the table of the comment on the pull request, after the lines of the failure class and before the reason. The row of the step that stopped SHALL be in it. The last failing command SHALL be the command of the last `check` event with an exit status other than 0, or the name of the check of the pull request that failed.

#### Scenario: A step that stops on a failed command
- **WHEN** group 2 stops after one repair round, with 4,100 input and 320 output tokens, and `mypy` exited 1
- **THEN** the table holds the row `group 2`, 2 attempts, `4100/320` and the `mypy` command

#### Scenario: A failed check of the pull request
- **WHEN** the checks of the pull request stop the item with the check `Tests & Coverage` failed
- **THEN** the table holds a row for the step of the checks with `Tests & Coverage` as its last failing command

### Requirement: The table cuts its rows and its cells
The table SHALL list at most `CONST_ROADMAP_IMPLEMENT_TABLE_ROWS` rows, the newest, SHALL cut a command to `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS` characters, and SHALL escape a `|` in a cell.

#### Scenario: A command with a pipe
- **WHEN** the last failing command holds `a | b`
- **THEN** the row holds `a \| b` in one cell

#### Scenario: More rows than the bound
- **WHEN** a run has more steps than `CONST_ROADMAP_IMPLEMENT_TABLE_ROWS`
- **THEN** the table holds the newest rows only

### Requirement: A request of a stopped step is judged before the item stops
When a step stops and its last message holds a request (`roadmap-plan-amendment`), the job SHALL judge the request before it stops the item. It SHALL commit an applied amendment as `docs(openspec): amend the plan of group <n> (#N)`, read `tasks.md` again, and run the same group again. It SHALL apply one amendment for each group. A plan that fails the check of the selection is left out before the run, so no request amends a missing test path or a refused command.

#### Scenario: A wrong test path in the plan
- **WHEN** group 1 names a test path that is no file
- **THEN** the plan leaves the item out before the run with the path as its reason, so no step runs and no amendment is committed

#### Scenario: A second request for the same group
- **WHEN** the second step of group 1 stops with another valid request
- **THEN** the job applies nothing, the item is Blocked, and the comment quotes the request as a question

#### Scenario: A stop with no request
- **WHEN** a step stops and its last message holds no `plan-request` block
- **THEN** the job stops the item as it does for any stop

### Requirement: A stop after an amendment names the action taken
When the job applied an amendment for the group that stops the item with the class `plan_defect`, the stop comment SHALL name `amend` as the action taken and `wait` as the action left.

#### Scenario: The amended group fails again
- **WHEN** the job applied an amendment to group 1, and the step of group 1 stops with "The agent changed no file."
- **THEN** the comment holds the class `plan_defect`, the action taken `amend` and the action left `wait`

### Requirement: The comment on the pull request lists each amendment with its evidence
The comment of the job on the pull request SHALL show one line for each applied amendment and each split: the group, the kind, the defect, the evidence, and the old and the new text. A stopped item whose pull request exists SHALL get the same lines in a comment.

#### Scenario: An amended run
- **WHEN** the job applied an amendment and reaches the ready pull request
- **THEN** the comment on the pull request holds a line with the group, the kind, the defect, the evidence, `old` and `new`

#### Scenario: A stop after an amendment
- **WHEN** the job applied an amendment and a later step stops the item, and the pull request exists
- **THEN** the pull request gets a comment with the line of the amendment

### Requirement: A false premise returns the item to New
When a step stops with a `premise` request whose evidence is not empty, the job SHALL return the item to New through `apply_return`, with a comment that holds the evidence masked and cut. Before it returns the item, it SHALL withdraw the checkpoints that it pushed, as the requirement on the withdraw says. A return SHALL remove the worktree and SHALL clear `implement.group`, `implement.sha`, `implement.branch`, `implement.pr` and `implement.base`. It SHALL NOT set `implement.stopped`.

#### Scenario: A false premise on a Planned item
- **WHEN** the first step of a Planned item ends with a `premise` request and evidence
- **THEN** the Status is New, the comment holds the evidence, `origin` has no branch for the item, no worktree is left, and the record has no `implement.stopped`

#### Scenario: A false premise on a Planned item after a checkpoint
- **WHEN** groups 1 and 2 of a Planned item passed, the checkpoints opened one draft pull request, and the step of group 3 ends with a `premise` request and evidence
- **THEN** the Status is New, `origin` has no branch for the item, the draft pull request is closed, and the record holds no `implement.base`

#### Scenario: A false premise on a Staged item
- **WHEN** the step of group 2 of a Staged item ends with a `premise` request, and group 1 passed in this run
- **THEN** the Status is New, `origin` holds the staged branch at the commit it had before the run, and `implement.group` and `implement.base` are cleared

#### Scenario: A premise request with no evidence
- **WHEN** the `premise` request has an empty `evidence`
- **THEN** the item is stopped as a question and its Status is Blocked

### Requirement: A return withdraws the checkpoints first
Before the job returns an item to New, it SHALL withdraw the checkpoints that it pushed. For a Staged item, the withdraw SHALL push the sha of `implement.base` back to the item branch with a lease on the last tip that the job pushed. For a Planned item, the withdraw SHALL delete the item branch with the same lease and close the recorded draft pull request, and SHALL do nothing when `origin` holds no item branch. A withdraw that fails SHALL stop the item as Blocked and SHALL NOT return it.

#### Scenario: A person pushed after the last checkpoint
- **WHEN** a person pushes to the item branch after a checkpoint, and a `premise` request with evidence follows
- **THEN** the lease of the withdraw fails, the item is Blocked and is not returned, and the push of the person stays on the branch

#### Scenario: A withdraw that fails
- **WHEN** the push of the withdraw fails with an error that is not a failed lease
- **THEN** the item is Blocked and is not returned, and `origin` keeps the checkpoints

#### Scenario: A withdraw after a refused draft
- **WHEN** GitHub refused the draft of a Planned item at its first checkpoint, and a `premise` request with evidence follows
- **THEN** the withdraw finds no branch on `origin` and does nothing, and the Status is New

### Requirement: A group over the limit of the step is split once for each item
When the inputs of a group measure more than the limit of the step, the job SHALL ask the split step of the stage job for the groups that replace it, once for each item. It SHALL write them in place of the group, number the later groups after them, give the lines of `## Criteria` the new numbers with the same criterion text, add an amendment bullet, commit, and run the new groups. A new group over the limit, or a second group over the limit in the same item, SHALL stop the item.

#### Scenario: A group is split
- **WHEN** group 2 of 3 measures more than the limit and the split reply gives two groups under the limit
- **THEN** `tasks.md` holds four groups, the old group 3 is group 4 with its tasks numbered `4.1` and on, the `## Criteria` lines hold the same criterion texts with the new numbers, and the job runs groups 2, 3 and 4

#### Scenario: A new group is still over the limit
- **WHEN** a group of the reply measures more than the limit
- **THEN** the job changes no file and stops the item with the class `plan_defect`

#### Scenario: A second group over the limit
- **WHEN** a split happened and a later group measures more than the limit
- **THEN** the job asks for no second split and stops the item

### Requirement: The dry run lists the writes of an amendment, a return and a split
The plan of `devops roadmap implement --dry-run` SHALL list the commit of an amendment, the model request of a split, and the comment and the Status of a return, each with the condition under which the run makes it.

#### Scenario: The dry run
- **WHEN** `devops roadmap implement --dry-run --item 7` runs
- **THEN** the write requests hold the amendment commit, the split request and the return, and each shows its condition

### Requirement: A stop site passes a typed class of its cause
Each stop of the job whose cause has a class SHALL pass that class, and the stop comment and `implement.failure` SHALL hold it. The classifier SHALL NOT decide a class that a site passes. The words of the last message of the agent and the words of a task SHALL NOT change a class. A step that changed no file SHALL pass `no_change_in_fix` in a fix step and `plan_defect` in a group step. A step whose reset of a moved `HEAD` failed SHALL pass `head_moved`.

#### Scenario: A fix step that changed no file
- **WHEN** a fix step stops with the reason "The agent changed no file." and its last message says "The item is already implemented."
- **THEN** the comment holds the class `no_change_in_fix` and `implement.failure` is `no_change_in_fix`

#### Scenario: A group step that changed no file
- **WHEN** the step of group 2 stops with the reason "The agent changed no file."
- **THEN** the class is `plan_defect`

#### Scenario: A lost test, a moved HEAD and the output cap
- **WHEN** a step stops because the agent removed a test, because the reset of a head that the agent moved failed, or because it reached the output cap
- **THEN** the classes are `tests_lost`, `head_moved` and `output_cap`

#### Scenario: The tier decision
- **WHEN** a turn ends with an error whose text the classifier reads as `parser`, and a second turn ends with the output cap and a message that holds the words of a parser failure
- **THEN** the step moves to the next tier after the first turn only, and the outcome of the step holds the class `parser` for the first and `output_cap` for the second, the class that the decision read

### Requirement: The job checks the premise of a behavior group at the branch tip
Before the job runs a behavior group, the job SHALL check each guard or check identifier that a task of the group adds against the branch tip, and SHALL return the item to New with the definition line when the branch tip defines it. The job SHALL read the kind of the group from `TaskGroup.is_behavior` of `src/devops_cli/roadmap/step_files.py`.

#### Scenario: A task adds a guard that the base already runs
- **WHEN** A behavior group task says to add the guard `_delivery_title` and the branch tip defines `_delivery_title`
- **THEN** The job runs no group step, writes no group file, makes no group commit, and comments the definition line with the return to New.

#### Scenario: A task adds a guard that the base lacks
- **WHEN** A behavior group task says to add the guard `_missing_guard` and the branch tip defines no `_missing_guard`
- **THEN** The job runs the group and commits the file that the group writes.

#### Scenario: A group that is not behavior adds a defined name
- **WHEN** A group whose kind is not behavior has a task that says to add the name `_delivery_title`, which the branch tip defines
- **THEN** The job returns no item to New and runs the group.

#### Scenario: The guard premise fails after a checkpoint
- **WHEN** groups 1 and 2 passed and were pushed as checkpoints, and a behavior group 3 adds a guard that the branch tip defines
- **THEN** the job runs no step for group 3, withdraws the checkpoints as for a `premise` request, and returns the item to New

### Requirement: One shared definition lookup reports a definition at a commit
The stage job, the refine context and the implement job SHALL use `definition_lines` of `src/devops_cli/roadmap/premise.py`. A Python file defines a name with a `def`, a `class` or an assignment line. If no Python file defines it, a file of another language defines it when its tree-sitter grammar finds a symbol of that name. A Markdown file defines nothing. A lookup that reads only some files that name it and finds no definition SHALL be undecided. `defines` reports a list that is not empty.

#### Scenario: Both jobs get the definition lines from one function
- **WHEN** The stage job probes a cited identifier and the implement job checks a task at the same commit
- **THEN** Both jobs get the same definition lines from `definition_lines` of `src/devops_cli/roadmap/premise.py`.

#### Scenario: The check writes nothing
- **WHEN** The implement job checks the tasks of a behavior group at the branch tip
- **THEN** The check runs only read-only git commands and the worktree holds no change.

#### Scenario: A Rust function
- **WHEN** the commit holds `src/scout.rs` with `fn scout_reaches_target() {` on line 4, and `src/main.rs`, which calls the function
- **THEN** `definition_lines` gives only line 4 of `src/scout.rs`

#### Scenario: A shell function
- **WHEN** the commit holds `scripts/deploy.sh` with `setup_node() {` on line 2
- **THEN** `definition_lines` gives line 2 of `scripts/deploy.sh`

#### Scenario: A call and a heading are no definition
- **WHEN** only a Rust call and a Markdown heading name `scout_reaches_target`
- **THEN** `definition_lines` gives no line

#### Scenario: A Python definition costs one command
- **WHEN** a Python file and a Rust file define the name
- **THEN** `definition_lines` gives the Python line and runs one git command

#### Scenario: A cut read that finds no definition is undecided
- **WHEN** 21 Rust files call `shared_helper`, and only `src/z_util.rs`, which is after them in path order, defines it
- **THEN** `definition_lines` gives None, not an empty list

### Requirement: A conflict stop names the conflicted files
When a rebase stops the item on a conflict, the job SHALL read the unmerged files with `git diff --name-only --diff-filter=U` before it aborts the rebase. The stop comment SHALL name each file, the job record SHALL hold the files as `implement.conflict`, and the next Job SHALL clear the record in its first record write. The job SHALL mask each path, list at most `CONST_ROADMAP_IMPLEMENT_REASON_PATHS` paths, and state the number of paths that the cut left out.

#### Scenario: A conflict at the start of a run
- **WHEN** the staged branch conflicts with the default branch in a real git repository when the job rebases at the start of the run
- **THEN** the item stops with the class `conflict`, and the comment names each conflicted file

#### Scenario: A conflict before the push
- **WHEN** the default branch gains a change that conflicts with the branch when the job rebases before the push
- **THEN** the item stops with the class `conflict`, and the comment names each conflicted file

#### Scenario: The record holds the files until a retry
- **WHEN** a conflict stops the item, and a person then comments `implement: retry`
- **THEN** `implement.conflict` holds each file after the stop, and holds none after the first record write of the next Job

#### Scenario: A clear rule keeps the files
- **WHEN** a conflict stops the item and a clear rule of the Service removes the stop
- **THEN** `implement.conflict` still holds each file

#### Scenario: A list above the limit
- **WHEN** the conflict holds more files than `CONST_ROADMAP_IMPLEMENT_REASON_PATHS`
- **THEN** the comment names the files up to the limit and states the number of files left out

#### Scenario: A secret in a path
- **WHEN** a conflicted file path holds a token that `mask_secrets` knows
- **THEN** the comment and the record hold the masked path and not the token

### Requirement: The job writes how its run ended
The job SHALL write `implement.result` as the last mark of the write that ends each run of an item. The value SHALL be `ready` for a pull request marked ready, `stopped` for a stop, `yielded` for a claim, and `returned` for a return to New. The job SHALL clear the key in its first record write of a run.

#### Scenario: A run that a claim ended
- **WHEN** a person claims the item while group 1 runs
- **THEN** the record holds `implement.result` equal to `yielded`

#### Scenario: A run that stops
- **WHEN** the scoped checks stop the item
- **THEN** the record holds `implement.result` equal to `stopped`, written after `implement.stopped`

#### Scenario: A stale result
- **WHEN** a new Job starts on an item whose record holds `implement.result` equal to `ready`, and the Job is killed in its first group
- **THEN** the record holds no `implement.result`

### Requirement: The first step of a run gets the stop of the earlier Job
The job SHALL read `implement.check_log` and `implement.conflict` before its first record write of a run. It SHALL give both to the first step of the run in a section `# The stop of the earlier Job` of the step message, and to no later step. The section SHALL be left out when both are empty. The prompt `roadmap_implement_step.md` SHALL state what the section holds.

#### Scenario: A retry after a failed check
- **WHEN** an item stopped with a recorded check log and recorded conflict files, and a trusted person retries
- **THEN** the message of the first step holds the log and the files, the message of the second step holds neither, and the record holds neither key after the first record write

#### Scenario: A continuation after a clear rule
- **WHEN** a clear rule of the Service removed the stop and a new Job takes the item
- **THEN** the message of the first step holds the recorded log

### Requirement: A spec that the archive validation refuses is a plan defect
When `uv run devops openspec archive <change>` exits with status 1 after it moved the change folder into the archive, the strict validation of the specs refused a spec of the plan. The stop SHALL pass the class `plan_defect`, so the action left is `amend`. The words of the output, as `1 failed`, SHALL NOT decide the class. An archive that fails before it moves the folder SHALL keep the class that the classifier gives.

#### Scenario: The validation refuses a long requirement
- **WHEN** the archive moves the change folder, then exits 1 with `Totals: 258 passed, 1 failed (259 items)` and a requirement text longer than 500 characters
- **THEN** the item stops at the archive, `implement.failure` is `plan_defect`, and the comment names the action left `amend` and the spec that failed

#### Scenario: An archive that keeps the change folder
- **WHEN** the archive exits 1 with `openspec: the change has no delta` and the change folder stays in place
- **THEN** the item stops at the archive with the class `ci_infra`
