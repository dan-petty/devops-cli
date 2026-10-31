## ADDED Requirements

### Requirement: Refuse data-egress environment variable caller override
build_subprocess_env SHALL raise SecurityError when a caller provides a key in the data-egress environment variable set in the env parameter.

#### Scenario: Caller sets GH_TELEMETRY_ENDPOINT_URL
- **WHEN** build_subprocess_env is called with env containing GH_TELEMETRY_ENDPOINT_URL set to https://example.com
- **THEN** SecurityError is raised and the key is not in the returned environment

### Requirement: Ambient filter excludes data-egress keys
The ambient environment filter SHALL exclude keys in the data-egress environment variable set because they are not in DEFAULT_ALLOWED_ENV_VARS and match no allowed prefix.

#### Scenario: Ambient environment holds GH_TELEMETRY_ENDPOINT_URL
- **WHEN** os.environ contains GH_TELEMETRY_ENDPOINT_URL and isolate_env is True
- **THEN** the key is absent from the returned environment dictionary

### Requirement: Non-egress GH_TELEMETRY keys remain accepted
build_subprocess_env SHALL NOT raise SecurityError for a caller override of GH_TELEMETRY or GH_TELEMETRY_SAMPLE_RATE.

#### Scenario: Caller sets GH_TELEMETRY
- **WHEN** build_subprocess_env is called with env containing GH_TELEMETRY set to log
- **THEN** no SecurityError is raised and the key is present in the returned environment

#### Scenario: Caller sets GH_TELEMETRY_SAMPLE_RATE
- **WHEN** build_subprocess_env is called with env containing GH_TELEMETRY_SAMPLE_RATE set to 0.5
- **THEN** no SecurityError is raised and the key is present in the returned environment
