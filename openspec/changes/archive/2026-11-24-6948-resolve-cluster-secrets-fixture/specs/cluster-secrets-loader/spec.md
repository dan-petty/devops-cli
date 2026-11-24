# cluster-secrets-loader Specification

## MODIFIED Requirements

### Requirement: Push-secrets uses the environment file
`devops k8s push-secrets` MUST load the environment rows from `cluster-secrets.toml` and append the product rows. When running in a repository checkout where the environment root lacks `cluster-secrets.toml`, the loader SHALL resolve the fixture file `tests/fixtures/cluster-secrets.toml` from the repository root when running from either source or an installed package.

#### Scenario: A fixture environment tree
- **WHEN** the test `tests/k8s/test_cluster_secret_push.py` runs with `--k8s-dir` pointing at a fixture environment tree
- **THEN** the plan contains each fixture row and each product row, and `uv run pytest tests/k8s -q -k cluster_secret` passes.

#### Scenario: Running in an installed package environment
- **WHEN** `load_cluster_secrets_table()` runs from an installed package where `__file__` is in site-packages and the working directory is inside a repository checkout
- **THEN** the loader locates `tests/fixtures/cluster-secrets.toml` and returns all 23 cluster secret rows.
