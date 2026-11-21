## ADDED Requirements

### Requirement: The agent phase rebases once and settles each stop
The agent phase SHALL rebase once, before the first step, onto the tip of the default branch that `prepare` recorded, when `prepare` chose a rebase. It SHALL skip only the archive commit of the item. At a stop on generated documents or `uv.lock` only, it SHALL take the side of the default branch by the stage of the index and make the files again. Another stop, or a settle that fails, SHALL abort the rebase and stop the item with the class `conflict`. The job SHALL NOT call `fix_rebase_conflict`.

#### Scenario: A main that moved
- **WHEN** `main` gains a commit before the Job starts
- **THEN** the pushed branch on `origin` holds that commit

#### Scenario: An archive commit that conflicts
- **WHEN** the branch holds an archive commit and `main` changes a spec that the archive changed
- **THEN** the rebase skips the archive commit, the run archives the change again, and the item reaches the draft

#### Scenario: A generated document that main deleted
- **WHEN** the branch changes a generated document, and `main` deletes it
- **THEN** the rebase deletes the document and goes on, and the item reaches the draft

#### Scenario: A conflict that no rule settles
- **WHEN** `main` changes a source file that the branch changed
- **THEN** the item stops with the class `conflict`, the comment names the conflicting path, and `origin` keeps the item branch as it was

### Requirement: The option skips the rebase of the agent phase
`devops roadmap implement` SHALL accept a `--no-rebase` option. With it, `prepare` records no rebase in the inputs of the agent phase, the agent phase makes no rebase, and the base of the patches is the tip of the pushed branch, or the tip of the default branch for a new branch. The agent phase SHALL take the choice of `prepare`, so its base and its patches agree.

#### Scenario: The option skips the rebase
- **WHEN** a runner Job runs `roadmap implement --repo <owner/name> --item 7 --confirm --no-rebase` in a real repository whose `origin/main` holds a commit that the branch lacks
- **THEN** the agent phase runs no `git rebase`, and `publish` puts the work of the run on the old tip of the branch with a lease on it

### Requirement: A publish that runs again keeps the draft of the run
`publish` SHALL record the draft of a new branch in `implement.pr` at once. A `publish` of the same run that runs again SHALL take the draft from the record and open no second draft. When GitHub refuses the draft, `publish` SHALL delete the branch only when the run made it: `prepare` found no branch.

#### Scenario: A publish that ended after the draft
- **WHEN** `publish` pushed the new branch and opened the draft, and its Job ended before the end of the run, and `publish` runs again
- **THEN** it takes the draft from `implement.pr`, opens no second draft and deletes no branch

### Requirement: The job records the summary of the plan once
`prepare` SHALL record the summary of the plan in `implement.plan_summary` once, and a later Job SHALL take it from the record, because a push of `publish` puts the plan inside a commit of the bot. A title with the summary of the plan that holds a closing keyword SHALL give way to the summary of the title of the issue, because a squash merge puts the title in the subject.

#### Scenario: A later Job of a Staged item
- **WHEN** the first Job of a Staged item stopped and pushed its work, and the next Job finishes the change
- **THEN** the title of the pull request is still the title with the summary of the plan

#### Scenario: A plan summary with a closing keyword
- **WHEN** the summary of the plan is `Fixes #4 in the job`
- **THEN** the title of the pull request is the title of the issue

## MODIFIED Requirements

### Requirement: The job commits the documentation and the archive, and pushes
After the last group the agent phase SHALL run `uv run devops docs generate` and commit its changes, then `uv run devops openspec archive <change>` and commit its changes, then run the scoped checks, each outside the agent shell. It SHALL write three patches: the work up to the archive commit, the archive commit alone, and the work after it. `publish` SHALL push one commit of the bot for each patch that changes a file, in that order. A stop SHALL first drop the files that no commit holds.

#### Scenario: Two groups
- **WHEN** a Staged low-effort P1 bug has a change with two unticked groups, and both steps pass
- **THEN** the branch on `origin` holds one commit of the bot with the work of the run and one commit of the bot with the archive, on the tip of the default branch

