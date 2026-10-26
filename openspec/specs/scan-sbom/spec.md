# scan-sbom Specification

## Purpose
How devops scan sbom generates Software Bill of Materials documents in CycloneDX and SPDX formats by invoking Aqua Trivy through the security scanner base, reporting a missing binary as not installed and streaming tool output unchanged.

## Requirements

### Requirement: devops scan sbom generates CycloneDX and SPDX-JSON SBOMs via Trivy
`devops scan sbom` SHALL execute `trivy fs --format cyclonedx <target>` for CycloneDX output and `trivy fs --format spdx-json <target>` for SPDX output through the security scanner base. The tool output SHALL be written unchanged to standard output or the destination path specified by `--output`.

#### Scenario: Generating CycloneDX SBOM to a file
- **WHEN** `devops scan sbom` runs with `--format cyclonedx` and `--output sbom.json`
- **THEN** Trivy executes with arguments `trivy fs --format cyclonedx <target>`
- **AND** the recorded tool output is written unchanged to `sbom.json`

#### Scenario: Generating SPDX JSON SBOM to stdout
- **WHEN** `devops scan sbom` runs with `--format spdx`
- **THEN** Trivy executes with arguments `trivy fs --format spdx-json <target>`
- **AND** the recorded tool output is written unchanged to stdout

### Requirement: Missing Trivy binary reports not installed
When the `trivy` executable is not found on `PATH`, `devops scan sbom` SHALL report that the dependency is not installed and exit with a non-zero status code.

#### Scenario: Trivy is missing from PATH
- **WHEN** `devops scan sbom` runs while `trivy` is not installed
- **THEN** the command exits with code 1
- **AND** the output reports that `trivy` is not installed
