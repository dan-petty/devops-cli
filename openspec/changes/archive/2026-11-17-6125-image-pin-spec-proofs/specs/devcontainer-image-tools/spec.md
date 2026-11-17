## MODIFIED Requirements

### Requirement: The image build checks each binary
The build of `.devcontainer/Dockerfile` SHALL download each binary tool of `tools.lock` with the url and the sha256 of `tools.lock` for `linux-amd64` and `linux-arm64`, SHALL check the sha256 before it unpacks the file, and SHALL NOT run `devops install-tools`.

#### Scenario: The Dockerfile pins what the lock pins
- **WHEN** the `DevContainer Image` check builds `.devcontainer/Dockerfile` for a pull request that changes `.devcontainer/` or `src/devops_cli/tools_lock/`
- **THEN** the `tools` stage checks each download with `sha256sum -c`, and a download with a different sha256 stops the build
- **AND** in a container of the built image, `devops install-tools status` shows a command under `/usr/local/bin` for each binary tool
- **AND** the version that each of these commands prints is the `Pinned` version of `devops install-tools status`

### Requirement: The image build installs Python and Node tools from their lock files
The build of `.devcontainer/Dockerfile` SHALL install each Python tool of `tools.lock` with `uv pip sync --require-hashes` from its requirements file, and each Node tool with `npm ci --ignore-scripts` from its lockfile.

#### Scenario: Each package manager step is present
- **WHEN** the `DevContainer Image` check builds the image
- **THEN** `uv pip sync --require-hashes` installs each Python tool from the requirements file that the lock names, and `npm ci --ignore-scripts` installs each Node tool from its lockfile
- **AND** a package with a hash other than the hash of its lock stops the build
- **AND** in a container of the built image, `devops install-tools status` shows a command for each Python tool and each Node tool

### Requirement: The image puts the tools under /usr/local
The build of `.devcontainer/Dockerfile` SHALL put the command of each tool in `/usr/local/bin` and the files of each Python or Node tool in `/usr/local/share/devops-tools`.

#### Scenario: The commands are on PATH
- **WHEN** a person runs `devops install-tools status` in a container of the image
- **THEN** the `Installed` column names a path under `/usr/local/bin` for each tool
- **AND** `readlink -f` of the command of each Python or Node tool names a path under `/usr/local/share/devops-tools/<tool>/`

### Requirement: The user vscode can open an ICMP echo socket
The `runArgs` of `.devcontainer/devcontainer.json` SHALL hold `--sysctl=net.ipv4.ping_group_range=1000 1000`, and the `devcontainer.json` that `devops devcontainer init` writes SHALL hold the same `runArgs`. In a container that starts with this run argument, `ping` as `vscode` SHALL get a reply.

#### Scenario: The workspace and a scaffolded devcontainer start with the same run arguments
- **WHEN** a person runs `cat /proc/sys/net/ipv4/ping_group_range` and `ping -c 1 127.0.0.1` as `vscode` in the workspace container
- **THEN** the range is `1000 1000`, and `ping` exits with code 0
- **AND** a container that `devcontainer up` starts from the configuration that `uv run devops devcontainer init --no-minikube <dir>` writes gives the same range and the same `ping` result

#### Scenario: ping works as vscode in the built image
- **WHEN** the smoke action starts the built image as `vscode` with `--sysctl net.ipv4.ping_group_range=1000 1000` and runs `ping -c 1 127.0.0.1`
- **THEN** `ping` exits with code 0

### Requirement: OpenTofu is a pinned tool
`tools.lock` SHALL hold OpenTofu with the sha256 of the linux-amd64 and linux-arm64 builds. The `tools` stage of the devcontainer image SHALL install it from the pin with a sha256 check. The runner image and the CI test job SHALL install it with `devops install-tools --tool tofu`.

#### Scenario: The lock
- **WHEN** `devops install-tools --tool tofu --target-dir <dir>` runs
- **THEN** `<dir>/tofu version` prints `OpenTofu v<version>`, with the `Pinned` version that `devops install-tools status` shows for `tofu`

#### Scenario: The devcontainer image
- **WHEN** the `DevContainer Image` check builds the image
- **THEN** the `tools` stage checks the download of `tofu` with `sha256sum -c`
- **AND** `tofu version` in a container of the built image prints the `Pinned` version

#### Scenario: CI
- **WHEN** the test job installs its tools
- **THEN** `tofu version` on the path prints the `Pinned` version

## REMOVED Requirements

### Requirement: The image installs the network diagnostics tools
**Reason**: Its first scenario named a test that reads the `apt-get install` step of `.devcontainer/Dockerfile`, and only restated the step. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with the smoke action as its proof (#6083).
**Migration**: The requirement "The image has the network diagnostics commands" holds the same rule.

## ADDED Requirements

### Requirement: The image has the network diagnostics commands
The system-package step of `.devcontainer/Dockerfile` SHALL install the Debian packages `iputils-ping`, `iputils-tracepath`, `traceroute`, `mtr-tiny`, `netcat-openbsd` and `tcpdump`, and the built image SHALL have the commands `ping`, `tracepath`, `traceroute`, `mtr`, `nc` and `tcpdump` on the path of `vscode`.

#### Scenario: The smoke action finds the network commands
- **WHEN** the smoke action `.github/actions/devcontainer-smoke` starts the built image as `vscode`
- **THEN** `command -v` finds `ping`, `tracepath`, `traceroute`, `mtr`, `nc` and `tcpdump`

#### Scenario: The image holds the network packages
- **WHEN** a person runs `dpkg-query -W iputils-ping iputils-tracepath traceroute mtr-tiny netcat-openbsd tcpdump` in a container of the image
- **THEN** the output lists the six packages with a version
