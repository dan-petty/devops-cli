# devcontainer-image-tools Specification

## Purpose
The devcontainer image builds FROM the devtools image at a digest and takes each tool from it, in standard locations. It adds the venv of devops-cli, the user vscode and Podman, so a tool is on PATH after a build and a new devtools digest is the way to change it.

## Requirements

### Requirement: The image puts the tools under /usr/local
The devcontainer image SHALL have the command of each tool of the devtools image in `/usr/local/bin`, and the files of each Python or Node tool in `/usr/local/lib/devtools`, as the devtools image puts them.

#### Scenario: The commands are on PATH
- **WHEN** the smoke action `.github/actions/devcontainer-smoke` starts the built image as `vscode`
- **THEN** `command -v` finds `gh`, `copilot`, `claude`, `openspec`, `semgrep`, `kubectl`, `helm`, `minikube`, `trivy` and `podman`
- **AND** `readlink -f /usr/local/bin/semgrep` in a container of the image names a path under `/usr/local/lib/devtools/semgrep/`

### Requirement: Post-create installs no locked tool
`devops devcontainer post-create` SHALL install no tool of `tools.lock` and SHALL have no `--skip-tools` option, and its plan SHALL have no request of an installer for a tool.

#### Scenario: The plan has no tool install
- **WHEN** a test builds the post-create plan
- **THEN** no request has the method `npm` or a `GET` of a tool download

#### Scenario: The skip option is gone
- **WHEN** a test runs `devops devcontainer post-create --skip-tools`
- **THEN** the command exits with code 2

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
`tools.lock` SHALL hold OpenTofu with the sha256 of the linux-amd64 and linux-arm64 builds. The runner image and the CI test job SHALL install it with `devops install-tools --tool tofu`. The devcontainer image SHALL have the `tofu` of the devtools image.

#### Scenario: The lock
- **WHEN** `devops install-tools --tool tofu --target-dir <dir>` runs
- **THEN** `<dir>/tofu version` prints `OpenTofu v<version>`, with the `Pinned` version that `devops install-tools status` shows for `tofu`

#### Scenario: The devcontainer image
- **WHEN** a person runs `tofu version` in a container of the image
- **THEN** it prints `OpenTofu v<version>` and exits with code 0

#### Scenario: CI
- **WHEN** the test job installs its tools
- **THEN** `tofu version` on the path prints the `Pinned` version

### Requirement: The image has the network diagnostics commands
The devcontainer image SHALL have the Debian packages `iputils-ping`, `iputils-tracepath`, `traceroute`, `mtr-tiny`, `netcat-openbsd` and `tcpdump` of the devtools image, and the commands `ping`, `tracepath`, `traceroute`, `mtr`, `nc` and `tcpdump` on the path of `vscode`.

#### Scenario: The smoke action finds the network commands
- **WHEN** the smoke action `.github/actions/devcontainer-smoke` starts the built image as `vscode`
- **THEN** `command -v` finds `ping`, `tracepath`, `traceroute`, `mtr`, `nc` and `tcpdump`

#### Scenario: The image holds the network packages
- **WHEN** a person runs `dpkg-query -W iputils-ping iputils-tracepath traceroute mtr-tiny netcat-openbsd tcpdump` in a container of the image
- **THEN** the output lists the six packages with a version

### Requirement: The image builds FROM the devtools image
`.devcontainer/Dockerfile` SHALL build FROM `ghcr.io/dan-petty/devtools` with a tag and a `@sha256:` digest, and SHALL download no tool. It SHALL have `# check=error=true`.

#### Scenario: The Dockerfile names the devtools digest and downloads nothing
- **WHEN** a person runs `git grep -n -E '^FROM |curl|sha256sum|npm ci|devops-tools' -- .devcontainer/Dockerfile`
- **THEN** the only image that the file pulls is `ghcr.io/dan-petty/devtools:<tag>@sha256:<digest>`, each other `FROM` names a stage of the file or `scratch`, and no line downloads or installs a tool

#### Scenario: The tools of the devtools image run
- **WHEN** the smoke action starts the built image as `vscode`
- **THEN** `kubectl version --client`, `helm version`, `minikube version`, `trivy --version`, `gh --version`, `openspec --version` and `semgrep --version` exit with code 0

### Requirement: The image holds devops in a venv
The image SHALL install the requirements of `uv.lock` with `--require-hashes` into `/opt/devops-cli/.venv`, the last directory of `PATH`, then the project as the last layer of `.devcontainer/Dockerfile` (the Dev Containers CLI adds the Feature layers over it, #6470), and SHALL set `USER vscode`.

#### Scenario: devops comes from the venv
- **WHEN** the smoke action starts the built image as `vscode`
- **THEN** `command -v devops` prints `/opt/devops-cli/.venv/bin/devops`, `devops --version` exits with code 0, and `id -u` prints `1000`

### Requirement: Podman takes the place of Docker
`.devcontainer/image/devcontainer.json` SHALL have only the Features `common-utils:2` (user `vscode`, uid and gid 1000) and `podman-in-podman:1` with `dockerCompat`, and its `remoteEnv` SHALL set `DOCKER_HOST` to `unix:///var/run/docker.sock`. The image SHALL have no Docker CLI and no Docker engine.

#### Scenario: docker runs Podman, and the API socket is rootful Podman
- **WHEN** the smoke action starts the built image with `devcontainer up` and runs `docker version` and `podman --url "$DOCKER_HOST" version` as `vscode`
- **THEN** the post-start check of the Feature passes, `docker version` prints `Podman Engine`, `DOCKER_HOST` is `unix:///var/run/docker.sock`, and the second command prints a `Server:` section

### Requirement: The credential helpers of GitHub come from remoteEnv
The `GIT_CONFIG_*` entries that route `github.com` and `gist.github.com` credentials through `gh auth git-credential` SHALL be in the `remoteEnv` of `.devcontainer/image/devcontainer.json`, and not in its `containerEnv`.

#### Scenario: The helper order in a started image
- **WHEN** the smoke action runs `git config --get-all credential.https://github.com.helper` through `devcontainer exec` in the started image
- **THEN** the command prints the empty value and then `!gh auth git-credential`
