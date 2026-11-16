## RENAMED Requirements

- FROM: `### Requirement: Each repository command has an anchored regex and runs in no shell`
- TO: `### Requirement: No upgrade task runs until the token is out of its reach`

- FROM: `### Requirement: The caches are on a kept claim, and the first runs are a lookup dry run`
- TO: `### Requirement: The caches are on a kept claim, and Renovate opens update pull requests`

## MODIFIED Requirements

### Requirement: No upgrade task runs until the token is out of its reach
A `postUpgradeTasks` command runs in the container that can read the installation token (#6020). Until #6020 keeps the token away from the tasks, `allowedCommands` SHALL be empty, the Renovate config of this repository SHALL name no `postUpgradeTasks`, and `allowShellExecutorForPostUpgradeCommands` SHALL be false. A group that needs a task SHALL name its commands in `prBodyNotes`.

#### Scenario: A new command
- **WHEN** a pull request adds a `postUpgradeTasks` command or an `allowedCommands` regex before #6020
- **THEN** the test fails and names the command

### Requirement: The caches are on a kept claim, and Renovate opens update pull requests
The config SHALL set `binarySource: install`, `cacheDir` on PVC `renovate-cache` (`local-path`, 5Gi, ReadWriteOnce, `Prune=false,Delete=false`), `containerbaseDir` under it, `repositoryCache: enabled`, `reportType: file` and `persistRepoData: false`. The container SHALL set no `RENOVATE_DRY_RUN`: the first measured run (#4909) was a lookup dry run, and Renovate now opens update pull requests.

#### Scenario: The cache and the dry run
- **WHEN** a test reads the config, the PVC and the env of `renovate`
- **THEN** each value above is set, and the env has no `RENOVATE_DRY_RUN`
