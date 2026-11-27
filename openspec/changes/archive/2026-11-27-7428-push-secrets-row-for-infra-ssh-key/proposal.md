# Proposal: #7428

## Why

WorkflowTemplate `infra-drift` (`k8s/devops/workflowtemplate-infra-drift.yaml`, #5129) mounts Secret `devops/infra-ssh-key` at `/secrets/ssh` and reads its key `id_ed25519` as `ANSIBLE_SSH_PRIVATE_KEY_FILE`. #5129 says that a person writes this Secret with `devops k8s push-secrets` from the keyring. The table of `push-secrets` has no row for it, and nothing else in the repository makes it. So the pod of each `infra-drift` Workflow stays in `Init:0/1` with a `FailedMount` event, and a person has no command to write the Secret (#7428).

## What Changes

- A new managed credential, `infra.ssh_private_key`, with the keyring entry `infra_ssh_private_key` and the variable `DEVOPS_CLI_INFRA_SSH_PRIVATE_KEY`. A person stores the private key with `devops config set infra.ssh_private_key --from-file <key-file>`, which keeps each line of the file.
- A new product row of `CLUSTER_SECRETS`: Secret `devops/infra-ssh-key` of stack `devops`, with one optional key, `id_ed25519`, from that keyring entry. It has no generator and restarts no workload.
- `k8s/README.md` (Cluster Secrets) and a new section "Infra drift" of `docs/CLUSTER.md` name the Secret, its key, its keyring source and the commands of a person.
- The change is observable: `devops k8s push-secrets` gets a new Secret and `devops config set` a new key, so it has a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `cluster-secrets-loader`: the product Secret table holds the infra SSH key.

## Impact

- Code: `src/devops_cli/config/env.py`, `src/devops_cli/k8s/cluster_secrets.py`
- Tests: `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`, `tests/security/test_config_declarations.py`, `tests/commands/test_config_audit_keys.py`
- Documents: `k8s/README.md`, `docs/CLUSTER.md`, `docs/ENV_VARS.md` (generated)
- No manifest changes. The WorkflowTemplate already mounts the Secret.

## Feasibility

- Live, 2026-11-27 (#7428): a Workflow from `cronwf/infra-drift` got a pod that stayed in `Init:0/1` with `FailedMount: ... secret "infra-ssh-key" not found`, and `uv run devops k8s push-secrets --plan --only devops/infra-ssh-key` gave `Unknown Secret: devops/infra-ssh-key`.
- The table holds a multi-line value: `SecretEntry` takes any text, and the push encodes it with `base64.b64encode(value.encode("utf-8"))` (`_encode`, `src/devops_cli/k8s/secret_push.py`). The PEM keys of `devops/devops-cli` and `devops/renovate` use the same form.
- `devops config set <key> --from-file` stores the text of a file "with no line added or removed" (`read_secret_input`, `src/devops_cli/config/secret_input.py`). For a credential with no settings field, `dotted_set` writes only the keyring (`src/devops_cli/config/settings.py`).
- keyring 25.7.0, `keyring/cli.py`: `keyring set` reads a pipe with `strip_last_newline(sys.stdin.read())`, and a terminal with `getpass`, which reads one line.
- OpenSSH_10.6p2: `ssh-keygen -y -f` loads a throwaway ed25519 key with its last newline, and refuses the same key without it.

## Existing Tool Considered

The cluster Secret table of `devops k8s push-secrets` and `devops config set --from-file` cover the need. The change adds one credential and one row to them, with no new code path: about 60k tokens and 1 hour. External Secrets Operator is not used for product rows, and a new store for one key costs more than a row.
