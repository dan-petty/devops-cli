## MODIFIED Requirements

### Requirement: A stopped item is Blocked and the job does not retry it
When a step, the rebase, the documentation, the archive, a push or the checks stop the item, the job SHALL post a comment that starts with the marker and names the step, the reason and the last message of the agent, SHALL set Status to Blocked, and SHALL record `implement.stopped` with the step. It SHALL push the commits of the steps that passed, unless a rebase stopped. The job SHALL NOT run the item again until a clear rule removes the record. The job SHALL go on to the next selected item.

#### Scenario: A step stops
- **WHEN** the step of group 2 reports stopped
- **THEN** Status is Blocked, `implement.stopped` is `group 2`, the comment holds the reason, `origin` holds the commit of group 1, and the pull request is still a draft

#### Scenario: A conflict on the rebase before a push
- **WHEN** the default branch holds a change that conflicts with a commit of the branch, and no rule settles it
- **THEN** the agent phase aborts the rebase, `publish` pushes nothing, `origin` keeps the branch as it was, Status is Blocked, and `implement.stopped` is `rebase`

### Requirement: The job writes how its run ended
`publish` SHALL write `implement.result` as the last mark of the write that ends each run of an item. The value SHALL be `drafted` for a run that ended at the draft pull request, `stopped` for a stop, `yielded` for a claim, and `returned` for a return to New. `prepare` SHALL clear the key. A `publish` that finds a result in the record SHALL write nothing and give that result, because an earlier `publish` of the same run wrote it.

#### Scenario: A run that a claim ended
- **WHEN** a person claims the item while group 1 runs
- **THEN** the record holds `implement.result` equal to `yielded`

#### Scenario: A run that stops
- **WHEN** the scoped checks stop the item
- **THEN** the record holds `implement.result` equal to `stopped`, written after `implement.stopped`

#### Scenario: A stale result
- **WHEN** a new Job starts on an item whose record holds `implement.result` equal to `drafted`, and the Job is killed in its first group
- **THEN** the record holds no `implement.result`

#### Scenario: A second publish of a stopped run
- **WHEN** `publish` of a Planned item opened the draft and stopped, and `publish` runs again on the same run folder
- **THEN** the second `publish` gives `stopped`, pushes nothing, opens no draft and posts no comment

### Requirement: The job checks the premise of every open behavior group before the first step
The job SHALL check the premise of each open behavior group once in a run, at the first group boundary, before the first step. An open group has a task that is not ticked. The check SHALL read the head of the checkout at that boundary. A later group boundary of the run SHALL make no premise check. The comment of the return SHALL say that the run made no model request and wrote no code.

#### Scenario: A false premise of a late group
- **WHEN** a plan has 3 groups, behavior group 3 adds a guard that the branch defines, and groups 1 and 2 are open
- **THEN** the job returns the item to New before the step of group 1: it makes no model request, pushes nothing, closes no pull request, and the comment names the guard and says that the run made no model request

#### Scenario: A guard of a group that passed in an earlier Job
- **WHEN** an earlier Job passed behavior group 1, which added `_delivery_title`, and group 2 is open
- **THEN** the job checks no premise of group 1, runs group 2, and ends the run at the draft

## ADDED Requirements

### Requirement: A false premise returns the item to New after the withdraw
When a step stops with a `premise` request whose evidence is not empty, the agent phase SHALL end the run with the outcome `returned`. `publish` SHALL push no work of the run, withdraw what earlier Jobs pushed, and return the item to New through `apply_return`, with the evidence masked, cut and in a code fence. A return SHALL clear `implement.group`, `implement.sha`, `implement.branch`, `implement.pr`, `implement.base` and `implement.plan_summary`, and SHALL NOT set `implement.stopped`.

#### Scenario: A false premise on a Planned item
- **WHEN** the first step of a Planned item ends with a `premise` request and evidence
- **THEN** the Status is New, the comment holds the evidence in a code fence, `origin` has no branch for the item, and the record has no `implement.stopped`

#### Scenario: A false premise on a Planned item after an earlier Job
- **WHEN** the first Job of a Planned item stopped after group 1, pushed the new branch and opened a draft, and the step of group 2 of the next Job ends with a `premise` request and evidence
- **THEN** the Status is New, `origin` has no branch for the item, the draft pull request is closed, and the record holds no `implement.base`

#### Scenario: A false premise on a Staged item after an earlier Job
- **WHEN** the first Job of a Staged item stopped after group 1 and pushed it, and the step of group 2 of the next Job ends with a `premise` request and evidence
- **THEN** the Status is New, `origin` holds the staged branch at the commit it had before the first Job, and `implement.group` and `implement.base` are cleared

#### Scenario: A premise request with no evidence
- **WHEN** the `premise` request has an empty `evidence`
- **THEN** the item is stopped as a question and its Status is Blocked

