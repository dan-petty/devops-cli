## MODIFIED Requirements

### Requirement: The Secret row holds the two IDs and the key under their variables
The cluster secrets file of the environment tree of dan-petty/homelab SHALL hold `devops/renovate`, an optional-feature Secret of stack `devops` with no restart, and its three optional keys under their variables. The product table of devops-cli SHALL hold no such row. The token container SHALL take the Secret as optional, and the `homelab` AppProject SHALL ignore Secret `renovate`.

#### Scenario: The push
- **WHEN** a person runs `uv run devops k8s push-secrets --stack devops --dry-run` and `kubectl -n argocd get applications -o jsonpath='{..conditions[*].type}'`
- **THEN** the dry run writes Secret `devops/renovate` with the keys `DEVOPS_CLI_RENOVATE_GITHUB_APP_ID`, `DEVOPS_CLI_RENOVATE_GITHUB_APP_INSTALLATION_ID` and `DEVOPS_CLI_RENOVATE_GITHUB_APP_PRIVATE_KEY` and no restart, with no value in the output, and no Application of project `homelab` has the condition `OrphanedResourceWarning` for Secret `renovate`.

#### Scenario: A workstation with no Renovate settings
- **WHEN** `devops k8s push-secrets --stack devops` runs with no Renovate setting and no keyring entry
- **THEN** the push skips the three keys with a warning, writes no Secret `renovate`, and exits 0.
