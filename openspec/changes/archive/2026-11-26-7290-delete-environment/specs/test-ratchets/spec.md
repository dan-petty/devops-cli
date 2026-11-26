## MODIFIED Requirements

### Requirement: No new test reads a committed manifest or config file
The `test-tree` row of `devops ci` SHALL find each test that reads a committed manifest or config file: through a path built from `REPO_ROOT`, a relative `Path`, or a path reader of its module, and through a module-level constant, helper or fixture that reads one. For each test module, the count of such tests SHALL equal the count in `tests/gate/tree_checks/config_reads.toml`, and a count SHALL only fall (#6060).

#### Scenario: A new test reads a manifest
- **WHEN** a test module adds a test that reads a file under `k8s/` through a helper of the module
- **THEN** the count of the module passes its entry, and the check fails and names the module and docs/TESTING.md

#### Scenario: A test that read config goes
- **WHEN** a test that read a committed config file is deleted, and its module keeps its entry
- **THEN** the count of the module is below its entry, and the check fails until the entry is lowered

#### Scenario: A path under tmp_path
- **WHEN** a test builds a `k8s` folder under `tmp_path` and reads it
- **THEN** the check does not count the test
