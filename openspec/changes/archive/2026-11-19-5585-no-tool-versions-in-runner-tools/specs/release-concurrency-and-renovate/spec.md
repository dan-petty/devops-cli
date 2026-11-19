## MODIFIED Requirements

### Requirement: Every pin of the repository has a Renovate manager
No rule SHALL turn off a manager. Each pinned file SHALL match a file pattern of its manager. Custom managers SHALL read the pins that no built-in manager reads: the Python minor, the tools lock, CloudNativePG and Mattermost images, values tags with no repository and Grafana plugins. No custom manager SHALL write a tool version into a Python file under `src/`, except `DEFAULT_PYTHON_VERSION`. Pins of one tool in several files SHALL share one group of every update type.

#### Scenario: The managers are read against the tracked files
- **WHEN** a test applies the file patterns and the match strings of the configuration to the tracked files
- **THEN** each pinned file matches its manager, and the custom managers find exactly the expected pins
- **AND** the coupled groups `trivy`, `argo`, `cloudflared`, `uv`, `node`, `python runtime`, `ruff`, `bandit`, `actionlint`, `openspec` and `dcgm-exporter` set no update type

#### Scenario: A uv or Node update changes no runtime code
- **WHEN** Renovate opens a pull request in the group `uv` or `node`
- **THEN** its diff holds no file under `src/devops_cli/`, and no `Fail-to-Pass Check` runs on it

## REMOVED Requirements

### Requirement: An update of runtime code has the prefix of a release
**Reason**: Its scenario named the runner tools table, which holds no version now. OpenSpec refuses a MODIFIED block that gives a scenario a new title, so the requirement goes and comes back with a new name.
**Migration**: The requirement "A Renovate update of runtime code has the prefix of a release" holds the same rule.

## ADDED Requirements

### Requirement: A Renovate update of runtime code has the prefix of a release
The repository configuration SHALL give each update that changes a file under `src/devops_cli/` the prefix `fix(deps):`, because the `Semantic PR title` check refuses a hidden type for runtime code and release-please must release the change. A group takes the prefix of its first update, so each group that holds such a file, and lock file maintenance, SHALL set the same prefix for each of their updates.

#### Scenario: An update of a pin under src
- **WHEN** Renovate opens a pull request that changes a file under `src/devops_cli/`, alone, in the group `python runtime`, `bandit` or `tools`, or as lock file maintenance
- **THEN** its title has the prefix `fix(deps):`, the `Semantic PR title` check passes with no manual retitle, and release-please adds a changelog line for it
- **AND** no update changes the runner tools table `RUNNER_TOOLS`, because it holds no version
