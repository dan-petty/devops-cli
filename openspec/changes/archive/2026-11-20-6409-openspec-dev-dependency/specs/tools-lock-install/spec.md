## REMOVED Requirements

### Requirement: The check reads the version the openspec command prints
**Reason**: OpenSpec is a devDependency of the root `package.json`, and `package-lock.json` pins it (#6409). `tools.lock` holds no OpenSpec entry, so `devops install-tools` reads the version of no command.
**Migration**: `npm ci --ignore-scripts` installs OpenSpec, and `devops openspec check` compares the version of the binary that it runs with `package-lock.json`.

### Requirement: Only-missing installs openspec when PATH holds another version
**Reason**: `tools.lock` holds no OpenSpec entry, so `devops install-tools` installs no OpenSpec (#6409).
**Migration**: `npm ci --ignore-scripts` at the root of the checkout installs the OpenSpec of `package-lock.json`.

## ADDED Requirements

### Requirement: The check judges each tool by its link
`devops install-tools --check` SHALL report each tool whose commands in the target directory do not link to its locked version, SHALL exit 1 when it reports one, and SHALL make no request.

#### Scenario: A tool off its pin
- **WHEN** every tool of the lock but `k9s` and `semgrep` links to its locked version in the target directory and PATH is empty
- **THEN** the check names `k9s` and `semgrep`, exits 1 and makes no request, and exits 0 after both link to their locked versions
