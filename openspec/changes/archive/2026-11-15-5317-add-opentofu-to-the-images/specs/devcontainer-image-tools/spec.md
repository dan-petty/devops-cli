## ADDED Requirements

### Requirement: OpenTofu is a pinned tool
`tools.lock` SHALL hold OpenTofu 1.13.9 with the sha256 of the linux-amd64 and linux-arm64 builds. The `tools` stage of the devcontainer image SHALL install it from the pin with a sha256 check. The runner image and the CI test job SHALL install it with `devops install-tools --tool tofu`.

#### Scenario: The lock
- **WHEN** `devops install-tools --tool tofu --target-dir <dir>` runs
- **THEN** `<dir>/tofu version` prints `OpenTofu v1.13.9`

#### Scenario: The devcontainer image
- **WHEN** the `tools` stage builds
- **THEN** its step names the pinned URL and sha256 for each platform and runs `unzip`

#### Scenario: CI
- **WHEN** the test job installs its tools
- **THEN** `tofu` is on the path at 1.13.9
