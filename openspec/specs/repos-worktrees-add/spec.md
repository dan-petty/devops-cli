# repos-worktrees-add Specification

## Purpose
How `devops repos worktrees add` creates the worktree of an issue in one place and one branch form, how it refuses an issue that a worktree or a pushed branch already holds, and how `worktrees status` shows the issue of each worktree.

## Requirements

### Requirement: A new worktree starts at the fetched main
When `origin` has no branch for the issue, `add <issue> --type <type> --slug <slug>` SHALL fetch `origin/main` and create the worktree `w-<issue>` under the agent worktrees directory, on the new branch `<type>/<issue>-<slug>` at the tip of the fetched `origin/main`. The branch SHALL have no upstream. The command SHALL print the path and the branch. It SHALL require `--type` and `--slug` in that case.

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

#### Scenario: No type and no slug without a branch
- **WHEN** `origin` has no branch for issue 2337 and the user runs `add 2337`
- **THEN** the command exits 1, the error names `--type` and `--slug`, and nothing is created

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
The command SHALL read the branches of `origin` and refuse issue N, with exit status 1 and no change, when `origin` has a branch of the form `<type>/N-<slug>` that it does not take over. The error SHALL name that branch. A local branch that no worktree has checked out SHALL hold nothing. A branch with no commit past `origin/main` SHALL be refused, and so SHALL any branch when `service.github_app.slug` is not set; in both cases the error names the branch.

#### Scenario: A branch of origin
- **WHEN** `origin` has the branch `fix/2337-other` with a commit past `origin/main` by a person, and the user runs `add 2337 --type feat --slug worktrees-add`
- **THEN** the command exits 1 and the error names `origin/fix/2337-other`
- **AND** no worktree or branch is created

#### Scenario: A branch of origin with no commit past main
- **WHEN** `origin` has the branch `fix/2337-other` at the tip of `origin/main` and the user runs `add 2337 --type fix --slug other`
- **THEN** the command exits 1 and the error names `origin/fix/2337-other`
- **AND** no worktree is created

#### Scenario: The App slug is not set
- **WHEN** `service.github_app.slug` is not set, `origin` has a branch for issue 2337 with commits, and the user runs `add 2337`
- **THEN** the command exits 1, the error names the branch and `service.github_app.slug`, and nothing is created

#### Scenario: A local branch with no worktree
- **WHEN** the clone has the local branch `feat/2337-old` with no worktree, and `origin` has no branch for issue 2337
- **THEN** `add 2337 --type feat --slug worktrees-add` creates the worktree

### Requirement: A missing origin is named
The command SHALL refuse with exit status 1 and no change when the repository has no remote named `origin`, and the error SHALL name `origin`.

#### Scenario: No origin
- **WHEN** the repository has no remote named `origin` and the user runs `add 2337 --type feat --slug x`
- **THEN** the command exits 1, the error names `origin` and nothing is created

### Requirement: A dry run reads nothing from origin
`add --dry-run` SHALL make no request to `origin` and change nothing. It SHALL check the local worktrees, as the real run does, and print the `git ls-remote`, `git fetch`, `git log` and `git worktree add` commands that the real run can run, in order. The `git log` command reads the authors of the commits of the pushed branch past `origin/main`. A dry run SHALL need `--type` and `--slug`, and without one SHALL exit 2.

#### Scenario: Dry run
- **WHEN** the user runs `add 2337 --type feat --slug worktrees-add --dry-run`
- **THEN** the output lists the four commands and no worktree or branch is created

#### Scenario: Dry run of a held issue
- **WHEN** a worktree has the branch `fix/2337-other` and the user runs `add 2337 --type feat --slug x --dry-run`
- **THEN** the command exits 1 and the error names that worktree

#### Scenario: Dry run without a slug
- **WHEN** the user runs `add 2337 --type feat --dry-run`
- **THEN** the command exits 2 and names `--slug`

### Requirement: Status shows the issue of each worktree
`worktrees status` SHALL show the issue number of each worktree, read from its branch when the branch has the form `<type>/<issue>-<slug>`, as the column `Issue` of the table and the field `issue` of the JSON. The value SHALL be null in the JSON, and empty in the table, for any other branch, for a detached head and for the main worktree.

