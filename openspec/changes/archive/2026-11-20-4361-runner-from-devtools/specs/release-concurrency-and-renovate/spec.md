## MODIFIED Requirements

### Requirement: Every pin of the repository has a Renovate manager
No rule SHALL turn off a manager. Each pinned file SHALL match a file pattern of its manager. Custom managers SHALL read the pins that no built-in manager reads: the Python minor, the tools lock, CloudNativePG and Mattermost images, values tags with no repository and Grafana plugins. No custom manager SHALL write a tool version into a Python file under `src/`, except `DEFAULT_PYTHON_VERSION`. Pins of one tool in several files SHALL share one group of every update type.

#### Scenario: The managers are read against the tracked files
- **WHEN** a test applies the file patterns and the match strings of the configuration to the tracked files
- **THEN** each pinned file matches its manager, and the custom managers find exactly the expected pins
- **AND** the coupled groups `trivy`, `argo`, `cloudflared`, `uv`, `node`, `python runtime`, `ruff`, `bandit`, `actionlint`, `dcgm-exporter` and `devtools` set no update type
- **AND** the group `devtools` holds the devtools image of both Dockerfiles and the OpenSpec pin of `tools.lock`, because the runner image takes OpenSpec from the devtools image

#### Scenario: A uv or Node update changes no runtime code
- **WHEN** Renovate opens a pull request in the group `uv` or `node`
- **THEN** its diff holds no file under `src/devops_cli/`, and no `Fail-to-Pass Check` runs on it
