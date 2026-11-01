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

### Requirement: NetworkIntelResult is removed
NetworkIntelResult SHALL not exist in the models package, and devops_cli.models.__all__ SHALL not list it.

#### Scenario: Import NetworkIntelResult
- **WHEN** A consumer attempts to import NetworkIntelResult from devops_cli.models
- **THEN** The import raises ImportError

#### Scenario: Read the exports for NetworkIntelResult
- **WHEN** A consumer reads devops_cli.models.__all__
- **THEN** The list does not contain NetworkIntelResult

### Requirement: PackageIntelResult is removed
PackageIntelResult SHALL not exist in the models package, and devops_cli.models.__all__ SHALL not list it.

#### Scenario: Import PackageIntelResult
- **WHEN** A consumer attempts to import PackageIntelResult from devops_cli.models
- **THEN** The import raises ImportError

#### Scenario: Read the exports for PackageIntelResult
- **WHEN** A consumer reads devops_cli.models.__all__
- **THEN** The list does not contain PackageIntelResult