#### Scenario: A fix round after the archive
- **WHEN** a scoped check fails after the archive, and a fix round changes a file
- **THEN** the branch on `origin` holds three commits of the bot: the work, the archive and the fix, and a rebase onto a later `main` can skip the archive commit

#### Scenario: An archive that fails after it moved the change folder
- **WHEN** the archive moves the change folder and exits 1
- **THEN** the item stops, and the branch on `origin` holds the work of the groups and of the documentation, and no moved change folder

### Requirement: A Planned item gets a draft pull request at its first push
`publish` SHALL push the new branch of a Planned item with an empty lease, so the push fails when the branch exists, and SHALL open a draft pull request into the default branch at once. The first body SHALL hold the closing keyword of the delivered issue once (`Closes #<issue>`) and no other closing keyword, so a stop leaves a grounded draft. `publish` SHALL record the pull request. A stop whose run made no commit SHALL push nothing.

#### Scenario: A stop in the first group
- **WHEN** the step of group 1 reports stopped before any commit
- **THEN** `origin` holds no branch for the item, no pull request opened, the Status is Blocked, and `implement.stopped` is `group 1`

#### Scenario: A stop in the second group
- **WHEN** the step of group 2 reports stopped after group 1 passed
- **THEN** `origin` holds the new branch with the work of group 1, a draft pull request is open with a body that holds `Closes #<issue>` once, the job writes no later body to it, and the record holds its number

#### Scenario: A retry
- **WHEN** a comment `implement: retry` follows that stop
- **THEN** the plan selects the item with the recorded branch and pull request as a Staged item, and the run takes the branch over

#### Scenario: A draft that GitHub refuses
- **WHEN** GitHub refuses the draft pull request after the push
- **THEN** `publish` removes the branch from `origin` with a lease on its push, stops the item, and the record holds no pull request

### Requirement: The job skips a phase that passed at the same head
`publish` SHALL write `implement.published_sha` after each push, and `implement.checked_sha` after the push of a run that passed the scoped checks. An agent phase whose head equals `implement.checked_sha` SHALL run no scoped check. `publish` SHALL push no commit when the lease holds the new tree already. `prepare` SHALL clear `implement.published_sha`, and `publish` SHALL take it as the lease when it holds a value. The job SHALL clear both keys at the end of the draft and at a return to New.

#### Scenario: A second Job at a checked head
- **WHEN** a first Job pushes and is killed before the end of the run, and a second Job starts on the pushed branch
- **THEN** the agent phase of the second Job runs no scoped check, and `publish` pushes nothing

#### Scenario: A head that moved
- **WHEN** `implement.checked_sha` holds a sha that is not the head
- **THEN** the agent phase runs the scoped checks

## REMOVED Requirements

### Requirement: The job checkpoints each passed group on the item branch
**Reason**: The agent phase holds no GitHub credential, so no run pushes before `publish` (#3702).
**Migration**: None. A killed Job loses the groups of its run, and the next Job runs them again.

### Requirement: A Planned item gets its draft at the first checkpoint
**Reason**: No run makes a checkpoint (#3702). `publish` opens the draft at the first push.
**Migration**: None.

### Requirement: A failed checkpoint does not stop the run
**Reason**: No run makes a checkpoint (#3702).
**Migration**: None.

### Requirement: A conflicting checkpoint or stop push keeps the head on the item branch
**Reason**: The agent phase rebases once, before the first step, and `publish` makes no rebase (#3702).
**Migration**: None. A conflict stops the item before the first step, with nothing to push.

### Requirement: The option skips the fetch and the rebase
**Reason**: The agent phase makes no fetch, so the option skips only the rebase (#3702).
**Migration**: The requirement "The option skips the rebase of the agent phase" replaces it.

### Requirement: A push rebases the checkout onto the default branch
**Reason**: No run pushes before `publish`, and `publish` makes no rebase (#3702).
**Migration**: The requirement "The agent phase rebases once and settles each stop" replaces it.
