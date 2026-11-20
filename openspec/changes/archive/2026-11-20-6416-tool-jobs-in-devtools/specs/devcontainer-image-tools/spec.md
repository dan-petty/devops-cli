## MODIFIED Requirements

### Requirement: OpenTofu is a pinned tool
`tools.lock` SHALL hold OpenTofu with the sha256 of the linux-amd64 and linux-arm64 builds. The `Static Analysis` job SHALL put the `tofu` of the devtools image on its path with `.github/actions/devtools-commands`. The devcontainer image and the runner image SHALL have the `tofu` of the devtools image.

#### Scenario: The lock
- **WHEN** `devops install-tools --tool tofu --target-dir <dir>` runs
- **THEN** `<dir>/tofu version` prints `OpenTofu v<version>`, with the `Pinned` version that `devops install-tools status` shows for `tofu`

#### Scenario: The devcontainer image
- **WHEN** a person runs `tofu version` in a container of the image
- **THEN** it prints `OpenTofu v<version>` and exits with code 0

#### Scenario: CI
- **WHEN** the live check reads the log of the `Static Analysis` job of a pull request
- **THEN** the step `Put the tools of the devtools image on PATH` builds the `devtools-bin` stage from the tag and the digest of the devtools image and puts `tofu` on the path of the job
