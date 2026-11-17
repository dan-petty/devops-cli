## MODIFIED Requirements

### Requirement: No upgrade task runs until the token is out of its reach
A `postUpgradeTasks` command runs in the container that can read the installation token (#6020). Until #6020 keeps the token away from the tasks, `allowedCommands` SHALL be empty, the Renovate config of this repository SHALL name no `postUpgradeTasks`, and `allowShellExecutorForPostUpgradeCommands` SHALL be false. A group that needs a task SHALL name its commands in `prBodyNotes`.

#### Scenario: A new command
- **WHEN** a person runs `kubectl -n devops get configmap renovate-config -o yaml` on the cluster before #6020
- **THEN** `allowedCommands` is empty, so Renovate runs no `postUpgradeTasks` command
