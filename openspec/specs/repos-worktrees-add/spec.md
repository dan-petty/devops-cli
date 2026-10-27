# repos-worktrees-add Specification

## Purpose
How `devops repos worktrees add` creates the worktree of an issue in one place and one branch form, how it refuses an issue that a worktree or a pushed branch already holds, and how `worktrees status` shows the issue of each worktree.

## Requirements

### Requirement: A new worktree starts at the fetched main
`devops repos worktrees add <issue> --type <type> --slug <slug>` SHALL fetch `origin/main` and create the worktree `w-<issue>` under the agent worktrees directory of the data directory, on the new branch `<type>/<issue>-<slug>` at the tip of the fetched `origin/main`. The branch SHALL have no upstream. The command SHALL print the path and the branch.

#### Scenario: Create the worktree
- **WHEN** the user runs `add 2337 --type feat --slug worktrees-add` and no worktree or branch holds issue 2337
- **THEN** the directory `w-2337` exists under the agent worktrees directory with the branch `feat/2337-worktrees-add` checked out
- **AND** the output names the path and the branch

#### Scenario: The base is the fetched tip
- **WHEN** `origin/main` has a commit that the local clone has not fetched, and the user runs `add`
- **THEN** the tip of the new worktree is that commit

#### Scenario: No upstream
- **WHEN** the worktree is created
- **THEN** its branch has no upstream branch

### Requirement: The branch form is checked first
The command SHALL accept as `--type` only a type of `release-please-config.json`, and as `--slug` only lowercase letters and digits joined by single hyphens. It SHALL refuse any other value as a usage error, with exit status 2, before it runs a git command that changes the repository or reads `origin`.

#### Scenario: Unknown type
- **WHEN** the user runs `add 2337 --type feature --slug x`
- **THEN** the command exits 2, names the allowed types and creates nothing

#### Scenario: Slug with a capital letter, an underscore or a leading hyphen
- **WHEN** the user runs `add 2337 --type feat --slug Bad_Slug`
- **THEN** the command exits 2, names the allowed form and creates nothing

#### Scenario: A bad value in a repository with no origin
- **WHEN** the repository has no remote named `origin` and the user runs `add 2337 --type feature --slug x`
- **THEN** the error is about the type and not about `origin`

### Requirement: A worktree holds its issue
The command SHALL refuse issue N, with exit status 1 and no change, when a worktree of the repository has a branch of the form `<type>/N-<slug>`, whatever its type and slug, or when the directory `w-N` already exists. The error SHALL name the holder with its path and its branch.

#### Scenario: Another slug of the same issue
- **WHEN** a worktree has the branch `fix/2337-other` and the user runs `add 2337 --type feat --slug worktrees-add`
- **THEN** the command exits 1 and the error names the path and the branch `fix/2337-other`

#### Scenario: The standard directory exists
- **WHEN** the directory `w-2337` exists and the user runs `add 2337`
- **THEN** the command exits 1 and the error names that directory

#### Scenario: A longer issue number is no claim
- **WHEN** a worktree has the branch `feat/23370-x` and the user runs `add 2337`
- **THEN** the command creates the worktree

### Requirement: A pushed branch holds its issue
The command SHALL read the branches of `origin` and refuse issue N, with exit status 1 and no change, when `origin` has a branch of the form `<type>/N-<slug>`. The error SHALL name that branch. A local branch that no worktree has checked out SHALL hold nothing.

#### Scenario: A branch of origin
- **WHEN** `origin` has the branch `fix/2337-other` and the user runs `add 2337 --type feat --slug worktrees-add`
- **THEN** the command exits 1 and the error names `origin/fix/2337-other`
- **AND** no worktree or branch is created

#### Scenario: A local branch with no worktree
- **WHEN** the clone has the local branch `feat/2337-old` with no worktree, and `origin` has no branch for issue 2337
- **THEN** `add 2337 --type feat --slug worktrees-add` creates the worktree

