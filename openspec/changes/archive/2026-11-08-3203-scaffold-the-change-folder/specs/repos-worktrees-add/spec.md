## MODIFIED Requirements

### Requirement: A new worktree starts at the fetched main
When `origin` has no branch for the issue, `add <issue> --type <type> --slug <slug>` or `add <issue> --title <title>` SHALL fetch `origin/main` and create the worktree `w-<issue>` under the agent worktrees directory, on the new branch `<type>/<issue>-<slug>` at the tip of the fetched `origin/main`. The branch SHALL have no upstream. The command SHALL print the path and the branch. It SHALL require `--type` and `--slug` or `--title` in that case.

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

#### Scenario: Title derives type and slug
- **WHEN** the user runs `add 3203 --title 'feat(openspec): scaffold the change folder' --dry-run`
- **THEN** the command plans the branch `feat/3203-scaffold-the-change-folder`