#### Scenario: A worktree of an issue
- **WHEN** a worktree has the branch `fix/2337-other`
- **THEN** `status --json` gives the issue 2337 for it

#### Scenario: A worktree with another branch
- **WHEN** a worktree has the branch `main` or a detached head
- **THEN** `status --json` gives a null issue for it

### Requirement: A run reclaims the worktrees of merged work first
`devops repos worktrees add` SHALL remove each worktree that `devops repos worktrees prune --confirm` removes before it checks who holds the issue, and SHALL name each removed worktree with the size of its directory. The JSON report SHALL list them in `reclaimed`. A worktree that a run in parallel already removed is not a failed reclaim: the run SHALL report it as removed and say nothing of a failed reclaim. `--no-reclaim` SHALL skip the step and read no pull request.

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

#### Scenario: A run in parallel removes a worktree first
- **WHEN** a run in parallel removes a merged worktree before `add` removes it, so `git worktree remove` of it fails
- **THEN** `add` reports the worktree as removed, creates the new worktree, and says nothing of a failed reclaim

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

### Requirement: A staged branch is taken over
When `origin` has the branch `<type>/N-<slug>` for issue N, and every commit of it past `origin/main` has the author `<service.github_app.slug>[bot]`, `add N` SHALL create the worktree `w-N` on that branch, with `origin/<branch>` as its upstream. The branch SHALL have at least one such commit. The output and the JSON report SHALL say that the command took over a staged branch, and SHALL give the number of commits. The same rule SHALL take over the App's commits of a stopped implement run.

#### Scenario: A branch with only the App's commits
- **WHEN** `origin` has `feat/2657-staged` with two commits by `devops-roadmap[bot]` past `origin/main`, `service.github_app.slug` is `devops-roadmap`, and the user runs `add 2657`
- **THEN** the directory `w-2657` exists with `feat/2657-staged` checked out at the tip of the pushed branch
- **AND** the upstream of that branch is `origin/feat/2657-staged`
- **AND** the output and the JSON report (`status` `took over`, `commits` 2) say that the command took over a staged branch with 2 commits

#### Scenario: A stopped implement run
- **WHEN** the pushed branch has three commits by the App: the staging commit and two code commits of a stopped run
- **THEN** `add` takes the branch over and the report gives `commits` 3

### Requirement: A commit by another author refuses the takeover
When one commit of the pushed branch past `origin/main` has an author other than the App's bot login, `add` SHALL exit 1, change nothing, and name the branch and that author.

#### Scenario: One commit by a person
- **WHEN** `origin` has `feat/2657-staged` with a commit by the App and a commit by `Jane Doe`, and the user runs `add 2657`
- **THEN** the command exits 1 and the error names `origin/feat/2657-staged` and `Jane Doe`
- **AND** no worktree or local branch is created

### Requirement: A staged branch gives the type and the slug
When `origin` has a branch for the issue, `add` SHALL take `--type` and `--slug` from it, so both are optional. A `--type` or `--slug` that differs from the branch SHALL be an error with exit status 1 that names the branch and changes nothing.

#### Scenario: Options left out
- **WHEN** `origin` has a staged branch `feat/2657-staged` and the user runs `add 2657`
- **THEN** the worktree is on `feat/2657-staged`

#### Scenario: Options that match
- **WHEN** the user runs `add 2657 --type feat --slug staged` for that branch
- **THEN** the worktree is on `feat/2657-staged`

#### Scenario: A slug that differs
- **WHEN** the user runs `add 2657 --type feat --slug other` for that branch
- **THEN** the command exits 1 and the error names `origin/feat/2657-staged`
- **AND** no worktree is created

#### Scenario: A type that differs
- **WHEN** the user runs `add 2657 --type fix --slug staged` for that branch
- **THEN** the command exits 1 and the error names `origin/feat/2657-staged`

### Requirement: A stray local branch that origin holds is cleared
Before the command creates the worktree on the branch `<type>/N-<slug>`, in a new worktree or in a takeover, it SHALL look for a local branch of that name that no worktree uses. When `origin` holds every commit of that branch, the command SHALL delete the branch, log one line that names the branch and its commit, and create the worktree.

