## ADDED Requirements

### Requirement: A refused backend URL keeps its credentials out of the sweep
When the throughput sweep refuses a backend URL that is not an http or https URL with a host, the error text that the sweep records SHALL name no part of the URL.

#### Scenario: A URL with a password and a query token
- **WHEN** `run_level` gets the URL `ftp://user:s3cr3t@example.com/x?token=t0k3n`
- **THEN** the level counts one error, and its `last_error` starts with `ValueError: ` and holds neither `s3cr3t` nor `t0k3n`
