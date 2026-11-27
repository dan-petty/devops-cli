# cluster-secrets-loader Specification

## Purpose
The cluster Secrets loader reads `cluster-secrets.toml` into existing frozen dataclasses and combines environment rows with product rows.

## Requirements

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

### Requirement: Push-secrets reads the environment file of the tree
The cluster Secret table SHALL be the rows of `cluster-secrets.toml` of the environment tree, then the product rows. A command that needs the table of a tree with no such file SHALL stop with a `ConfigurationError` that names the file, `--k8s-dir` and `infra.repos`, and MUST NOT read another file in its place.

#### Scenario: A fixture environment tree
- **WHEN** `devops k8s push-secrets --dry-run` runs with `--k8s-dir` at a fixture environment tree
- **THEN** the plan holds each fixture row and each product row

#### Scenario: A tree with no Secret table
- **WHEN** `devops k8s push-secrets` runs with `--plan` or `--dry-run` on a tree with no `cluster-secrets.toml`, also in a checkout that holds `tests/fixtures/cluster-secrets.toml`
- **THEN** it exits non-zero and names `cluster-secrets.toml`, `--k8s-dir` and `infra.repos`

#### Scenario: A deploy reads the table before the cluster
- **WHEN** `devops k8s deploy-stack --stack llm` runs with a push on a tree with no `cluster-secrets.toml`
- **THEN** it exits 1 and starts no `kubectl` and no `helm`

### Requirement: A command that needs only product rows needs no environment tree
`devops config set <key> --generate` for a key that a product row generates, and `devops k8s bootstrap-roadmap-key`, SHALL read the product rows only. `--generate` for another key SHALL read the table of the environment tree.

#### Scenario: A product key with no tree
- **WHEN** `devops config set crawl4ai.api_token --generate` runs with no environment tree
- **THEN** it stores the token

#### Scenario: An environment key with no tree
- **WHEN** `devops config set grafana.password --generate` runs with no environment tree
- **THEN** it exits non-zero, stores nothing and names `--k8s-dir`

### Requirement: An optional feature Secret is in the Secret table
`OPTIONAL_FEATURE_SECRETS` SHALL name `monitoring/grafana-image-renderer`, so a missing renderer token stops only panel images. `k8s/README.md` SHALL say that a pull request which adds a Secret reference names the push command as its first line.

#### Scenario: The list and the table
- **WHEN** a test reads `OPTIONAL_FEATURE_SECRETS` and the table of the fixture environment tree
- **THEN** each name of the list is a Secret of the table

### Requirement: The product Secret table holds no key of the object store
`CLUSTER_SECRETS` SHALL hold no row whose name starts with `object-store-`. The key pair of a writer comes from an ESO `Password` generator of the tenant chart, not from the keyring.

#### Scenario: The product rows
- **WHEN** a test reads `CLUSTER_SECRETS` in `src/devops_cli/k8s/cluster_secrets.py`
- **THEN** no row has a name that starts with `object-store-`

### Requirement: The product Secret table holds the infra SSH key
`CLUSTER_SECRETS` SHALL hold Secret `devops/infra-ssh-key` of stack `devops` with one optional key, `id_ed25519`, read from the keyring entry `infra_ssh_private_key` of the managed credential `infra.ssh_private_key`, with no generator and no workload to restart. A push SHALL write the keyring value with no line added or removed.

#### Scenario: The plan names the Secret and its key
- **WHEN** `devops k8s push-secrets --only devops/infra-ssh-key --plan` runs with the private key in the keyring and no live Secret
- **THEN** it prints `devops/infra-ssh-key: id_ed25519 (keyring infra_ssh_private_key) would create; would restart: none`, prints no line of the key, runs only `kubectl get`, and writes nothing

#### Scenario: The push keeps the last newline
- **WHEN** `devops k8s push-secrets --only devops/infra-ssh-key` runs with a private key whose last line ends with a newline
- **THEN** key `id_ed25519` of the Secret holds the same text with its last newline, and no workload restarts

#### Scenario: A push with no key
- **WHEN** `devops k8s push-secrets --only devops/infra-ssh-key` runs and the keyring and the cluster hold no value for the key
- **THEN** it exits 0, writes no Secret, and warns with the command `devops config set infra.ssh_private_key`
