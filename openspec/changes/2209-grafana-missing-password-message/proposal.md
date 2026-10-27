# Proposal

## Why

Issue #2209: `devops k8s sync-secrets` prints "Grafana secret not found in active cluster." when the Grafana admin password is missing. The sync reads that password from the OS keyring, not from the cluster, so the message sends the reader to the wrong place.

## What Changes

- When the keyring has no `grafana_password`, the sync prints a message that names the keyring entry and two commands: `devops config set grafana.password` to store the password, and `devops k8s push-secrets` to adopt it from the cluster.
- The message for a missing Argo CD secret stays as it is: the sync reads that secret from the cluster.
- The change alters a command message, so it carries a spec delta. It fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `stack-credential-sync`: adds a requirement for the message of a missing Grafana admin password.

## Impact

- `src/devops_cli/commands/k8s/stack_lifecycle.py`, `src/devops_cli/lang/en/messages.py`, `tests/test_k8s_credentials.py`.

## Feasibility

- Source: `sync_k8s_credentials` in `src/devops_cli/k8s/credentials.py` reads `_keyring_get("grafana_password")` and never reads a cluster Secret for Grafana. The Argo CD password is read from the cluster.
- The issue names the entry `grafana_admin_password` and the setting `grafana.admin_password`. Both names are wrong. The keyring entry is `grafana_password` and the setting is `grafana.password` (`opt.GRAFANA_PASSWORD`). The change uses the real names.
- The cluster Secret table in `src/devops_cli/k8s/cluster_secrets.py` gives `grafana-admin` the source `KeyringSource("grafana_password", opt.GRAFANA_PASSWORD)` with `adopt_from` the `monitoring/grafana` Secret key `admin-password`. So `devops k8s push-secrets` does adopt the password from the cluster.

## Existing Tool Considered

No outside tool applies. The change adds one message string and one match case in the existing report function.
