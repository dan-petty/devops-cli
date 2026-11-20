# repos-worktrees-prune Specification

## Purpose
Defines which git worktrees `devops repos worktrees prune` removes, refuses and reports as failed, and how its preview, dry-run and confirm modes behave, so that prune never removes a worktree that is in use.

## Requirements

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

### Requirement: Local state protects a worktree
The system SHALL keep the main worktree, a locked worktree, a worktree with uncommitted paths and a worktree whose dirty state is unknown, and SHALL NOT read GitHub for them. The scope refusal comes before the lock and the dirty state: a locked or dirty worktree outside the managed folder, or one that holds ignored data files, gets the reason of the scope. The count of uncommitted paths SHALL include the untracked files also when the git configuration sets `status.showUntrackedFiles` to `no`.

#### Scenario: Locked worktree
- **WHEN** a worktree under the managed folder that holds no ignored data file is locked
- **THEN** `prune --confirm` keeps it and reports the lock reason

#### Scenario: Dirty state unknown
- **WHEN** `git status` fails in a worktree
- **THEN** `worktrees status` shows its dirty count as unknown and `prune --confirm` keeps it

#### Scenario: Untracked files that the git configuration hides
- **WHEN** the git configuration sets `status.showUntrackedFiles` to `no`, and a clean worktree under the managed folder at a merged head holds the untracked file `untracked-notes.md`
- **THEN** `prune --confirm` keeps the worktree with the reason `dirty (1 uncommitted path)`, the file still exists, and GitHub receives no request for it

### Requirement: Remove only on confirm
The system SHALL remove a worktree only when `--confirm` is given. Without it, `prune` SHALL read GitHub, list the worktrees that it would remove and the ones it keeps, and change nothing. `--dry-run` SHALL make no external request and SHALL print the requests that the run would make. `--dry-run` with `--confirm` SHALL be refused.

#### Scenario: Preview
- **WHEN** the user runs `devops repos worktrees prune` with a removable worktree
- **THEN** the output says the worktree would be removed and the directory still exists

#### Scenario: Dry run
- **WHEN** the user runs `devops repos worktrees prune --dry-run`
- **THEN** GitHub receives no request and the output lists the request for each worktree that needs one

#### Scenario: Dry run with confirm
- **WHEN** the user runs `devops repos worktrees prune --dry-run --confirm`
- **THEN** the command exits 1 and removes nothing

### Requirement: A failed removal is reported
The system SHALL report a worktree as failed, with the message of git, when `git worktree remove` fails, SHALL keep its directory, and SHALL exit 1. A worktree that a run in parallel already removed is not a failed removal: the system SHALL report it as removed and count it as done, and the command SHALL exit 0.

#### Scenario: Forced removal of a locked worktree
- **WHEN** the user runs `devops repos worktrees prune --force --confirm` and a worktree is locked
- **THEN** the output reports the worktree as failed, its directory still exists and the command exits 1

#### Scenario: A run in parallel removes a worktree first
- **WHEN** a run in parallel removes a merged worktree before this run removes it, so `git worktree remove` of it fails
- **THEN** the output reports the worktree as removed, not as a failed removal

### Requirement: The worktree of the current directory stays
`prune` SHALL keep the worktree that holds the current directory, also under `--force`, report it as refused with the reason "current directory", and read no pull request for it.

#### Scenario: Prune from inside a merged worktree
- **WHEN** the current directory is inside a clean worktree whose tip heads a merged pull request, and the user runs `prune --confirm`
- **THEN** the worktree is kept and reported as the current directory
- **AND** GitHub receives no request for its tip

#### Scenario: Forced prune from inside a worktree
- **WHEN** the current directory is inside a worktree and the user runs `prune --force --confirm`
- **THEN** that worktree is kept and the other worktrees are removed

#### Scenario: Prune from another directory
- **WHEN** the same merged worktree exists and the current directory is outside it
- **THEN** `prune --confirm` removes it

### Requirement: A removable worktree reports its size
For each worktree that `prune` removes or would remove, the report SHALL give the size of its directory in bytes as `size_bytes`, and the table SHALL show the size beside the worktree and the total in its last line. A worktree whose directory is missing SHALL have no size. When a file in the directory is deleted during measurement, it SHALL contribute 0 bytes and SHALL NOT cause an error.

