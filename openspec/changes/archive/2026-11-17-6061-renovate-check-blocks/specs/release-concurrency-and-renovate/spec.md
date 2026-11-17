## ADDED Requirements

### Requirement: An update of runtime code has the prefix of a release
The repository configuration SHALL give each update that changes a file under `src/devops_cli/` the prefix `fix(deps):`, because the `Semantic PR title` check refuses a hidden type for runtime code and release-please must release the change. A group takes the prefix of its first update, so each group that holds such a file, and lock file maintenance, SHALL set the same prefix for each of their updates.

#### Scenario: An update of the tools lock or of the runner tools table
- **WHEN** Renovate opens a pull request that changes a file under `src/devops_cli/`, alone, in the group `uv`, `node`, `python runtime`, `bandit` or `tools`, or as lock file maintenance
- **THEN** its title has the prefix `fix(deps):`, the `Semantic PR title` check passes with no manual retitle, and release-please adds a changelog line for it