#### Scenario: Evidence that holds Markdown
- **WHEN** the evidence holds a line that starts with `#`
- **THEN** the comment holds the line inside the code fence, as text

### Requirement: A return withdraws the pushes of earlier Jobs first
`prepare` SHALL write `implement.base` once: the tip of the branch on `origin`, or `new`. Before a return to New, `publish` SHALL withdraw what earlier Jobs pushed, with a lease on the tip that `prepare` found: it SHALL push a sha base back when the tip differs, and for `new` SHALL delete the branch that `prepare` found and close the recorded draft. A withdraw that fails SHALL stop the item as Blocked and SHALL NOT return it.

#### Scenario: A person pushed after prepare
- **WHEN** a person pushes to the item branch after `prepare`, and a `premise` request with evidence follows
- **THEN** the lease of the withdraw fails, the item is Blocked and is not returned, and the push of the person stays on the branch

#### Scenario: A branch at its base
- **WHEN** no earlier Job pushed to the item branch, and a `premise` request with evidence follows
- **THEN** the withdraw pushes nothing, and the Status is New

### Requirement: A behavior group whose Adds line the branch tip defines returns the item
Before the job runs a behavior group, the job SHALL read the identifiers of the `Adds:` line of the group through `TaskGroup.added_names` of `src/devops_cli/roadmap/step_files.py`, and SHALL return the item to New with the definition line when the branch tip defines one of them. The job SHALL use no rule of a task text. The job SHALL read the kind of the group from `TaskGroup.is_behavior` of `src/devops_cli/roadmap/step_files.py`, and a group of another kind SHALL run with no check.

#### Scenario: A task adds a guard that the base already runs
- **WHEN** A behavior group holds an `Adds:` line with `_delivery_title`, and the branch tip defines `_delivery_title`
- **THEN** The job runs no group step, writes no group file, makes no group commit, and comments the definition line with the return to New.

#### Scenario: A task adds a guard that the base lacks
- **WHEN** A behavior group holds an `Adds:` line with `_missing_guard`, and the branch tip defines no `_missing_guard`
- **THEN** The job runs the group and commits the file that the group writes.

#### Scenario: A task names a defined guard and the group has no Adds line
- **WHEN** A behavior group task says to add a check beside the guard `_delivery_title`, which the branch tip defines, and the group holds no `Adds:` line
- **THEN** The job returns no item to New and runs the group.

#### Scenario: A group that is not behavior adds a defined name
- **WHEN** A group whose kind is not behavior names the guard `_delivery_title`, which the branch tip defines, and holds no `Adds:` line
- **THEN** The job returns no item to New and runs the group.

#### Scenario: The guard premise fails after an earlier Job
- **WHEN** an earlier Job passed groups 1 and 2 and pushed them at its stop, and the `Adds:` line of a behavior group 3 names a guard that the branch tip defines
- **THEN** the job runs no step for group 3, `publish` withdraws the pushes of the earlier Job as for a `premise` request, and returns the item to New

### Requirement: A conflict stop of the rebase names the conflicted files
When the rebase of the agent phase stops the item on a conflict, the job SHALL read the unmerged files with `git diff --name-only --diff-filter=U` before it aborts the rebase. The action left SHALL be `wait`, with no fix round, until #6640. The stop comment SHALL name each file, `implement.conflict` SHALL hold them, and the next Job SHALL clear it in its first record write. The job SHALL mask each path, list at most `CONST_ROADMAP_IMPLEMENT_REASON_PATHS` paths, and state the number left out.

#### Scenario: A conflict at the start of a run
- **WHEN** the staged branch conflicts with the default branch in a real git repository when the job rebases at the start of the run
- **THEN** the item stops with the class `conflict` and the action left `wait`, and the comment names each conflicted file

#### Scenario: A settle that fails
- **WHEN** a git command of the settle of a generated document fails
- **THEN** the agent phase aborts the rebase, the item stops with the class `conflict`, and `publish` pushes no tree of a half-done rebase

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

## REMOVED Requirements

### Requirement: A false premise returns the item to New
**Reason**: The agent phase ends the run, and `publish` withdraws what earlier Jobs pushed and returns the item (#3702).
**Migration**: The requirement "A false premise returns the item to New after the withdraw" replaces it.

### Requirement: A return withdraws the checkpoints first
**Reason**: No run makes a checkpoint; an earlier Job pushes at its stop, in `publish` (#3702).
**Migration**: The requirement "A return withdraws the pushes of earlier Jobs first" replaces it.

### Requirement: The job checks the premise of a behavior group at the branch tip
**Reason**: No run makes a checkpoint, so the scenario after a checkpoint changes (#3702).
**Migration**: The requirement "A behavior group whose Adds line the branch tip defines returns the item" replaces it.

### Requirement: A conflict stop names the conflicted files
**Reason**: The agent phase rebases once, at the start, and no rebase comes before the push (#3702).
**Migration**: The requirement "A conflict stop of the rebase names the conflicted files" replaces it.
