## ADDED Requirements

### Requirement: The Loki address is a setting
The settings SHALL hold the Loki address as `loki.url`, unset by default. The key SHALL take a URL with the scheme `http` or `https`. It SHALL refuse any other scheme, such as `k8s`, with an error that names `loki.url`. The variable `DEVOPS_CLI_LOKI_URL` SHALL set it.

#### Scenario: A Loki address is set
- **WHEN** `devops config set loki.url http://example.com:3100` runs
- **THEN** the command exits 0 and the config file holds `loki.url` as `http://example.com:3100`

#### Scenario: A cluster address is refused
- **WHEN** `devops config set loki.url k8s://logging/loki:3100` runs
- **THEN** the command exits non-zero, the error names `loki.url`, and the config file does not change

#### Scenario: The variable sets the address
- **WHEN** `DEVOPS_CLI_LOKI_URL` is `http://example.com:3100` and the settings load
- **THEN** `loki.url` is `http://example.com:3100`
