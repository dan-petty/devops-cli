## MODIFIED Requirements

### Requirement: ssh-request-plans
The commands `ssh register` and `ssh rotate` SHALL carry the `request-plan` dry-run class and SHALL expose `--dry-run`. A dry run SHALL make no request to GitHub, start no process, and print the requests of the real run in order. A dry run of `ssh rotate` for a prefix that is not the project prefix SHALL list no GitHub key request and no `git config` command.

#### Scenario: Dry run on ssh register
- **WHEN** user executes `devops ssh register --dry-run` and `devops --dry-run ssh register`
- **THEN** `github_api` receives no request, no process starts, and the output lists `POST /user/keys` and `POST /user/ssh_signing_keys` with the key as a placeholder, the listing of each endpoint with the condition that the `POST` answers HTTP 422, and the `git config` commands that point git signing at the key

#### Scenario: Dry run on ssh rotate
- **WHEN** user executes `devops ssh rotate --dry-run`
- **THEN** no key file is written, `github_api` receives no request, and the output lists the same requests with the condition that the key is old enough or `--force` is set

#### Scenario: The plan matches the real run
- **WHEN** a test runs `devops ssh register` against `github_api` routes that accept both keys, and compares the requests that it received with the plan lines that have no condition
- **THEN** the methods and the paths are the same, in the same order

#### Scenario: Dry run of a host-only prefix
- **WHEN** a test runs `devops ssh rotate --prefix alpha --dry-run` with `ssh.key_prefix` set to `devops-cli`
- **THEN** the output lists no `POST /user/keys`, no `POST /user/ssh_signing_keys` and no `git config` command, and holds the line that tells the person to put the public key on the hosts
