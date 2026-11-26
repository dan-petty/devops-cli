## ADDED Requirements

### Requirement: A new worktree gets the Node tools of the lock file
The `devops repos worktrees add` command SHALL run `npm ci --ignore-scripts` in the new worktree when that worktree holds `package-lock.json`, SHALL start no npm process when the worktree holds no such file, and SHALL start none on a dry run. A failed install SHALL write a warning that names `npm ci --ignore-scripts` and SHALL keep the new worktree.

#### Scenario: The add command installs the Node tools of the lock file
- **WHEN** A test runs `devops repos worktrees add` with the process fake for a repository that holds `package-lock.json`.
- **THEN** The fake records one `npm ci --ignore-scripts` call whose working directory is the new worktree.

#### Scenario: A checkout with no lock file starts no npm
- **WHEN** A test runs `devops repos worktrees add` with the process fake for a repository that holds no `package-lock.json`.
- **THEN** The fake records no call of `npm`.

#### Scenario: A failed install warns and keeps the worktree
- **WHEN** The process fake answers the `npm ci --ignore-scripts` call with exit code 1.
- **THEN** The command writes a warning that names `npm ci --ignore-scripts`, and the new worktree still exists.
