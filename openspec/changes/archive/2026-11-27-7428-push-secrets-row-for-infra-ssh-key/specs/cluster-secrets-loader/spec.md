## ADDED Requirements

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
