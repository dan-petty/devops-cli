# Spec Delta

## MODIFIED Requirements

### Requirement: The job takes a Staged or a Planned item that the filter names
A Staged item SHALL have a recorded branch on `origin` and an open draft pull request. The pair is `implement.branch` and `implement.pr`, else `stage.branch` and `stage.pr`. A Planned item SHALL have no recorded branch on `origin` and its change folder on `origin/<default branch>`. A branch on `origin` makes it Staged. The default filter SHALL be `status=ready`, `status=planned`, `priority=p0-critical`, `priority=p1-high`, `type=bug` and `effort=low`. `--limit` SHALL default to 1.

#### Scenario: The default filter
- **WHEN** the roadmap holds a Staged Ready P1 bug of low effort, a Staged Ready P1 bug of high effort, and a Staged Ready P3 bug of low effort
- **THEN** the plan selects the first item, and does not name the other two, which the filter does not name

#### Scenario: A plan on the default branch and a branch that is gone
- **WHEN** a Ready P1 bug of low effort has a record with a merged `stage.pr` and a `stage.branch` that is not on `origin`, and `origin/main` holds its change folder
- **THEN** the plan selects it as a Planned item, with the branch `fix/<issue>-<slug>` and no pull request, and the slug is the one of the change folder

#### Scenario: A plan on the default branch and a branch that is there
- **WHEN** the staged branch of the item is on `origin` with an open draft, and `origin/main` also holds the change folder
- **THEN** the plan selects the item with its staged branch and its pull request, as a Staged item

#### Scenario: Two Planned items
- **WHEN** two Ready P1 bugs of low effort have their change folders on `origin/main`, and the limit is 2
- **THEN** the plan selects both, the lower number first

#### Scenario: An item with the Status Planned
- **WHEN** a P1 bug of low effort has the Status Planned and its change folder is on `origin/main`
- **THEN** the plan selects it as a Planned item

### Requirement: The job leaves out an item and says why
The job SHALL leave out, with a reason in the plan, an item that the filter names and that is neither Ready nor Planned, is neither Staged nor Planned, holds `implement.stopped`, has an untrusted author, has a commit past the default branch by anyone but the App, is held by a worktree, or whose pull request is not an open draft. An item that is In Progress SHALL stay in the plan while its record names a Job that no round reported. It SHALL also leave out a Planned item with a branch of `origin` or a worktree that holds it, an archived change, no branch type, no branch name, no `tasks.md`, or no unticked task.

#### Scenario: An item that is not Staged
- **WHEN** a Ready P1 bug of low effort has no `stage.pr` in its record and no change folder on `origin/main`
- **THEN** the plan leaves it out with the reason that it is neither Staged nor Planned

#### Scenario: An item with a stop on record
- **WHEN** a Staged item holds `implement.stopped`
- **THEN** the plan leaves it out with the reason that names the stop and the comment `implement: retry`

#### Scenario: A commit by another author
- **WHEN** the branch of a Staged item holds a commit whose author is not the App
- **THEN** the plan leaves the item out with the reason that names the author

#### Scenario: The pull request is not an open draft
- **WHEN** the pull request of a Staged item is ready for review, or closed
- **THEN** the plan leaves the item out with the reason that its pull request is not an open draft

#### Scenario: A retry comment
- **WHEN** a Staged item holds `implement.stopped` and a comment `implement: retry` by the owner, made after the stop comment
- **THEN** the plan selects the item, and the run clears `implement.stopped` before the first step

#### Scenario: A retry comment by a stranger
- **WHEN** the comment `implement: retry` comes from a user who is not the owner, a member or a collaborator
- **THEN** the item stays left out

#### Scenario: A Planned item that another agent holds
- **WHEN** the change folder of a Ready item is on `origin/main` and `origin` holds a branch `fix/<issue>-other` for it, which is not its recorded branch
- **THEN** the plan leaves the item out with the reason of the held issue

#### Scenario: A Planned item whose change is archived
- **WHEN** `origin/main` holds only the archived folder of the item
- **THEN** the plan leaves the item out and says that its change is archived on `main`

#### Scenario: A Planned item whose change has no tasks.md
- **WHEN** the change folder of a Planned item on `origin/main` holds no `tasks.md`, and a second Planned item is valid
- **THEN** the plan leaves the first item out with a reason that names the folder and the error of git, and selects the second item

#### Scenario: A Planned item with every task ticked
- **WHEN** the `tasks.md` of the change folder on `origin/main` has no unticked task
- **THEN** the plan leaves the item out and says that every task is ticked

#### Scenario: A closed Planned item
- **WHEN** `--item N` names a closed issue whose change folder is on `origin/main`
- **THEN** the plan leaves it out because it is closed

#### Scenario: The item of a Job that runs
- **WHEN** the Service set an item In Progress for the Job it made, and the Job plans the item with `--item`
- **THEN** the plan selects the item

#### Scenario: An item that is In Progress with no Job
- **WHEN** an item is In Progress and its record names no Job
- **THEN** the plan leaves it out with its Status
