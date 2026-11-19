## ADDED Requirements

### Requirement: An ignored path keeps a worktree
`devops repos worktrees prune` SHALL refuse a clean worktree whose tip heads a merged pull request when the worktree holds paths that the repository ignores, and SHALL name the number of those paths in the reason.

#### Scenario: One ignored file in the managed folder
- **WHEN** a test runs prune on a clean worktree under the managed folder at a merged head that holds one file that the repository ignores
- **THEN** the preview keeps the worktree with the reason `holds 1 ignored path`, and `--confirm` leaves the directory in place

### Requirement: A worktree outside the managed folder stays
`devops repos worktrees prune` SHALL refuse a worktree whose path is not under the managed folder, and SHALL name that folder in the reason.

#### Scenario: Worktree in another tool's folder
- **WHEN** a test runs prune on a clean worktree at a merged head in a folder outside the managed folder
- **THEN** the preview keeps the worktree with a reason that names the managed folder, and `--confirm` leaves the directory in place

### Requirement: Prune and the reclaim share one scope decision
`devops repos worktrees prune` and the reclaim of `devops repos worktrees add` MUST take the scope refusal from one function, `scope_refusal`, so that the two rules cannot drift.

#### Scenario: Both callers return the shared refusal
- **WHEN** a test calls `scope_refusal`, the prune decision and the reclaim with one worktree outside the managed folder and with one worktree that holds one ignored path
- **THEN** each caller returns the same refusal text as the shared function for each worktree

### Requirement: Force removes a refused worktree
`devops repos worktrees prune --confirm --force` SHALL remove a worktree that the scope rules refuse, except the main worktree and the worktree that holds the current directory.

#### Scenario: Force removes a worktree with an ignored file
- **WHEN** a test runs prune with `--confirm --force` on a clean worktree at a merged head under the managed folder that holds one ignored file
- **THEN** the worktree directory is gone

### Requirement: The prune help states the scope
The help text of `devops repos worktrees prune` MUST state that the command removes only the worktrees under the managed folder that hold no ignored path, and that `--force` removes every worktree but the main one.

#### Scenario: Help output names the folder, the ignored refusal and force
- **WHEN** a test runs `devops repos worktrees prune --help`
- **THEN** the output names the managed folder, the ignored-path refusal and `--force`

## MODIFIED Requirements

### Requirement: A merged pull request makes a worktree removable
The system SHALL treat a worktree that the scope rules allow as removable only when GitHub reports a merged pull request whose head commit is the tip of the worktree, and SHALL keep every other worktree, whatever refs contain its tip.

#### Scenario: Squash-merged branch
- **WHEN** the tip of a clean, unlocked worktree under the managed folder that holds no ignored path is the head of a merged pull request
- **THEN** `prune --confirm` removes the worktree and reports it as removed

#### Scenario: New worktree
- **WHEN** a worktree has no commit of its own and no pull request has its tip as head
- **THEN** `prune --confirm` keeps the worktree and reports that no merged pull request has this commit as its head

#### Scenario: Pushed branch with an open pull request
- **WHEN** the branch of a worktree is pushed and its pull request is open
- **THEN** `prune --confirm` keeps the worktree

#### Scenario: New commit after the merge
- **WHEN** a worktree has a commit that is not the head of the merged pull request
- **THEN** `prune --confirm` keeps the worktree

#### Scenario: Commit that GitHub does not know
- **WHEN** GitHub answers HTTP 422 for the tip of a worktree
- **THEN** `prune --confirm` keeps the worktree and does not fail
