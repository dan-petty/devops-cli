## MODIFIED Requirements

### Requirement: A closed item loses its staged branch when only the App wrote to it
In each run the job SHALL look at the staged branch of each closed item whose record holds `stage.branch`. When every commit of the branch past `origin/<default branch>` has the identity of the session as its author, or is a clean merge, the job SHALL close the draft pull request and delete the branch. A clean merge is a merge commit with two parents whose tree is the tree that `git merge-tree --write-tree` gives for those parents. When any other commit exists, the job SHALL keep both and say so in the plan.

#### Scenario: Only the App wrote to the branch
- **WHEN** the item is closed and its staged branch holds one commit by the session identity
- **THEN** the job closes the draft and deletes the branch

#### Scenario: A person added a commit
- **WHEN** the item is closed and its staged branch holds a commit by another author
- **THEN** the job keeps the branch and the draft, and the plan says why

#### Scenario: A person added only a clean merge
- **WHEN** the item is closed and its staged branch holds one commit by the session identity and a clean merge by another author
- **THEN** the job closes the draft and deletes the branch
