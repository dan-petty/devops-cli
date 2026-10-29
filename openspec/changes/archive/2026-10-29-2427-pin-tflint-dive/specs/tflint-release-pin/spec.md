
## Purpose
The tflint release that `devops install-tools` installs, and the zip archive format of `tools.lock` that it needs. Every build is checked against its SHA-256 before it is unpacked, so a build whose bytes differ from the lock is refused.

## ADDED Requirements

### Requirement: The tools lock pins tflint for four platforms
The `tflint` entry of `tools.lock` SHALL be a binary tool at version 0.65.0 with the format `zip`. It SHALL have one build for each of `linux-amd64`, `linux-arm64`, `darwin-amd64` and `darwin-arm64`. The `url` of each build SHALL name the GitHub release `v0.65.0` of `terraform-linters/tflint`, each build SHALL name the member `tflint`, and each `sha256` SHALL be 32 bytes.

#### Scenario: A test reads the lock
- **WHEN** a test loads the tools lock that devops-cli ships
- **THEN** the `tflint` entry has the version `0.65.0`, the format `zip`, and the four platforms
- **AND** every `url` starts with `https://github.com/terraform-linters/tflint/releases/download/v0.65.0/`, and every build names the member `tflint`

### Requirement: The installer unpacks a zip build
The installer SHALL unpack a build of the format `zip` only after its SHA-256 equals the lock's. It SHALL copy the member that the lock names to the executable of the tool and set its execute bit.

#### Scenario: A zip build holds the tool beside other files
- **WHEN** `install_binary` installs a verified zip build that holds `LICENSE` and the member `tflint`
- **THEN** the tool on the target directory has the bytes of the member and is executable

#### Scenario: The member is not in the archive
- **WHEN** `install_binary` installs a verified zip build that does not hold the member that the lock names
- **THEN** the install fails with an error that names the member, and no file of the tool stays
