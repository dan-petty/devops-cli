## MODIFIED Requirements

### Requirement: The Secret row holds the two IDs and the key under their variables
The cluster secret table SHALL hold `devops/renovate`, an optional-feature Secret in stack `devops` with no restart, and three optional keys: the variables of `renovate.github_app_id` and `renovate.github_app_installation_id` from their settings, and of `renovate.github_app_private_key` from its keyring entry. The token container SHALL take it as optional.

#### Scenario: The push
- **WHEN** a person runs `uv run devops k8s push-secrets --stack devops --dry-run`
- **THEN** the dry run writes Secret `devops/renovate` with the keys `DEVOPS_CLI_RENOVATE_GITHUB_APP_ID`, `DEVOPS_CLI_RENOVATE_GITHUB_APP_INSTALLATION_ID` and `DEVOPS_CLI_RENOVATE_GITHUB_APP_PRIVATE_KEY` and no restart, with no value in the output

#### Scenario: A workstation with no Renovate settings
- **WHEN** `devops k8s push-secrets --stack devops` runs with no Renovate setting and no keyring entry
- **THEN** the push skips the three keys with a warning, writes no Secret `renovate`, and exits 0
