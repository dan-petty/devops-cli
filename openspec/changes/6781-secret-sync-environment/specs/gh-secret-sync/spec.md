## Purpose
How `devops gh secret sync` seals GitHub Actions secrets: it reads the public key of the repository or of one environment, seals each value with a PyNaCl sealed box, sends the sealed body on stdin, and never shows a value in output, logs, traces or error text.

## ADDED Requirements

### Requirement: Secret sync writes into the scope that the command names
`devops gh secret sync` SHALL read the public key and put each sealed secret under `repos/{repo}/actions/secrets` when no `--env` is given, and under `repos/{repo}/environments/{env}/secrets` when `--env <env>` is given. The command SHALL encode the environment name for the URL, so a slash becomes `%2F`. The PUT body SHALL hold only `encrypted_value` and `key_id`, and the command SHALL send it on stdin.

#### Scenario: A secret of an environment
- **WHEN** a person runs `devops gh secret sync -n RELEASE_APP_PRIVATE_KEY -R owner/repo --env release` and the keyring holds a value for `RELEASE_APP_PRIVATE_KEY`
- **THEN** the command reads `repos/owner/repo/environments/release/secrets/public-key`
- **AND** it sends `PUT repos/owner/repo/environments/release/secrets/RELEASE_APP_PRIVATE_KEY` with a body on stdin that the private key of the environment opens to the value
- **AND** it calls no route under `repos/owner/repo/actions/secrets`

#### Scenario: An environment name with a slash
- **WHEN** a person runs `devops gh secret sync -n TOKEN -R owner/repo --env prod/eu`
- **THEN** each route of the command starts with `repos/owner/repo/environments/prod%2Feu/secrets`

#### Scenario: An environment that does not exist
- **WHEN** GitHub answers the public key request of the environment with 404
- **THEN** the command exits 1 with an error that names the environment, and it sends no PUT

### Requirement: A file gives the value of one secret
With `--from-file <path>`, or `--from-file -` for stdin, `devops gh secret sync` SHALL read the value of the one secret that `--secret-names` names from the input, and not from `--source`. The input SHALL keep the limits of `devops config set --from-file`: at most 64 KiB of UTF-8 text that is not empty, with every line as the input has it.

#### Scenario: A value from a file
- **WHEN** a person runs `devops gh secret sync -n RELEASE_APP_PRIVATE_KEY -R owner/repo --env release --from-file key.pem`
- **THEN** the sealed body opens to the text of `key.pem`, with its last newline
- **AND** the row of the secret names the source `file`

### Requirement: Secret sync refuses a file with a second source of values
`devops gh secret sync` SHALL refuse `--from-file` with more than one secret name, and with `--source vault`. It SHALL exit 2 before it reads a value or sends a request.

#### Scenario: A file for two secrets
- **WHEN** a person runs `devops gh secret sync -n A,B -R owner/repo --from-file key.pem`
- **THEN** the command exits 2 and starts no process

#### Scenario: A file and Vault
- **WHEN** a person runs `devops gh secret sync -n A -R owner/repo --source vault --from-file key.pem`
- **THEN** the command exits 2 and starts no process

### Requirement: No secret value reaches output, logs, traces or error text
`devops gh secret sync` SHALL keep each value in memory between its source and the seal. The output, the arguments and the stdin of each `gh` call, the Python log records, the exported spans and log records, and the text of each error SHALL NOT hold the value.

#### Scenario: A known test value
- **WHEN** a test seals the known value `known-test-value-6781` into an environment, once with an accepted upload and once with a rejected one
- **THEN** no output, no argument or stdin of a `gh` call, no log record and no exported span or log record holds `known-test-value-6781`

### Requirement: The dry run of an environment sync sends no request
`devops gh secret sync --env <env> --dry-run` SHALL print the planned public key request and the planned PUT of each secret under `repos/{repo}/environments/{env}/secrets`, with placeholders for the sealed value and the key id. It SHALL read no keyring, no Vault and no file content, and it SHALL start no process.

#### Scenario: A dry run of an environment
- **WHEN** a person runs `devops gh secret sync -n TOKEN -R owner/repo --env release --dry-run`
- **THEN** the command exits 0 and prints `repos/owner/repo/environments/release/secrets/public-key` and `repos/owner/repo/environments/release/secrets/TOKEN`
- **AND** it starts no process
