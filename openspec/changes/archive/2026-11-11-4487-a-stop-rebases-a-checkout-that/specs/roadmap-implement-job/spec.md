## MODIFIED Requirements

### Requirement: The job commits the documentation and the archive, and pushes
After the last group the job SHALL run `uv run devops docs generate --sync-readme` and commit its changes, then `uv run devops openspec archive <change>` and commit its changes, then rebase, run the scoped checks, then push. The job SHALL run each of these outside the agent shell. When one of them fails, the job SHALL drop the files that no commit holds before the push of the stop, so the rebase of that push finds a clean checkout.

#### Scenario: Two groups
- **WHEN** a Staged low-effort P1 bug has a change with two unticked groups, and both steps pass
- **THEN** the branch holds the commit of the stage job, one commit for each group, one commit for the documentation and one commit for the archive, in that order, and `origin` holds the same branch

#### Scenario: An archive that fails after it moved the change folder
- **WHEN** `main` gains a commit, and then the archive moves the change folder and exits 1
- **THEN** the item stops, `origin` holds the commit of the group and the commit of the documentation, and `main` has no commit that the branch on `origin` lacks
