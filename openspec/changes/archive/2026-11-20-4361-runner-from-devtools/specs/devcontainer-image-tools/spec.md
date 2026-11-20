## MODIFIED Requirements

### Requirement: OpenTofu is a pinned tool
`tools.lock` SHALL hold OpenTofu with the sha256 of the linux-amd64 and linux-arm64 builds. The CI test job SHALL install it with `devops install-tools --tool tofu`. The devcontainer image and the runner image SHALL have the `tofu` of the devtools image.

#### Scenario: The lock
- **WHEN** `devops install-tools --tool tofu --target-dir <dir>` runs
- **THEN** `<dir>/tofu version` prints `OpenTofu v<version>`, with the `Pinned` version that `devops install-tools status` shows for `tofu`

#### Scenario: The devcontainer image
- **WHEN** a person runs `tofu version` in a container of the image
- **THEN** it prints `OpenTofu v<version>` and exits with code 0

#### Scenario: CI
- **WHEN** the test job installs its tools
- **THEN** `tofu version` on the path prints the `Pinned` version
