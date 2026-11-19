## MODIFIED Requirements

### Requirement: Only the token init container reads Secret renovate
Init container `token` SHALL run the Service image with the args `gh app-token --app renovate --write /token/github-token`, and SHALL be the only container with `envFrom` (optional) or a `secretKeyRef`. No volume SHALL be a Secret. Container `renovate` SHALL mount the volume `token` writable, and `config.js` SHALL read `/token/github-token` into the config and remove that file before it exports the config, so a child process of user 12021 finds no token file.

#### Scenario: A container reads the Secret
- **WHEN** a person runs `kubectl get cronjob renovate -o yaml` in namespace `devops` on the cluster
- **THEN** init container `token` is the only container with `envFrom` or a `secretKeyRef`, no volume is a Secret, and container `renovate` mounts the volume `token` with no `readOnly: true`, and `uv run devops gh pr list --state all` lists the pull requests that the last run opened with the token that the init container wrote

#### Scenario: A config that keeps the token
- **WHEN** `uv run devops ci --check --only k8s` runs against a `config.js` that reads `/token/github-token` and does not remove it
- **THEN** the row exits non-zero and its message names `/token/github-token`

### Requirement: A post-upgrade task cannot open the installation token
A `postUpgradeTasks` command SHALL run as user 12021 in container `renovate` and SHALL open no `/token/github-token`, because `config.js` reads that file into the Renovate config and removes it before Renovate processes a repository. `allowShellExecutorForPostUpgradeCommands` SHALL stay false, and `allowedCommands` SHALL hold only an anchored regex for each command that `.github/renovate.json` names, so a command with no regex runs nowhere.

#### Scenario: A new command
- **WHEN** a person runs `kubectl get configmap renovate-config -o yaml` in namespace `devops` on the cluster
- **THEN** `allowedCommands` holds only anchored regexes and `allowShellExecutorForPostUpgradeCommands` is false, so Renovate runs no command that no regex matches and no command in a shell

#### Scenario: The token path after the config runs
- **WHEN** `uv run devops ci test tests/invariants/test_k8s_renovate.py` runs the `config.js` of ConfigMap `renovate-config` with `DEVOPS_CLI_TOKEN_FILE` at a temporary path and then starts a `node` child process that opens that path
- **THEN** the child exits non-zero with `ENOENT`, because the script removed the file before the child started

## RENAMED Requirements

- FROM: `### Requirement: No upgrade task runs until the token is out of its reach`
- TO: `### Requirement: A post-upgrade task cannot open the installation token`