### Requirement: A missing origin is named
The command SHALL refuse with exit status 1 and no change when the repository has no remote named `origin`, and the error SHALL name `origin`.

#### Scenario: No origin
- **WHEN** the repository has no remote named `origin` and the user runs `add 2337 --type feat --slug x`
- **THEN** the command exits 1, the error names `origin` and nothing is created

### Requirement: A dry run reads nothing from origin
`add --dry-run` SHALL make no request to `origin` and change nothing. It SHALL check the local worktrees, as the real run does, and print the `git ls-remote`, `git fetch` and `git worktree add` commands that the real run would run, in order.

#### Scenario: Dry run
- **WHEN** the user runs `add 2337 --type feat --slug worktrees-add --dry-run`
- **THEN** the output lists the three commands and no worktree or branch is created

#### Scenario: Dry run of a held issue
- **WHEN** a worktree has the branch `fix/2337-other` and the user runs `add 2337 --type feat --slug x --dry-run`
- **THEN** the command exits 1 and the error names that worktree

### Requirement: Status shows the issue of each worktree
`worktrees status` SHALL show the issue number of each worktree, read from its branch when the branch has the form `<type>/<issue>-<slug>`, as the column `Issue` of the table and the field `issue` of the JSON. The value SHALL be null in the JSON, and empty in the table, for any other branch, for a detached head and for the main worktree.

#### Scenario: A worktree of an issue
- **WHEN** a worktree has the branch `fix/2337-other`
- **THEN** `status --json` gives the issue 2337 for it

#### Scenario: A worktree with another branch
- **WHEN** a worktree has the branch `main` or a detached head
- **THEN** `status --json` gives a null issue for it

### Requirement: A run reclaims the worktrees of merged work first
`devops repos worktrees add` SHALL remove each worktree that `devops repos worktrees prune --confirm` removes before it checks who holds the issue, and SHALL name each removed worktree with the size of its directory. The JSON report SHALL list them in `reclaimed`. `--no-reclaim` SHALL skip the step and read no pull request.

#### Scenario: A merged worktree is removed
- **WHEN** a clean, unlocked worktree has a tip that is the head of a merged pull request, and the user runs `add 2345 --type feat --slug next`
- **THEN** the directory of that worktree no longer exists and the output names it with its size
- **AND** the worktree `w-2345` is created

#### Scenario: A merged worktree no longer holds its issue
- **WHEN** the merged worktree has the branch `chore/2344-old`, and the user runs `add 2344 --type chore --slug again`
- **THEN** the old worktree is removed and `w-2344` is created

#### Scenario: Other worktrees stay
- **WHEN** a worktree is dirty, locked, or has a tip that no merged pull request heads
- **THEN** `add` keeps it

#### Scenario: Reclaim skipped
- **WHEN** the user runs `add 2344 --type chore --slug again --no-reclaim` and the merged worktree of issue 2344 exists
- **THEN** the command exits 1 and names that worktree as the holder
- **AND** GitHub receives no request

### Requirement: A failed reclaim does not stop the run
When the pull requests of the worktrees cannot be read, `add` SHALL say why once, remove nothing, and go on to create the worktree. The JSON report SHALL hold the reason in `reclaim_error`.

#### Scenario: GitHub answers an error
- **WHEN** GitHub answers an error for the tip of a worktree, and the user runs `add 2345 --type feat --slug next`
- **THEN** the command exits 0, says that the merged worktrees were not reclaimed and why, and creates `w-2345`
- **AND** no worktree is removed

### Requirement: A dry run plans the reclaim
`add --dry-run` SHALL list the GitHub requests that the reclaim would make, SHALL make no request, and SHALL remove nothing.

#### Scenario: Dry run with a worktree to check
- **WHEN** a clean, unlocked worktree exists and the user runs `add 2345 --type feat --slug next --dry-run`
- **THEN** the output lists the request for the pull requests of its tip
- **AND** GitHub receives no request and the worktree still exists
