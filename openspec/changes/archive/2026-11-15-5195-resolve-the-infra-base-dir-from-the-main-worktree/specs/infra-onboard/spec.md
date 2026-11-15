## ADDED Requirements

### Requirement: A relative repos base dir resolves under the main worktree
`default_checkout` SHALL resolve a relative `repos.base_dir` under `main_worktree_root()`, so every git worktree of devops-cli finds the clone at the main checkout. An absolute `repos.base_dir` SHALL stay as given.

#### Scenario: A command in a linked worktree
- **WHEN** `devops infra status owner/name` runs in a worktree, and `repos.base_dir` is `repos`
- **THEN** the default checkout is `<main worktree>/repos/owner/name`

#### Scenario: An absolute base dir
- **WHEN** `repos.base_dir` is `/srv/repos`
- **THEN** the default checkout is `/srv/repos/owner/name`
