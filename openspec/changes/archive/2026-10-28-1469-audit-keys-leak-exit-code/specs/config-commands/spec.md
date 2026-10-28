## ADDED Requirements

### Requirement: devops config audit-keys exits 0 only on a compliant audit
`devops config audit-keys` SHALL exit 0 only when no config file that it scans holds a plaintext secret and it reads and parses each of these files. It SHALL exit 1 when a config file holds a plaintext secret, or when it cannot read or parse a config file. The table output and each serialized output SHALL print the full report before the exit. The command SHALL print its success line only when it exits 0.

#### Scenario: A plaintext secret in the table output
- **WHEN** the active config file holds `grafana.token` with a value, and `devops config audit-keys` runs
- **THEN** the table shows `LEAK DETECTED` for `grafana.token`, the security alert names the leak, the success line does not show, and the command exits 1

#### Scenario: A plaintext secret in the JSON output
- **WHEN** the active config file holds `grafana.token` with a value, and `devops config audit-keys --json` runs
- **THEN** the JSON report holds `is_compliant: false` and the leak of `grafana.token` under `plaintext_leaks`, and the command exits 1

#### Scenario: A compliant config
- **WHEN** no config file that the audit scans holds a secret value, and each of these files parses
- **THEN** the command exits 0, and the table output shows the success line

#### Scenario: A config file that does not parse
- **WHEN** the active config file is not valid YAML, and `devops config audit-keys` runs
- **THEN** the command reports the file unaudited, the success line does not show, and the command exits 1
