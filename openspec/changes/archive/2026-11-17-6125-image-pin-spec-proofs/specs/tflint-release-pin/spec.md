## REMOVED Requirements

### Requirement: The tools lock pins tflint for four platforms
**Reason**: Its scenario named a test that reads the lock, and the requirement restated the version that each bump of tflint changes. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with an install as its proof (#6083).
**Migration**: The requirement "devops install-tools installs tflint from a zip build of its release" holds the same rule, with no version.

## ADDED Requirements

### Requirement: devops install-tools installs tflint from a zip build of its release
The `tflint` entry of `tools.lock` SHALL be a binary tool with the format `zip` and one build for each of `linux-amd64`, `linux-arm64`, `darwin-amd64` and `darwin-arm64`. The `url` of each build SHALL name the GitHub release of the locked version of `terraform-linters/tflint`, and each build SHALL name the member `tflint`.

#### Scenario: The download comes from the release of the locked version
- **WHEN** a person runs `uv run devops install-tools --tool tflint --dry-run` on a `linux-amd64`, `linux-arm64`, `darwin-amd64` or `darwin-arm64` host
- **THEN** the one request is a `GET` of a `.zip` URL that starts with `https://github.com/terraform-linters/tflint/releases/download/v<version>/`
- **AND** `<version>` is the `Pinned` version that `uv run devops install-tools status` shows for `tflint`

#### Scenario: The install unpacks the member of the build of the host
- **WHEN** a person runs `uv run devops install-tools --tool tflint --target-dir <dir>`
- **THEN** the install checks the sha256 of the build before it unpacks the member `tflint`
- **AND** `<dir>/tflint --version` prints `TFLint version <version>`, with the `Pinned` version
