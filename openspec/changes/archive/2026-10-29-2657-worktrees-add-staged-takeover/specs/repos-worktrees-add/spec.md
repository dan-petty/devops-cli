## MODIFIED Requirements

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

## ADDED Requirements

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