#### Scenario: Preview
- **WHEN** the user runs `prune` and a worktree of 1 MB would be removed
- **THEN** the line of that worktree and the last line give the size

#### Scenario: JSON
- **WHEN** the user runs `prune --confirm --json` and a worktree is removed
- **THEN** its item has `size_bytes` as the number of bytes of the directory before the removal

#### Scenario: Missing directory
- **WHEN** the directory of a worktree is gone and the user runs `prune --json`
- **THEN** its item has a null `size_bytes`

#### Scenario: File deleted during directory size walk
- **WHEN** a file in a measured directory is deleted before its size is read
- **THEN** the directory size returns the sum of the remaining files without raising an error

### Requirement: Ignored data files keep a worktree
`devops repos worktrees prune` SHALL refuse a worktree that holds ignored data files: files that `.gitignore` hides and that no regenerable path holds. It SHALL name the number of those files in the reason and SHALL read no pull request for the worktree. When git cannot list the ignored files, or warns while it lists them, prune SHALL refuse the worktree with a reason that says the count is unknown.

#### Scenario: A scratch note
- **WHEN** a clean worktree under the managed folder at a merged head holds `.venv/x`, `src/pkg/__pycache__/m.pyc`, `.pytest_cache/v` and `.data/agent/scratch/note.md`
- **THEN** the preview refuses the worktree with the reason `holds 1 ignored data file`, and `--confirm` leaves the directory and the note in place

#### Scenario: A local environment file
- **WHEN** a clean worktree under the managed folder at a merged head holds `.env.local`, which `.gitignore` hides
- **THEN** `prune --confirm` refuses the worktree and the file still exists

#### Scenario: Git cannot list the ignored files
- **WHEN** the `.git` file of a worktree under the managed folder is broken
- **THEN** `prune --confirm` refuses the worktree with a reason that names `git ls-files`, and GitHub receives no request for it

#### Scenario: Git cannot open a directory
- **WHEN** a worktree under the managed folder holds `.data/agent/scratch/dist/note.md`, and git has no permission to open `.data/agent/scratch/dist`
- **THEN** the scope rule refuses the worktree with a reason that names `git ls-files`

### Requirement: Prune checks the scope again before each removal
`devops repos worktrees prune --confirm` without `--force` SHALL ask the scope rule again right before it removes each worktree, and SHALL refuse a worktree that holds ignored data files at that time.

#### Scenario: A data file written after the decision
- **WHEN** a clean worktree under the managed folder at a merged head holds no data file when prune decides it, and an agent writes `.data/agent/scratch/note.md` in it while prune reads GitHub
- **THEN** `prune --confirm` refuses the worktree with the reason `holds 1 ignored data file`, and the note still exists

### Requirement: Regenerable paths hold no data
The count of ignored data files SHALL leave out the regenerable paths: the caches and build outputs that a command makes again. They are `.venv`, `dist`, `build`, `htmlcov`, `.data/cache`, `.data/rag`, the coverage outputs under `.data/`, `.coverage` and `.coverage.*` at the root and under `.data/`, and each `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.hypothesis` and `node_modules` path at any depth. An empty directory holds no data file.

#### Scenario: Only caches
- **WHEN** a clean worktree under the managed folder at a merged head holds only `.venv/x`, `src/pkg/__pycache__/m.pyc` and `.pytest_cache/v`
- **THEN** `prune --confirm` removes it and reports it as removed

#### Scenario: Only the data cache
- **WHEN** a clean worktree under the managed folder at a merged head holds only `.data/cache/x`
- **THEN** `prune --confirm` removes it

#### Scenario: A note named like coverage output
- **WHEN** a worktree under the managed folder holds `.coverage`, `.coverage.host.1`, `.data/.coverage`, `.data/.coverage.host.2` and `.data/agent/notes/.coverage-notes.md`, which `.gitignore` hides
- **THEN** the scope rule refuses the worktree with the reason `holds 1 ignored data file`

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
