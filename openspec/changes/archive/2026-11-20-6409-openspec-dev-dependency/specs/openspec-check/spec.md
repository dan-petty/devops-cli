## RENAMED Requirements

- FROM: `### Requirement: The gate reads the version of the command on PATH`
- TO: `### Requirement: The gate reads the version of the binary that it runs`

## MODIFIED Requirements

### Requirement: The gate reads the version of the binary that it runs
`devops openspec check` SHALL run `openspec --version` before its other checks and SHALL report one problem naming the printed version, the locked version, the command path and `npm ci --ignore-scripts` when the printed version differs from the `@fission-ai/openspec` version of the `package-lock.json` at the root of the checkout. When that lockfile is absent or pins no `@fission-ai/openspec`, the gate SHALL report one problem naming the lockfile and the package, and SHALL run no other check.

#### Scenario: An older command replaces the skill advice
- **WHEN** the `openspec` command prints `1.14.3`, the `package-lock.json` of the checkout pins another version, and a committed skill differs from a regeneration
- **THEN** the output holds `1.14.3`, the locked version and `npm ci --ignore-scripts`, holds no `regenerate`, and the gate ran no `openspec update --force`

#### Scenario: The locked command keeps the skill check
- **WHEN** the `openspec` command prints the version that the `package-lock.json` of the checkout pins and a committed skill differs from a regeneration
- **THEN** the output holds the skill path and `uv run devops openspec regenerate`

#### Scenario: The lockfile of the checkout moves the pin
- **WHEN** the `openspec` command prints the version of the old pin and the `package-lock.json` of the checkout pins `9.9.9`
- **THEN** the gate reports one `version` problem that names both versions and `package-lock.json`, and runs no `openspec update --force`

#### Scenario: A checkout with no lockfile
- **WHEN** the checkout has no `package-lock.json`
- **THEN** the gate reports one `version` problem that names `package-lock.json` and `@fission-ai/openspec`, and runs no `openspec update --force`

## ADDED Requirements

### Requirement: The gate runs the OpenSpec that npm installed in the checkout
`devops openspec check`, `devops openspec regenerate`, `devops openspec archive`, `devops openspec new` and `devops roadmap plan-check` SHALL run `node_modules/.bin/openspec` of the checkout when that file exists, in place of the `openspec` on PATH, and the version problem SHALL name its path. With no such file, they SHALL run the `openspec` on PATH.

#### Scenario: The project install runs with no openspec on PATH
- **WHEN** the checkout holds `node_modules/.bin/openspec` and PATH resolves no `openspec`
- **THEN** `check_openspec` passes the tree, and each `openspec` run started `node_modules/.bin/openspec` of the checkout

#### Scenario: The version problem names the project install
- **WHEN** the checkout holds `node_modules/.bin/openspec`, PATH resolves another `openspec`, and the binary prints `1.14.3`
- **THEN** the version problem names the path of `node_modules/.bin/openspec` of the checkout and not the path on PATH
