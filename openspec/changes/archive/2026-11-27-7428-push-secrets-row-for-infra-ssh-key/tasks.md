# Tasks

## 1. Declare the infra SSH key credential

Kind: behavior.

Reads: `src/devops_cli/config/env.py`, `tests/security/test_config_declarations.py`.

Changes: `src/devops_cli/config/env.py`, `tests/security/test_config_declarations.py`, `tests/commands/test_config_audit_keys.py`, `docs/ENV_VARS.md`.

- [x] 1.1 Pin the credential `infra.ssh_private_key`, its keyring entry `infra_ssh_private_key` and its variable `DEVOPS_CLI_INFRA_SSH_PRIVATE_KEY` in the declaration tests, and watch them fail.
  - Verification: `$ uv run devops ci test tests/security/test_config_declarations.py tests/commands/test_config_audit_keys.py`
- [x] 1.2 Declare the credential in `CREDENTIALS` and regenerate the documents.
  - Verification: `$ uv run devops ci test tests/security/test_config_declarations.py tests/commands/test_config_audit_keys.py`

## 2. Add the Secret row

Kind: behavior.

Reads: `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/k8s/secret_push.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`.

Changes: `src/devops_cli/k8s/cluster_secrets.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`.

- [x] 2.1 Write the tests and watch them fail: the table holds `devops/infra-ssh-key` with the optional key `id_ed25519` from the credential, the plan names the Secret and its key and writes nothing, the push keeps the last newline and restarts nothing, and a push with no key skips it and names the store command.
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/k8s/test_cluster_secret_push.py`
- [x] 2.2 Add the row to `CLUSTER_SECRETS`.
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/k8s/test_cluster_secret_push.py`

## 3. Documents

Kind: documents.

Changes: `k8s/README.md`, `docs/CLUSTER.md`.

- [x] 3.1 Name the Secret, its key, its keyring source and the commands of a person in `k8s/README.md` (Cluster Secrets) and in a new section "Infra drift" of `docs/CLUSTER.md`.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: store the key with `uv run devops config set infra.ssh_private_key --from-file <key-file>`, run `uv run devops k8s push-secrets --only devops/infra-ssh-key --plan` and then `uv run devops k8s push-secrets --only devops/infra-ssh-key`. Then `argo submit -n devops --from cronwf/infra-drift` starts one Workflow, and `argo get -n devops @latest` shows that its pod gets past the mount of `ssh-key`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
