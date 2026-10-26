# Proposal: Generate SBOM via Aqua Trivy

## Why

This change resolves #1439. `devops scan sbom` previously built unvalidated CycloneDX 1.5 and SPDX 2.3 JSON documents with manual in-process Python dictionaries. The dependency inspection read `uv.lock` or fell back to the Python runtime packages of `devops-cli` itself, generating invalid SBOM inventories for non-Python repositories. In addition, the SPDX document namespace used unformatted timestamps with `None` versions, and SPDX identifiers lacked specification conformance.

This change fits one pull request.

## What Changes

- Delegate CycloneDX and SPDX SBOM generation to Aqua Trivy (`trivy fs`) through the security scanner base integration.
- For CycloneDX output, execute `trivy fs --format cyclonedx <target>`.
- For SPDX output, execute `trivy fs --format spdx-json <target>`.
- Output generated SBOM contents directly to the requested `--output` file or standard output without modifying text bytes.
- When the `trivy` binary is missing from `PATH`, report that the dependency is not installed and exit with code 1.
- Delete custom SBOM data classes (`SBOMComponent`, `SBOMDocument`), internal package inspection (`extract_workspace_components`), and hand-rolled JSON document builders (`generate_cyclonedx_sbom`, `generate_spdx_sbom`) in `src/devops_cli/security/sbom.py`.
- Add command builder `build_trivy_sbom_cmd` in `src/devops_cli/config/commands.py`.
- Implement `TrivySbomScanner` and `run_trivy_sbom` in `src/devops_cli/security/sbom.py`.

## Capabilities

### New Capabilities
- `scan-sbom`: Generation of Software Bill of Materials (SBOM) documents in CycloneDX and SPDX formats via Aqua Trivy.

### Modified Capabilities
None.

## Impact

- `src/devops_cli/config/commands.py`: added `build_trivy_sbom_cmd`.
- `src/devops_cli/security/sbom.py`: replaced hand-rolled document builders with Trivy-backed SBOM scanner.
- `src/devops_cli/commands/scan.py`: wired `devops scan sbom` to execute Trivy via `run_trivy_sbom` and check binary presence.
- `tests/test_sbom.py`: rewritten to verify Trivy command argument execution, unaltered file output, and missing tool handling.

## Feasibility

The premise was verified against the real system:
- Aqua Trivy 0.75.0 is installed in the local environment (`trivy --version`).
- `trivy fs --help` confirms native support for `--format cyclonedx` and `--format spdx-json`.
- Executing `trivy fs --format cyclonedx .` produces valid CycloneDX SBOM JSON output.
- Executing `trivy fs --format spdx-json .` produces valid SPDX JSON SBOM output.

## Existing Tool Considered

Aqua Trivy (version 0.75.0, already pinned in `src/devops_cli/tools_lock/tools.lock`) provides validated CycloneDX and SPDX SBOM writers. Using Trivy removes the need to maintain hand-rolled dictionary generators in `src/devops_cli/security/sbom.py`. Deleted internal code includes `SBOMComponent`, `SBOMDocument`, `extract_workspace_components`, `generate_cyclonedx_sbom`, and `generate_spdx_sbom`.
