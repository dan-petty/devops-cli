## ADDED Requirements

### Requirement: A Valkey client sends the user that valkey.username names
`valkey.username` SHALL name the ACL user that a Valkey client sends, and `DEVOPS_CLI_VALKEY_USER` SHALL replace it. An unset or empty `valkey.username` SHALL send no user, so the server answers as its default user. The cache tier SHALL send the user and the password of `valkey.password` in one authentication.

#### Scenario: Settings declaration
- **WHEN** The test `tests/security/test_config_declarations.py` reads the Settings declarations
- **THEN** `valkey.username` is declared, its variable is `DEVOPS_CLI_VALKEY_USER`, and its default is empty

#### Scenario: The cache tier sends the user
- **WHEN** The test `tests/valkey/test_valkey_cache_tier.py` builds the credential provider over settings with `valkey.username` set to `sweep` and a password
- **THEN** The provider returns `sweep` and the password

#### Scenario: An empty user keeps the default user
- **WHEN** The test `tests/valkey/test_valkey_cache_tier.py` builds the credential provider over settings with `valkey.username` unset and a password
- **THEN** The provider returns the password alone
