## Purpose

How `devops gh app-token --app renovate --write <path>` writes an installation token of the GitHub App that self-hosted Renovate acts as to a file: the settings it reads, the request it sends, the file it writes, and what its output and its dry run show.

## ADDED Requirements

### Requirement: The Renovate token asks for exactly the Renovate permissions
`devops gh app-token --app renovate --write <path>` SHALL send one `POST /app/installations/<renovate.github_app_installation_id>/access_tokens` whose body names exactly administration, checks, statuses, contents, vulnerability_alerts, issues, metadata, pull_requests and workflows, at the levels of the Renovate App. The App's private key SHALL sign the JWT, and its issuer SHALL be `renovate.github_app_id` as given: an App ID or a Client ID.

#### Scenario: The App ID in a variable
- **WHEN** the variables give App ID `1001`, installation `42` and an RSA key, and GitHub answers with a token
- **THEN** the command exits 0, sends one request whose body is `{"permissions": ...}` with the 9 permissions, and the JWT that the key signs has the issuer `1001`

#### Scenario: The Client ID in a variable
- **WHEN** `DEVOPS_CLI_RENOVATE_GITHUB_APP_ID` is `Iv23liExampleClient01`
- **THEN** the JWT has the issuer `Iv23liExampleClient01`

#### Scenario: The App ID as a number in the config file
- **WHEN** the config file sets `renovate.github_app_id` to the number 1001 and no variable sets it
- **THEN** the JWT has the issuer `1001`

### Requirement: The token file has mode 0600 and holds only the token
The command SHALL write the token, with no newline, to a new file with mode 0600 that replaces `<path>`.

#### Scenario: A file that other users can read
- **WHEN** `<path>` holds `old` with mode 0644 and GitHub answers with a token
- **THEN** `<path>` holds only the token and has mode 0600

### Requirement: The token is in no output and no log line
The command SHALL print the path and the time when GitHub ends the token. The token SHALL be in no stdout, no stderr and no log record.

#### Scenario: A written token
- **WHEN** the command writes a token, and the log is read at level DEBUG
- **THEN** stdout, stderr and each log record hold no token, and the output names the path and `GitHub ends the token at`

### Requirement: The dry run sends no request and shows the token as a placeholder
With `--dry-run` after the command or before `gh`, the command SHALL send no request, read no keyring entry and write no file. It SHALL show the request with its body, and `<installation-token>` as what a run writes to `<path>` with mode 0600.

#### Scenario: A dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** it exits 0, the GitHub fake and the keyring fake record no read, `<path>` does not exist, and the output holds `POST https://api.github.com/app/installations/42/access_tokens` and `<installation-token> to <path> with mode 0600`

### Requirement: A setting that is not set names the setting and its variable
When `renovate.github_app_id`, `renovate.github_app_installation_id` or `renovate.github_app_private_key` is not set, the command SHALL exit 1 with an error that names each such setting and its variable, and SHALL send no request and write no file.

#### Scenario: One setting is not set
- **WHEN** one of the three variables is not set, and the keyring and the config file do not set it
- **THEN** the command exits 1, the output holds `these settings are not set: <setting>.` and the variable, no request is sent, and `<path>` does not exist

### Requirement: A refused permission names each permission and writes no file
When GitHub refuses the exchange, the command SHALL exit 1, name the App's bot `dan-petty-renovate[bot]` and GitHub's reason, and write no file. For HTTP 422, the error SHALL name each permission that the token asks for.

#### Scenario: GitHub answers HTTP 422
- **WHEN** GitHub answers the exchange with HTTP 422
- **THEN** the command exits 1, the output holds `GitHub App dan-petty-renovate[bot] has no installation token` and `vulnerability_alerts (read)`, and `<path>` does not exist
