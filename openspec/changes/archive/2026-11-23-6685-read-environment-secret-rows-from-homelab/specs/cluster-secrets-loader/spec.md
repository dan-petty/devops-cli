# cluster-secrets-loader Specification

## Purpose
The cluster Secrets loader reads `cluster-secrets.toml` into existing frozen dataclasses and combines environment rows with product rows.

## ADDED Requirements

### Requirement: File rows load into existing dataclasses
The loader SHALL build the existing `ClusterSecret` dataclasses from `cluster-secrets.toml`.

#### Scenario: One row of each source kind
- **WHEN** the test `tests/k8s/test_cluster_secrets_file.py` loads `tests/fixtures/cluster-secrets.toml` with one keyring, setting, literal and derived row
- **THEN** each loaded object equals the equal `ClusterSecret` Python row and `uv run pytest tests/k8s -q -k cluster_secret` passes.

### Requirement: Generator and adopt_from tables load
The file model SHALL read the generator and `adopt_from` tables for each row.

#### Scenario: A generated row and an adopted row
- **WHEN** the fixture file holds a generator table and an `adopt_from` table
- **THEN** the loaded `SecretEntry` has the same `SecretGenerator` and `SecretKeyRef` as the equal Python row, and `uv run pytest tests/k8s -q -k cluster_secret` passes.

### Requirement: Environment rows removed from code
The module `src/devops_cli/k8s/cluster_secrets.py` MUST contain no environment Secret rows after the change.

#### Scenario: No moved stack rows remain
- **WHEN** the test `tests/k8s/test_cluster_secret_source.py` runs `git grep -n -E 'stack=(BASE_STACK|"(chat|gitea|infra)")' src/`
- **THEN** the command finds no match, and `git grep -n 'name="valkey-' src/devops_cli/k8s/cluster_secrets.py` finds only `valkey-devops-auth` and `valkey-runs-auth`.

### Requirement: Push-secrets uses the environment file
`devops k8s push-secrets` MUST load the environment rows from `cluster-secrets.toml` and append the product rows.

#### Scenario: A fixture environment tree
- **WHEN** the test `tests/k8s/test_cluster_secret_push.py` runs with `--k8s-dir` pointing at a fixture environment tree
- **THEN** the plan contains each fixture row and each product row, and `uv run pytest tests/k8s -q -k cluster_secret` passes.
