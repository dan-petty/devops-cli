## ADDED Requirements

### Requirement: The image installs the network diagnostics tools
The system-package step of `.devcontainer/Dockerfile` SHALL install the Debian packages `iputils-ping`, `iputils-tracepath`, `traceroute`, `mtr-tiny`, `netcat-openbsd` and `tcpdump` with the other system packages of the image, and the built image SHALL have the commands `ping`, `tracepath`, `traceroute`, `mtr`, `nc` and `tcpdump` on the path of `vscode`.

#### Scenario: The system-package step holds the network packages
- **WHEN** a test reads the first `apt-get install` step of the last stage of `.devcontainer/Dockerfile`
- **THEN** the step holds `socat` and the six network packages

#### Scenario: The built image has the network commands
- **WHEN** the smoke action `.github/actions/devcontainer-smoke` starts the built image as `vscode`
- **THEN** `command -v` finds `ping`, `tracepath`, `traceroute`, `mtr`, `nc` and `tcpdump`

### Requirement: The user vscode can open an ICMP echo socket
The `runArgs` of `.devcontainer/devcontainer.json` SHALL hold `--sysctl=net.ipv4.ping_group_range=1000 1000`, and the `devcontainer.json` that `devops devcontainer init` writes SHALL hold the same `runArgs`. In a container that starts with this run argument, `ping` as `vscode` SHALL get a reply.

#### Scenario: The workspace and a scaffolded devcontainer start with the same run arguments
- **WHEN** a test reads `runArgs` of `.devcontainer/devcontainer.json` and of the template rendered for the published image
- **THEN** the workspace list holds `--sysctl=net.ipv4.ping_group_range=1000 1000`, and the two lists are equal

#### Scenario: ping works as vscode in the built image
- **WHEN** the smoke action starts the built image as `vscode` with `--sysctl net.ipv4.ping_group_range=1000 1000` and runs `ping -c 1 127.0.0.1`
- **THEN** `ping` exits with code 0
