## MODIFIED Requirements

### Requirement: A staged item gets a branch and one commit
For each item the job SHALL make the branch `<type>/<issue>-<slug>`, where the type is the Conventional Commit type of the title and the slug comes from its summary. The job SHALL write the change folder `openspec/changes/<issue>-<slug>/` on the staged commit, and `publish` SHALL apply its patch to the tip of the default branch as one commit of the identity of the session and push it from a new repository with a lease (#6704).

#### Scenario: A Ready bug is staged
- **WHEN** the job runs with `--confirm` on a Ready P1 bug and the model gives a valid plan
- **THEN** the branch is pushed with one commit by the session identity, and the commit holds the change folder

#### Scenario: A push URL in the clone of the job
- **WHEN** the clone that the planner reads has a push URL that names another repository
- **THEN** the job pushes the branch to `origin` all the same, with one commit whose body is `Plans #<issue>.`

#### Scenario: A re-stage branch that moved past the recorded commit
- **WHEN** the App pushed a commit after `stage.sha`, and the new plan renders the files of `stage.sha` again
- **THEN** the item fails, and `origin` keeps the branch at that commit

#### Scenario: GitHub refuses the draft of a new plan
- **WHEN** the clone of the job has a push URL that names another repository, and GitHub refuses the draft
- **THEN** the job deletes the pushed branch from `origin`, and the item fails with the refusal

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
- **THEN** the git commands move the clone to the staged commit before the tracked files are read, and the agent work of each item writes its change folder on the staged commit

## ADDED Requirements

### Requirement: A staged plan goes onto the tip of the default branch
The job SHALL write the change folder of a staged item on the staged commit of its round, so that the probe and the plan read one commit. `publish` SHALL apply the patch of the change folder to the tip of the default branch as one commit, so that the pushed branch holds the default branch (#6704). A patch that the tip refuses SHALL fail the item with nothing pushed.

#### Scenario: origin moves after the round read the default branch
- **WHEN** `origin/main` gains a commit after the round read it, and the job stages an item
- **THEN** the parent of the commit of the new branch is the tip of `origin/main`, and `main` has no commit that the new branch lacks

#### Scenario: The patch does not apply to the tip
- **WHEN** `origin/main` gains a file with the path of a file of the plan after the round read it
- **THEN** the job pushes no branch, opens no pull request, and records the item as failed

## REMOVED Requirements

### Requirement: A staged branch starts at the staged commit
**Reason**: The job makes no commit on the staged commit and no rebase: `publish` applies the patch of the change folder to the tip of the default branch (#6704).
**Migration**: The requirement "A staged plan goes onto the tip of the default branch" replaces it.
