## Purpose
The devcontainer image holds every tool of `tools.lock` at its locked version in standard locations, so a tool is on PATH after a build and a rebuild of the image is the way to change it.

## ADDED Requirements

### Requirement: The image build checks each binary
The build of `.devcontainer/Dockerfile` SHALL download each binary tool of `tools.lock` with the url and the sha256 of `tools.lock` for `linux-amd64` and `linux-arm64`, SHALL check the sha256 before it unpacks the file, and SHALL NOT run `devops install-tools`.

#### Scenario: The Dockerfile pins what the lock pins
- **WHEN** a test reads `.devcontainer/Dockerfile` and `tools.lock`
- **THEN** the Dockerfile holds the url and the sha256 of each binary for both Linux architectures
- **AND** the Dockerfile checks a download with `sha256sum -c`
- **AND** the Dockerfile does not name `install-tools`

### Requirement: The image build installs Python and Node tools from their lock files
The build of `.devcontainer/Dockerfile` SHALL install each Python tool of `tools.lock` with `uv pip sync --require-hashes` from its requirements file, and each Node tool with `npm ci --ignore-scripts` from its lockfile.

#### Scenario: Each package manager step is present
- **WHEN** a test reads `.devcontainer/Dockerfile` and `tools.lock`
- **THEN** each Python tool installs with `uv pip sync --require-hashes` from the requirements file that the lock names
- **AND** each Node tool installs with `npm ci --ignore-scripts`

### Requirement: The image puts the tools under /usr/local
The build of `.devcontainer/Dockerfile` SHALL put the command of each tool in `/usr/local/bin` and the files of each Python or Node tool in `/usr/local/share/devops-tools`.

#### Scenario: The commands are on PATH
- **WHEN** a test reads `.devcontainer/Dockerfile`
- **THEN** the Dockerfile copies the commands of the binary tools into `/usr/local/bin`
- **AND** each Python tool installs into `/usr/local/share/devops-tools/<tool>`

### Requirement: Post-create installs no locked tool
`devops devcontainer post-create` SHALL install no tool of `tools.lock` and SHALL have no `--skip-tools` option, and its plan SHALL have no request of an installer for a tool.

#### Scenario: The plan has no tool install
- **WHEN** a test builds the post-create plan
- **THEN** no request has the method `npm` or a `GET` of a tool download

#### Scenario: The skip option is gone
- **WHEN** a test runs `devops devcontainer post-create --skip-tools`
- **THEN** the command exits with code 2
