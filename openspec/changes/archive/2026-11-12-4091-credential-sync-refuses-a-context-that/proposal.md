# Proposal: #4091

## Why

`devops k8s deploy-stack --stack infra` exits with status 1 when the kubeconfig context is a valid kubeconfig name that is not an RFC 1123 name, such as the EKS ARN `arn:aws:eks:us-east-1:123456789012:cluster/prod` (#4091). The command accepts the name with `validate_k8s_context_name` and deploys the Helm releases. Then `sync_k8s_credentials` reads the Argo CD and Grafana Secrets through `fetch_secret_data`, which checks the same name with the RFC 1123 validator `validate_k8s_name`. The command prints `Invalid context: '<name>'. Must be a valid RFC 1123 name.` after the deploy and exits with status 1.

A test hid the defect: `test_deploy_and_teardown_stack_use_effective_context` deployed the `logging` stack, which syncs no credential, as a stand-in for `infra` since #4086.

## What Changes

- `fetch_secret_data` in `src/devops_cli/k8s/credentials.py` checks the context with `validate_k8s_context_name`, the validator of `switch-context`, `deploy-stack`, `argo` and `volume`. It accepts ARN, GKE and user-account names and still refuses an empty name, a space and shell metacharacters before it starts `kubectl`.
- `test_deploy_and_teardown_stack_use_effective_context` deploys and tears down the `infra` stack again with an EKS ARN context, and asserts that the Secret reads pass that context to `kubectl`.
- The Secret read and the exit status of `deploy-stack` are behavior that a user sees, so the change carries a spec delta for `stack-credential-sync`.

The change fits one pull request.

## Capabilities

### Modified Capabilities

- `stack-credential-sync`: the Secret read of the sync accepts every kubeconfig context name that `deploy-stack` accepts, and refuses an unsafe name before it starts `kubectl`.

## Impact

- `src/devops_cli/k8s/credentials.py`: one validator call changes. `fetch_secret_field`, `fetch_argocd_password` and `fetch_grafana_password` read through `fetch_secret_data`, so `devops k8s deploy-stack`, `devops k8s sync-secrets` and the Argo CD and Grafana token commands get the fix.
- No setting, message, command or document changes.

## Feasibility

- `src/devops_cli/k8s/credentials.py:175` on origin/main (devops-cli 0.113.0): `fetch_secret_data` calls `validate_k8s_name(context, "context")`.
- `src/devops_cli/core/validation.py`: `validate_k8s_name` accepts only RFC 1123 names, so `:` and `/` of an ARN fail. `validate_k8s_context_name` accepts letters, digits, `.`, `-`, `_`, `:`, `/` and `@`, and refuses an empty or blank name and every other character.
- `src/devops_cli/commands/k8s/cluster_runtime.py:21`: `deploy-stack` resolves the effective context through `validate_k8s_context_name`, so it accepts the ARN that the sync refuses.
- `git grep -n fetch_secret_data -- src` finds 2 callers, both in `credentials.py` (`fetch_secret_field` and `fetch_grafana_password`), so the one check covers every Secret read of the sync.
- The test `test_deploy_and_teardown_stack_use_effective_context`, changed to the `infra` stack, fails on origin/main with the RFC 1123 message and exit code 1.

## Existing Tool Considered

No open tool validates kubeconfig context names; the alternatives check of #4091 found none. The fix reuses the existing, tested `validate_k8s_context_name` of `devops_cli.core.validation` and adds no code. Internal code that the change deletes: the RFC 1123 check of the context in `fetch_secret_data`.
