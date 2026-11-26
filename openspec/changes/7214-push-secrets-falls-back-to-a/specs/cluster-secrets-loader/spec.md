## MODIFIED Requirements

### Requirement: Push-secrets uses the environment file
`devops k8s push-secrets` and `devops k8s deploy-stack` MUST load the environment Secret rows from the cluster secrets file of the environment tree, resolved from `--k8s-dir`, else from the project profile, else from the one infra repo, and append the product rows. When that tree holds no cluster secrets file, the load MUST raise `ConfigurationError` with a message that names the missing path. Product code SHALL read no Secret table under `tests/fixtures`.

#### Scenario: A fixture environment tree
- **WHEN** the test `tests/k8s/test_cluster_secret_push.py` runs with `--k8s-dir` pointing at a fixture environment tree
- **THEN** the plan contains each fixture row and each product row, and `uv run pytest tests/k8s -q -k cluster_secret` passes.

#### Scenario: Running in an installed package environment
- **WHEN** `load_cluster_secrets_table` runs in an installed release whose environment tree holds no cluster secrets file
- **THEN** the call raises the configuration error and its message names the path of the missing file, so the command exits non-zero and skips no environment Secret.
