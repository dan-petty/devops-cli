## ADDED Requirements

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
The job SHALL start the branch of a staged item at the staged commit of its round, so that the probe and the branch read one commit. When the job takes over a pushed branch of the item, the branch SHALL keep its own tip.

#### Scenario: origin moves after the round read the default branch
- **WHEN** `origin/main` gains a commit after the round read it, and the job stages an item
- **THEN** the parent of the commit of the new branch is the staged commit of the round, and the new commit of `origin/main` is not an ancestor of the new branch
