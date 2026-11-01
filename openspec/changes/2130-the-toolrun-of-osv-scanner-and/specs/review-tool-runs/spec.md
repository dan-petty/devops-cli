## ADDED Requirements

### Requirement: osv-scanner toolrun records database digest
The ToolRun of an osv-scanner run SHALL record a `database_digest` field that is a SHA-256 hex digest computed by streaming the advisory database files in sorted filename order. The digest SHALL change when the database content changes and SHALL stay the same when it does not.

#### Scenario: digest changes when database changes
- **WHEN** the advisory database files differ between two osv-scanner runs
- **THEN** the `database_digest` in the two ToolRun records is different

#### Scenario: digest stable for unchanged database
- **WHEN** the advisory database files are identical between two osv-scanner runs
- **THEN** the `database_digest` in the two ToolRun records is the same

### Requirement: ruff toolrun records configuration digest
The ToolRun of a Ruff run SHALL record a `config_digest` field that is a SHA-256 hex digest of the resolved configuration that Ruff used for the target. The digest SHALL change when the resolved configuration changes and SHALL stay the same when it does not.

#### Scenario: digest changes when configuration changes
- **WHEN** the Ruff configuration of the target differs between two Ruff runs
- **THEN** the `config_digest` in the two ToolRun records is different

#### Scenario: digest stable for unchanged configuration
- **WHEN** the Ruff configuration of the target is identical between two Ruff runs
- **THEN** the `config_digest` in the two ToolRun records is the same
