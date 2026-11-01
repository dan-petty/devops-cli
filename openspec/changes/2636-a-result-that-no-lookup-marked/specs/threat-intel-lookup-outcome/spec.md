## ADDED Requirements

### Requirement: NetworkReference security_status is required
NetworkReference.security_status SHALL have no default value.

#### Scenario: Construct without security_status
- **WHEN** A producer constructs NetworkReference without setting security_status
- **THEN** Pydantic raises a ValidationError

### Requirement: PackageLookupResult status is required
PackageLookupResult.status SHALL have no default value.

#### Scenario: Construct without status
- **WHEN** A producer constructs PackageLookupResult without setting status
- **THEN** Pydantic raises a ValidationError

### Requirement: No intel result model defaults to a clean status
The models package SHALL NOT offer a result model whose fields default to a clean security status. NetworkIntelResult and PackageIntelResult SHALL NOT be importable from devops_cli.models and SHALL NOT be listed in devops_cli.models.__all__.

#### Scenario: Import a removed intel result model
- **WHEN** A consumer attempts to import NetworkIntelResult or PackageIntelResult from devops_cli.models
- **THEN** The import raises ImportError

#### Scenario: Read the exports
- **WHEN** A consumer reads devops_cli.models.__all__
- **THEN** The list contains neither NetworkIntelResult nor PackageIntelResult
