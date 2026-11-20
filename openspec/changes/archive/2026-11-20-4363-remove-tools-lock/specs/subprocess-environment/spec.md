## MODIFIED Requirements

### Requirement: A key that only contains a refused name reaches the child
`build_subprocess_env` SHALL put a key of the caller override in the child environment with its value when the key only contains a refused file-write name, or contains `LD_` after its first characters, with isolation on and off. `SSL_CERT_FILE` and `NODE_EXTRA_CA_CERTS` are examples of keys that write no file. `npm_config_cache` also makes npm write files and stays accepted, because a caller sets it.

#### Scenario: Keys with a similar name
- **WHEN** a caller builds a child environment with the overrides `SSL_CERT_FILE`, `NODE_EXTRA_CA_CERTS`, `EXAMPLE_SSLKEYLOGFILE`, `QLOGDIR_EXAMPLE`, `BUILD_ID`, `OLD_LD_EXAMPLE`, `EXAMPLE_PYTEST_ADDOPTS` and `npm_config_logs_dirs`
- **THEN** the child environment holds each of these keys with its value
