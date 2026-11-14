## ADDED Requirements

### Requirement: The output names the branch of the checkout
`devops openspec new` SHALL name the branch of the checkout in its output, and SHALL name `HEAD detached` when HEAD is detached.

#### Scenario: The checkout is on the default branch
- **WHEN** the checkout is on `main` and the author runs `devops openspec new 4593 --title "fix(openspec): alpha"`
- **THEN** the output holds `Created openspec/changes/4593-alpha on branch main.` and `Branch:  main`

#### Scenario: HEAD is detached
- **WHEN** HEAD is detached and the author runs the command
- **THEN** the output holds `Branch:  HEAD detached`, holds no `on branch`, and creates `openspec/changes/4593-alpha/`

### Requirement: The folder takes the slug of the branch of the issue
The command SHALL take the slug of the change folder from the branch of the checkout when that branch is `<type>/<issue>-<slug>` for the same issue, and from the title otherwise.

#### Scenario: The branch slug differs from the title slug
- **WHEN** the worktree is on `fix/4593-alpha` and the author runs `devops openspec new 4593 --title "fix(openspec): beta"`
- **THEN** the command creates `openspec/changes/4593-alpha/` and no folder `openspec/changes/4593-beta/`

### Requirement: A branch of another issue is a suggestion
When the branch of the checkout does not name the same issue, the command SHALL state that the computed branch name is a suggestion and that the checkout is not on it.

#### Scenario: The checkout is on another issue
- **WHEN** the checkout is on `docs/5225-adr-front-matter-and-rules` and the author runs `devops openspec new 4593 --title "fix(openspec): alpha"`
- **THEN** the output holds `Branch:  docs/5225-adr-front-matter-and-rules` and `The branch fix/4593-alpha is a suggestion for this change. This checkout is not on it.`

### Requirement: The dry run names the folder and branch of a real run
The dry run SHALL name the folder and the branch that a real run creates in the same checkout, and SHALL create no folder.

#### Scenario: The dry run is in a worktree on the branch of the issue
- **WHEN** the worktree is on `fix/4593-alpha` and the author runs `devops openspec new 4593 --dry-run --title "fix(openspec): beta"`
- **THEN** the output holds `Would create openspec/changes/4593-alpha on branch fix/4593-alpha.` and `Branch: fix/4593-alpha`, and no folder is created
