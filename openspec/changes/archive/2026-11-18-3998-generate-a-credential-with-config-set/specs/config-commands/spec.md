## ADDED Requirements

### Requirement: devops config set --generate stores a declared credential
The generate option of the set command SHALL store a new value from the generator that the row of the cluster Secret table declares for the named credential, in the OS keyring, and SHALL print no part of the value.

#### Scenario: Generate the Crawl4AI token
- **WHEN** the person runs devops config set for crawl4ai.api_token with --generate, the keyring is unlocked and no token is stored
- **THEN** the keyring holds a new URL-safe value of 43 characters, and the output names crawl4ai.api_token and holds no part of the value

#### Scenario: The value reaches no argument, log or file
- **WHEN** the generate runs
- **THEN** no argument, log record or file of the run holds the value, and only the keyring entry does

### Requirement: The generator of a credential comes from the cluster Secret table
The command SHALL read the generator of a credential from the row of the cluster Secret table whose keyring source names that option, so `devops k8s push-secrets` and the generate option read one declaration per credential.

#### Scenario: The command and the push read one row
- **WHEN** a row of the cluster Secret table changes the encoding or the byte count of a generator
- **THEN** the generate makes the new value with no change to the command, and the test fails when an option that the command lists has no generator in the table

#### Scenario: The option list and the table agree
- **WHEN** the test walks the options that the command lists
- **THEN** the lookup of each of them returns the generator of that row, and the count of the options equals the count of the census

### Requirement: A credential with no declared generator is refused
The command MUST exit non-zero for a credential whose row declares no generator, MUST write nothing to the keyring, and MUST name the options that declare one.

#### Scenario: A typed credential has no generator
- **WHEN** the person runs devops config set for gemini.api_key with --generate
- **THEN** the command exits non-zero, writes nothing to the keyring, and names crawl4ai.api_token, mcp.token and qdrant.api_key among the options that declare a generator

### Requirement: A stored credential is kept unless the rotate flag is given
The command MUST NOT replace a value that the keyring already holds unless `--rotate` is given, and MUST name `--rotate` in the refusal.

#### Scenario: A token is already stored
- **WHEN** the person runs devops config set for crawl4ai.api_token with --generate while the keyring holds a token
- **THEN** the command exits non-zero, names --rotate, and the keyring keeps the stored token

### Requirement: The rotate flag replaces the stored credential
`--rotate` SHALL replace the stored value with a new value from the declared generator, and the command SHALL print no part of either value.

#### Scenario: Rotate the token
- **WHEN** the person runs devops config set for crawl4ai.api_token with --generate and --rotate while the keyring holds a token
- **THEN** the keyring holds a different value of the declared encoding and length, and the output holds no part of either value

### Requirement: The dry run of a generate writes nothing
`--generate --dry-run` MUST make no keyring read, no keyring write and no request.

#### Scenario: Dry run of a generate
- **WHEN** the person runs devops config set for crawl4ai.api_token with --generate and --dry-run
- **THEN** the command prints the generator encoding, its byte count and a masked placeholder, exits 0, and the keyring keeps its previous content

### Requirement: The generate flag refuses a value and a file
`--generate` with a VALUE or with `--from-file` MUST be a usage error that writes nothing.

#### Scenario: A typed value and the generate flag together
- **WHEN** the person runs devops config set for crawl4ai.api_token with --generate and a VALUE
- **THEN** the command exits non-zero with a usage error, names the two conflicting flags, and writes nothing

#### Scenario: A file and the generate flag together
- **WHEN** the person runs devops config set for crawl4ai.api_token with --generate and --from-file
- **THEN** the command exits non-zero with a usage error, names the two conflicting flags, and writes nothing

### Requirement: The rotate flag needs the generate flag
`--rotate` without `--generate` MUST be a usage error that writes nothing.

#### Scenario: Rotate without generate
- **WHEN** the person runs devops config set for crawl4ai.api_token with --rotate only
- **THEN** the command exits non-zero with a usage error, names --generate, and writes nothing
