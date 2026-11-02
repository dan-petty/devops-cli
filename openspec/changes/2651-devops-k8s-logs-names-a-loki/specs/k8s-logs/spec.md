## ADDED Requirements

### Requirement: loki-url-config-setting
The command devops k8s logs SHALL read the Loki address from the loki.url setting when no --loki-url flag is given, and the MCP tool k8s_logs SHALL read the same setting.

#### Scenario: configured-address-is-used
- **WHEN** loki.url is set to http://example.com:3100 and devops k8s logs is run without --loki-url
- **THEN** The HTTP request is sent to http://example.com:3100/loki/api/v1/query_range

#### Scenario: default-address-when-unset
- **WHEN** loki.url is not set and devops k8s logs is run without --loki-url
- **THEN** The HTTP request is sent to http://localhost:3100/loki/api/v1/query_range

#### Scenario: flag-overrides-setting
- **WHEN** loki.url is set to http://example.com:3100 and devops k8s logs is run with --loki-url http://192.0.2.1:3100
- **THEN** The HTTP request is sent to http://192.0.2.1:3100/loki/api/v1/query_range
