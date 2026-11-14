## MODIFIED Requirements

### Requirement: The runner image passes the image scan
The runner image SHALL pass the scan of `ci.yml` and `release.yml` (Trivy, `HIGH,CRITICAL`, fixed findings only) with no `.trivyignore` entry. A tool whose newest release fails the scan SHALL be in `NOT_IN_RUNNER`, with the finding as the reason. A tool whose newest release passes the scan SHALL be in `RUNNER_TOOLS`, and the `runner` stage SHALL install it.

#### Scenario: A tool fails the scan
- **WHEN** the newest release of a tool that the gate needs holds a fixed HIGH finding
- **THEN** the table `NOT_IN_RUNNER` names the tool with the image scan as the reason, and the `runner` stage installs neither it nor a tool that only serves it

#### Scenario: The scanned tools return
- **WHEN** the newest releases of actionlint and Trivy pass the scan
- **THEN** `RUNNER_TOOLS` holds `actionlint`, `shellcheck` and `trivy`, and the `runner` stage installs all three

#### Scenario: The image is scanned
- **WHEN** `trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1` runs on the built `runner` target
- **THEN** it exits 0
