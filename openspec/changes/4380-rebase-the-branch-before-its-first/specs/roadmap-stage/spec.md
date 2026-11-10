## MODIFIED Requirements

### Requirement: A staged branch starts at the staged commit
The job SHALL make the commit of a staged item on the staged commit of its round, so that the probe and the plan read one commit. Before it pushes, the job SHALL fetch the default branch and rebase the commit onto it, so that the pushed branch holds the default branch. A conflict SHALL abort the rebase and fail the item with nothing pushed. When the job takes over a pushed branch of the item, the branch SHALL keep its own tip.

#### Scenario: origin moves after the round read the default branch
- **WHEN** `origin/main` gains a commit after the round read it, and the job stages an item
- **THEN** the parent of the commit of the new branch is the tip of `origin/main`, and `main` has no commit that the new branch lacks

#### Scenario: The rebase conflicts
- **WHEN** `origin/main` gains a file with the path of a file of the plan
- **THEN** the job aborts the rebase, pushes no branch, opens no pull request, and records the item as failed
