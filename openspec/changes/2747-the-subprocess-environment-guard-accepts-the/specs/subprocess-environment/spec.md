## ADDED Requirements

### Requirement: Refuse PYTEST_ADDOPTS caller override
build_subprocess_env SHALL raise SecurityError when a caller override sets PYTEST_ADDOPTS.

#### Scenario: Caller sets PYTEST_ADDOPTS
- **WHEN** A caller passes PYTEST_ADDOPTS in the env dict to build_subprocess_env
- **THEN** build_subprocess_env raises SecurityError

### Requirement: Refuse NPM_CONFIG family caller overrides
build_subprocess_env SHALL raise SecurityError when a caller override sets any key matching the NPM_CONFIG_* pattern.

#### Scenario: Caller sets npm_config_logs_dir
- **WHEN** A caller passes npm_config_logs_dir in the env dict to build_subprocess_env
- **THEN** build_subprocess_env raises SecurityError

#### Scenario: Caller sets npm_config_cache
- **WHEN** A caller passes npm_config_cache in the env dict to build_subprocess_env
- **THEN** build_subprocess_env raises SecurityError

#### Scenario: Caller sets an unprobed NPM_CONFIG key
- **WHEN** A caller passes NPM_CONFIG_REGISTRY in the env dict to build_subprocess_env
- **THEN** build_subprocess_env raises SecurityError