#### Scenario: A stray branch at the tip of main
- **WHEN** the clone has the local branch `feat/2337-worktrees-add` at the tip of `origin/main` with no worktree, `origin` has no branch for issue 2337, and the user runs `add 2337 --type feat --slug worktrees-add`
- **THEN** the command exits 0 and the worktree `w-2337` is on `feat/2337-worktrees-add`
- **AND** the log has one line that names the branch and its commit

#### Scenario: A stray branch whose commits origin holds
- **WHEN** the local branch has a commit, `origin` has the same commit on a branch of another issue, and the user runs the same command
- **THEN** the command deletes the stray branch and creates the worktree

#### Scenario: A pushed branch and a stray local branch
- **WHEN** `origin` has the staged branch `feat/2657-staged` with a commit by the App, the clone has a local branch of the same name at the tip of `origin/main` with no worktree, and the user runs `add 2657`
- **THEN** the local branch is deleted and the worktree is created on the pushed branch with `origin/feat/2657-staged` as its upstream

#### Scenario: A pushed branch of a person and a stray local branch
- **WHEN** `origin` has the branch `feat/2657-staged` with a commit by a person, the clone has a local branch of the same name at the tip of `origin/main` with no worktree, and the user runs `add 2657`
- **THEN** the command exits 1 with the error about the author, and the local branch stays

#### Scenario: A dry run
- **WHEN** the clone has a stray local branch of the new name and the user runs `add 2337 --type feat --slug worktrees-add --dry-run`
- **THEN** the command deletes nothing and its output says that a real run can delete a stray branch

### Requirement: A stray local branch with a commit that origin lacks is kept and named
When the local branch of the new name has a commit that `origin` does not hold, the command SHALL exit 1 with no change. The error SHALL name the branch and the number of those commits. The command SHALL never delete such a branch.

#### Scenario: A stray branch with a commit of its own
- **WHEN** the local branch `feat/2337-worktrees-add` has one commit that `origin` does not hold, and the user runs `add 2337 --type feat --slug worktrees-add`
- **THEN** the command exits 1 and the error names `feat/2337-worktrees-add` and one commit
- **AND** the branch still has its commit and no worktree is created

#### Scenario: A stray branch of the pushed issue with its own commit
- **WHEN** `origin` has the staged branch `feat/2657-staged`, the clone has a local branch of the same name with a commit that `origin` does not hold, and the user runs `add 2657`
- **THEN** the command exits 1, the error names the branch and one commit, and the branch keeps its commit

### Requirement: Only a live ref holds a commit for origin
`origin` SHALL hold a commit when `origin/main` reaches it, or when a remote-tracking ref reaches it that is at the tip which `git ls-remote --heads origin` lists for the same branch. A stale remote-tracking ref, for a branch that `origin` deleted or that a push rewrote, SHALL hold nothing. The command SHALL read the stray branch as `refs/heads/<branch>`, so a tag of the same name does not stand in for it.

#### Scenario: A tag of the same name
- **WHEN** the local branch has a commit that `origin` does not hold, a tag has the name of the branch, and the user runs the same command
- **THEN** the command exits 1 and the branch keeps its commit

#### Scenario: A stale remote-tracking ref
- **WHEN** the commit of the local branch is reached only by a remote-tracking ref of a branch that `origin` deleted, and the user runs the same command
- **THEN** the command exits 1 and the branch keeps its commit

### Requirement: The stage and implement jobs leave out an item with such a branch
The stage job and the implement job SHALL read a stray local branch of the new name before they pick an item. When it has a commit that `origin` does not hold, they SHALL leave the item out. The reason SHALL name the branch and the number of those commits. When `origin` holds all its commits, they SHALL pick the item, and `add` then deletes the branch.

#### Scenario: A stray branch with a commit of its own
- **WHEN** a Ready item has the title `fix(roadmap): the job drops a comment` and the clone has the local branch `fix/1-the-job-drops-a-comment` with a commit that `origin` does not hold
- **THEN** the job leaves the item out with a reason that names the branch and one commit

#### Scenario: A stray branch at the tip of main
- **WHEN** the same local branch is at the tip of `origin/main`
- **THEN** the job picks the item
