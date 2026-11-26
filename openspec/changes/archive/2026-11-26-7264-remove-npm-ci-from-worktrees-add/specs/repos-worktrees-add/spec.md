## REMOVED Requirements

### Requirement: A new worktree gets the Node tools of the lock file
**Reason**: The gate failure that the install answered came from a stale `openspec` in a home folder that was first on `PATH`, not from a missing install (#7264).
**Migration**: The devcontainer puts `node_modules/.bin` of the main checkout on `PATH`, so a new worktree gets the pinned tools. Run `npm ci --ignore-scripts` in a worktree only before `make design-tokens`, or when its branch changes `package-lock.json`.

## ADDED Requirements

### Requirement: The add command installs no Node tools
The `devops repos worktrees add` command SHALL start no npm process, also when the new worktree holds `package-lock.json`.

#### Scenario: A repository with a lock file
- **WHEN** A test runs `devops repos worktrees add` with the process fake for a repository that holds `package-lock.json`.
- **THEN** The fake records no call of `npm`, and the new worktree exists.
