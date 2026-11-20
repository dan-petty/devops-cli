## MODIFIED Requirements

### Requirement: Every pin of the repository has a Renovate manager
No rule SHALL turn off a manager. Each pinned file SHALL match a file pattern of its manager. Custom managers SHALL read the pins that no built-in manager reads: the Python minor, CloudNativePG and Mattermost images, values tags with no repository and Grafana plugins. No custom manager SHALL write a tool version into a file under `src/`, except `DEFAULT_PYTHON_VERSION`. Pins of one tool in several files SHALL share one group of every update type.

#### Scenario: The managers are read against the tracked files
- **WHEN** a test applies the file patterns and the match strings of the configuration to the tracked files
- **THEN** each pinned file matches its manager, and the custom managers find exactly the expected pins
- **AND** the coupled groups `uv`, `node`, `python runtime`, `ruff`, `actionlint`, `openspec`, `dcgm-exporter` and `devtools` set no update type
- **AND** the group `devtools` holds the devtools image of both Dockerfiles

#### Scenario: A uv or Node update changes no runtime code
- **WHEN** Renovate opens a pull request in the group `uv` or `node`
- **THEN** its diff holds no file under `src/devops_cli/`, and no `Fail-to-Pass Check` runs on it

## REMOVED Requirements

### Requirement: Renovate holds a security fix that the semgrep pins block
**Reason**: The Semgrep lock of `src/devops_cli/tools_lock/` is gone (#4363). The devtools repository holds the Semgrep of its image and its held fixes.
**Migration**: None in this repository.
