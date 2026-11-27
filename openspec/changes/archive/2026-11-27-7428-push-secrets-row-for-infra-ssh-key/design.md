# Design

## Decisions

- **A managed credential, as the other PEM keys.** The row reads `KeyringSource.for_credential("infra.ssh_private_key")`, as `devops/devops-cli` reads `service.github_app.private_key` and `devops/renovate` reads `renovate.github_app_private_key`. `devops config set infra.ssh_private_key --from-file` then stores the key with its last newline.
- **One optional key.** `id_ed25519` has `required=False`. A push with no keyring value and no live value skips the Secret with a warning that names `devops config set infra.ssh_private_key`, and it writes the other Secrets of the stack. The rows of stack `devops` go out with each `push-secrets` and each `deploy-stack`, so a required key would stop those pushes on a workstation with no infra key.
- **No generator and no restart.** A person makes the SSH key and authorizes it on the hosts, so the push makes no value. Each Workflow pod mounts the Secret at its start, so no workload restarts.
- **The row is a product row.** The consumer, `k8s/devops/workflowtemplate-infra-drift.yaml`, is in this repository, and `k8s/README.md` (Cluster Secrets) adds a row in the file of the repository that holds its consumer.
- **Not an optional feature Secret.** `OPTIONAL_FEATURE_SECRETS` makes a reference optional, and a drift pod with no key cannot reach a host. The WorkflowTemplate keeps its required volume.

## Rejected alternatives

- **A keyring-only key, stored with `uv run keyring set devops-cli infra_ssh_private_key`.** keyring 25.7.0 removes the last newline of a pipe (`strip_last_newline` in `keyring/cli.py`) and reads one line from a terminal (`getpass`). OpenSSH_10.6p2 `ssh-keygen -y -f` refused a throwaway ed25519 key without its last newline, and loaded the same key with it.
- **A required key.** A required key with no value is `missing`, one of `BLOCKING_STATES` (`src/devops_cli/k8s/secret_push.py`), and `PushPlan.problems` stops the whole push. So each `push-secrets --stack devops` and each `deploy-stack` would fail until a person stores the key.
- **A row in `cluster-secrets.toml` of the environment repository.** The environment rows are for consumers of that repository; this consumer is a product manifest under `k8s/devops/`.
