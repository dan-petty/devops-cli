## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Push-secrets uses the environment file
**Reason**: The loader reads no fixture file in place of a missing `cluster-secrets.toml` (#7214, #7290).
**Migration**: Give the environment tree with `--k8s-dir` or `infra.repos`.
