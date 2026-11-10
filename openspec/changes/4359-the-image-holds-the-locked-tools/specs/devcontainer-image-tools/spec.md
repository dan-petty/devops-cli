## Purpose
The devcontainer image holds every tool of `tools.lock` at its locked version in standard locations, so a tool is on PATH after a build and a rebuild of the image is the way to change it.

## ADDED Requirements

### Requirement: The image holds the locked tools
The build of `.devcontainer/Dockerfile` SHALL run `devops install-tools` for every tool of `tools.lock`, with `--target-dir /usr/local/bin` and `DEVOPS_CLI_USER_DATA_ROOT=/usr/local/share/devops-cli` for that step only.

#### Scenario: The build installs under /usr/local
- **WHEN** a test reads `.devcontainer/Dockerfile`
- **THEN** one `RUN` runs `devops install-tools --target-dir /usr/local/bin` with `DEVOPS_CLI_USER_DATA_ROOT=/usr/local/share/devops-cli` and with no `--tool`

### Requirement: Post-create installs no locked tool
`devops devcontainer post-create` SHALL install no tool of `tools.lock` and SHALL have no `--skip-tools` option, and its plan SHALL have no request of an installer for a tool.

#### Scenario: The plan has no tool install
- **WHEN** a test builds the post-create plan
- **THEN** no request has the method `npm` or a `GET` of a tool download

#### Scenario: The skip option is gone
- **WHEN** a test runs `devops devcontainer post-create --skip-tools`
- **THEN** the command exits with code 2
