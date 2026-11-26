## Purpose
How a devops-cli process reaches `valkey-roadmap`, the Valkey of the shared state of the roadmap jobs: the settings that name the store, its ACL user and the credential of that user, and the one tier of a process that sends them and fails soft (ADR 0023 section 2).

## ADDED Requirements

### Requirement: Settings name the roadmap state store, its user and its password
The setting `roadmap.state.url` SHALL name the Valkey endpoint of the roadmap state, with the variable `DEVOPS_CLI_ROADMAP_STATE_URL`. The setting `roadmap.state.username` SHALL name the ACL user that a client sends, with the variable `DEVOPS_CLI_ROADMAP_STATE_USER`. The credential `roadmap.state.password` SHALL hold the password of that user, with the variable `DEVOPS_CLI_ROADMAP_STATE_PASSWORD` and the keyring entry `roadmap_state_password`. Each of the three SHALL have no default value.

#### Scenario: Variables set the settings
- **WHEN** a test sets `DEVOPS_CLI_ROADMAP_STATE_URL` to `valkey://example.com:6379/0` and `DEVOPS_CLI_ROADMAP_STATE_USER` to `brain`, and loads the settings
- **THEN** `roadmap.state.url` and `roadmap.state.username` hold these values, the three options name their variables, and settings with no source hold no URL and no user

### Requirement: The tier of the roadmap state sends the user and the password of its settings
`roadmap_state_tier()` SHALL give one `ValkeyCacheTier` for each process over the endpoint of `roadmap.state.url`. Its client SHALL authenticate with the user of `roadmap.state.username` and the password of `roadmap.state.password`, and never with the user or the password of `valkey.url`.

#### Scenario: The brain user
- **WHEN** a loopback listener records the commands, `roadmap.state.url` names it, `roadmap.state.username` is `brain`, `DEVOPS_CLI_ROADMAP_STATE_PASSWORD` holds a password, `valkey.username` is `sweep` and `DEVOPS_CLI_VALKEY_PASSWORD` holds another password, and a test reads one key through the tier
- **THEN** the listener gets `AUTH brain <the password of the roadmap state>` and then the `GET` of the key

#### Scenario: Two tiers in one process
- **WHEN** `valkey.url` and `roadmap.state.url` name two endpoints, and a test asks for both tiers
- **THEN** the cache tier dials the endpoint of `valkey.url`, the tier of the roadmap state dials the endpoint of `roadmap.state.url`, the two are not the same object, and a second call gives the same tier of the roadmap state

### Requirement: A reader of the roadmap state fails soft
A read through the tier SHALL give a miss, and a write SHALL NOT occur, with no error, while the store does not answer. With no `roadmap.state.url`, `roadmap_state_tier()` SHALL give no tier and write no warning. With a `roadmap.state.url` that is not valid, it SHALL give no tier and log one warning that names the setting.

#### Scenario: The store is down
- **WHEN** `roadmap.state.url` names a port that refuses each connection, and a test reads a key, reads a hash field and writes a key through the tier
- **THEN** the reads give no value, the write gives False, no error is raised, and the breaker of the tier is open after the first read

#### Scenario: No URL
- **WHEN** no source sets `roadmap.state.url`, and a test asks for the tier two times
- **THEN** both calls give no tier, and the log holds no warning

#### Scenario: A URL that is not valid
- **WHEN** `roadmap.state.url` is `valkey://example.com:99999`, and a test asks for the tier two times
- **THEN** both calls give no tier, and the log holds one warning that names `roadmap.state.url`
