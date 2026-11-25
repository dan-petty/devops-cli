## MODIFIED Requirements

### Requirement: Devcontainer guide names the driver
`docs/DEVCONTAINER_USAGE.md` SHALL name the `docker` driver and the rootful Podman socket in Topology 1.

#### Scenario: Guide names the driver and socket
- **WHEN** `git grep -n -e "--driver=docker" -e "/var/run/docker.sock" -- docs/DEVCONTAINER_USAGE.md` runs
- **THEN** the command prints a line of the Topology 1 section for each of the two texts

### Requirement: Issue link replacement
Each `#MINIKUBE_ISSUE` placeholder in `docs/DEVCONTAINER_USAGE.md` SHALL point to issue #6466.

#### Scenario: Placeholder links resolve to the issue
- **WHEN** `git grep -n "#MINIKUBE_ISSUE" -- docs/DEVCONTAINER_USAGE.md` runs
- **THEN** the command exits 1 with no match, and `git grep -n "#6466" -- docs/DEVCONTAINER_USAGE.md` prints a line
