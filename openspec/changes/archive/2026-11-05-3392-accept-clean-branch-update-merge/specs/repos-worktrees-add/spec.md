## MODIFIED Requirements

### Requirement: A staged branch is taken over

When `origin` has the branch `<type>/N-<slug>` for issue N, and every commit of it past `origin/main` is by `<service.github_app.slug>[bot]` or is a clean merge, `add N` SHALL create the worktree `w-N` on that branch, with `origin/<branch>` as its upstream. A clean merge is a merge commit whose tree is the one that `git merge-tree --write-tree` gives for its two parents. The branch SHALL have at least one commit by the App. The same rule SHALL apply to a stopped implement run.

#### Scenario: A branch with only the App's commits
- **WHEN** `origin` has `feat/2657-staged` with two commits by `devops-roadmap[bot]` past `origin/main`, `service.github_app.slug` is `devops-roadmap`, and the user runs `add 2657`
- **THEN** the directory `w-2657` exists with `feat/2657-staged` checked out at the tip of the pushed branch
- **AND** the upstream of that branch is `origin/feat/2657-staged`
- **AND** the output and the JSON report (`status` `took over`, `commits` 2) say that the command took over a staged branch with 2 commits

#### Scenario: A stopped implement run
- **WHEN** the pushed branch has three commits by the App: the staging commit and two code commits of a stopped run
- **THEN** `add` takes the branch over and the report gives `commits` 3

#### Scenario: A clean merge by a person
- **WHEN** the pushed branch has a commit by the App and a clean merge by `Jane Doe` past `origin/main`, and the user runs `add 2657`
- **THEN** `add` takes the branch over, and the report gives `commits` 1, because the clean merge is not counted

### Requirement: A commit by another author refuses the takeover
When one commit of the pushed branch past `origin/main` has an author other than the App's bot login, and the commit is not a clean merge, `add` SHALL exit 1, change nothing, and name the branch and that author.

#### Scenario: One commit by a person
- **WHEN** `origin` has `feat/2657-staged` with a commit by the App and a commit by `Jane Doe`, and the user runs `add 2657`
- **THEN** the command exits 1 and the error names `origin/feat/2657-staged` and `Jane Doe`
- **AND** no worktree or local branch is created

#### Scenario: A merge by a person that changes a file
- **WHEN** `origin` has `feat/2657-staged` with a commit by the App and a merge commit by `Jane Doe` whose tree differs from the tree of the clean merge of its parents, and the user runs `add 2657`
- **THEN** the command exits 1 and the error names `origin/feat/2657-staged` and `Jane Doe`
- **AND** no worktree or local branch is created
