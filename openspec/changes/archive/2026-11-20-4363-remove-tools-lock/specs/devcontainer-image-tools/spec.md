## MODIFIED Requirements

### Requirement: Post-create installs no locked tool
`devops devcontainer post-create` SHALL install no tool and SHALL have no `--skip-tools` option, and its plan SHALL have no request of an installer for a tool.

#### Scenario: The plan has no tool install
- **WHEN** a test builds the post-create plan
- **THEN** no request has the method `npm` or a `GET` of a tool download

#### Scenario: The skip option is gone
- **WHEN** a test runs `devops devcontainer post-create --skip-tools`
- **THEN** the command exits with code 2

## REMOVED Requirements

### Requirement: OpenTofu is a pinned tool
**Reason**: The tools lock and `devops install-tools` are gone (#4363); the devtools image holds OpenTofu.
**Migration**: The requirement below keeps the `tofu` of the devtools image in CI, the devcontainer and the runner image.

## ADDED Requirements

### Requirement: OpenTofu comes from the devtools image
The `Static Analysis` job SHALL copy the `tofu` of the devtools image with `.github/actions/devtools-commands` and put it on its path. The devcontainer image and the runner image SHALL have the `tofu` of the devtools image.

#### Scenario: The devcontainer image
- **WHEN** a person runs `tofu version` in a container of the image
- **THEN** it prints `OpenTofu v<version>` and exits with code 0

#### Scenario: CI
- **WHEN** the live check reads the log of the `Static Analysis` job of a pull request
- **THEN** the step `Copy the tools of the devtools image` restores the commands from the cache, or on a miss builds the `devtools-bin` stage from the tag and the digest of the devtools image, and the step `Put the tools of the devtools image on PATH` puts `tofu` on the path of the job
