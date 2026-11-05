## MODIFIED Requirements

### Requirement: The job leaves out an item and says why

The job SHALL leave out, with a reason in the plan, an item that the filter names and that is neither Ready nor Planned, is neither Staged nor Planned, holds `implement.stopped`, has an author that the jobs do not trust, is an item of a bot with no approval that holds (`roadmap-author-trust`), has a commit past the default branch by anyone but the App other than a clean merge, is held by a worktree, or whose pull request is not an open draft. A clean merge is a merge commit whose tree is the one that `git merge-tree --write-tree` gives for its two parents.

#### Scenario: An item that is not Staged
- **WHEN** a Ready P1 bug of low effort has no `stage.pr` in its record and no change folder on `origin/main`
- **THEN** the plan leaves it out with the reason that it is neither Staged nor Planned

#### Scenario: An item with a stop on record
- **WHEN** a Staged item holds `implement.stopped`
- **THEN** the plan leaves it out with the reason that names the stop and the comment `implement: retry`

#### Scenario: An item of a bot with no approval
- **WHEN** a Staged item of the Service App's bot has no approval of refine's review, or its body changed after the review
- **THEN** the plan leaves it out with the reason that no review approved its body as it is now

#### Scenario: A commit by another author
- **WHEN** the branch of a Staged item holds a commit whose author is not the App
- **THEN** the plan leaves the item out with the reason that names the author

#### Scenario: A clean merge by a person
- **WHEN** the branch of a Staged item holds a commit by the App and a merge commit by a person whose tree is the tree of the clean merge of its parents
- **THEN** the plan does not leave the item out for that merge commit

#### Scenario: A merge by a person that changes a file
- **WHEN** the branch of a Staged item holds a merge commit by a person whose tree differs from the tree of the clean merge of its parents, because the merge changed a file or resolved a conflict
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

#### Scenario: A closed Planned item
- **WHEN** `--item N` names a closed issue whose change folder is on `origin/main`
- **THEN** the plan leaves it out because it is closed

#### Scenario: The item of a Job that runs
- **WHEN** the Service set an item In Progress for the Job it made, and the Job plans the item with `--item`
- **THEN** the plan selects the item

#### Scenario: An item that is In Progress with no Job
- **WHEN** an item is In Progress and its record names no Job
- **THEN** the plan leaves it out with its Status
