## ADDED Requirements

### Requirement: Ignored data files keep a worktree
`devops repos worktrees prune` SHALL refuse a worktree that holds ignored data files: files that `.gitignore` hides and that no regenerable path holds. It SHALL name the number of those files in the reason and SHALL read no pull request for the worktree. When git cannot list the ignored files, prune SHALL refuse the worktree with a reason that says the count is unknown.

#### Scenario: A scratch note
- **WHEN** a clean worktree under the managed folder at a merged head holds `.venv/x`, `src/pkg/__pycache__/m.pyc`, `.pytest_cache/v` and `.data/agent/scratch/note.md`
- **THEN** the preview refuses the worktree with the reason `holds 1 ignored data file`, and `--confirm` leaves the directory and the note in place

#### Scenario: A local environment file
- **WHEN** a clean worktree under the managed folder at a merged head holds `.env.local`, which `.gitignore` hides
- **THEN** `prune --confirm` refuses the worktree and the file still exists

#### Scenario: Git cannot list the ignored files
- **WHEN** the `.git` file of a worktree under the managed folder is broken
- **THEN** `prune --confirm` refuses the worktree with a reason that names `git ls-files`, and GitHub receives no request for it

### Requirement: Regenerable paths hold no data
The count of ignored data files SHALL leave out the regenerable paths: the caches and build outputs that a command makes again. They are `.venv`, `dist`, `build`, `htmlcov`, `.data/cache`, `.data/rag` and the coverage outputs under `.data/`, and each `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.hypothesis`, `node_modules` and `.coverage*` path at any depth. An empty directory holds no data file.

#### Scenario: Only caches
- **WHEN** a clean worktree under the managed folder at a merged head holds only `.venv/x`, `src/pkg/__pycache__/m.pyc` and `.pytest_cache/v`
- **THEN** `prune --confirm` removes it and reports it as removed

#### Scenario: Only the data cache
- **WHEN** a clean worktree under the managed folder at a merged head holds only `.data/cache/x`
- **THEN** `prune --confirm` removes it

### Requirement: A worktree outside the managed folder stays
`devops repos worktrees prune` SHALL refuse a worktree whose path is not under the managed folder, also when its directory is missing, SHALL name that folder in the reason, and SHALL read no pull request for it. The dry run SHALL list no request for it.

#### Scenario: A worktree in the folder of another tool
- **WHEN** a clean worktree at a merged head is in a folder outside the managed folder
- **THEN** the preview refuses the worktree with a reason that names the managed folder, `--confirm` leaves the directory in place, and GitHub receives no request for its tip

#### Scenario: A record whose directory is missing
- **WHEN** the directory of a worktree outside the managed folder is missing
- **THEN** `prune --confirm` refuses the worktree with a reason that names the managed folder, and `git worktree list` still lists the record

#### Scenario: Dry run
- **WHEN** the user runs `prune --dry-run` with a worktree outside the managed folder
- **THEN** the output refuses that worktree with a reason that names the managed folder and lists no request for its tip

### Requirement: Prune and the reclaim share one scope rule
`devops repos worktrees prune` and the reclaim of `devops repos worktrees add` MUST take the scope refusal from one function, `scope_refusal`, so that the two rules cannot drift. The function SHALL check the folder first and the ignored data files second.

#### Scenario: Both callers give the shared reason
- **WHEN** a test runs prune and the reclaim on one worktree outside the managed folder and on one worktree under it that holds one ignored data file
- **THEN** prune and the reclaim give for each worktree the reason that `scope_refusal` returns

### Requirement: Force removes a worktree that the scope refuses
`devops repos worktrees prune --confirm --force` SHALL remove a worktree that the scope refuses: a worktree outside the managed folder and a worktree that holds ignored data files. It SHALL keep the main worktree and the worktree that holds the current directory.

#### Scenario: Force removes a worktree with a scratch note
- **WHEN** the current directory is inside one worktree, and the user runs prune with `--confirm --force` on another worktree that holds `.data/agent/scratch/note.md`
- **THEN** the worktree with the note is gone, and the main worktree and the worktree of the current directory stay

### Requirement: The prune help states the scope
The help text of `devops repos worktrees prune` MUST state that the command removes only the worktrees under the managed folder that hold no ignored data file, that it keeps the regenerable caches out of the count, and that `--force` removes every worktree but the main worktree and the worktree that holds the current directory.

#### Scenario: The help names the folder, the data refusal and force
- **WHEN** a test runs `devops repos worktrees prune --help`
- **THEN** the output names the managed folder, the ignored data files, the current directory and `--force`

## MODIFIED Requirements

### Requirement: A merged pull request makes a worktree removable
The system SHALL treat a worktree that the scope rule allows as removable only when GitHub reports a merged pull request whose head commit is the tip of the worktree, and SHALL keep every other worktree, whatever refs contain its tip.

#### Scenario: Squash-merged branch
- **WHEN** the tip of a clean, unlocked worktree under the managed folder that holds no ignored data file is the head of a merged pull request
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
