# tflint-release-pin Specification

## Purpose
The tflint release that `devops install-tools` installs, and the zip archive format of `tools.lock` that it needs. Every build is checked against its SHA-256 before it is unpacked, so a build whose bytes differ from the lock is refused.

## Requirements

### Requirement: The installer unpacks a zip build
The installer SHALL unpack a build of the format `zip` only after its SHA-256 equals the lock's. It SHALL copy the member that the lock names to the executable of the tool and set its execute bit.

#### Scenario: A zip build holds the tool beside other files
- **WHEN** `install_binary` installs a verified zip build that holds `LICENSE` and the member `tflint`
- **THEN** the tool on the target directory has the bytes of the member and is executable

#### Scenario: The member is not in the archive
- **WHEN** `install_binary` installs a verified zip build that does not hold the member that the lock names
- **THEN** the install fails with an error that names the member, and no file of the tool stays

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
