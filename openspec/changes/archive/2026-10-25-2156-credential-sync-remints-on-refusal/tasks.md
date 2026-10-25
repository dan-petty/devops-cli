# Tasks

## 1. The token checks, the mints and the sync

- [x] 1.1 Write the failing tests in `tests/test_k8s_credentials.py` on the edge fakes (`process_fake`, `stub_web`, `mock_keyring`): a 502 and a timeout at each check keep the stored token and send no mint, revoke or create request; 401, 403 and, for Argo CD, `loggedIn: false` mint a new token; and each failed mint, account lookup, revoke, token create, kubectl read, Secret field and keyring store reports its cause. Give `StubWeb` in `tests/web_fakes.py` `respond` and `fail` for them. On origin/main the file has 42 failed and 11 passed tests. Verify with `uv run devops ci test tests/test_k8s_credentials.py`
- [x] 1.2 Add `StackCredentialError` to `src/devops_cli/exceptions/k8s.py` and the refused and account-exists statuses to `src/devops_cli/config/constants.py`. Rewrite the checks, the mints and the sync in `src/devops_cli/k8s/credentials.py` so that each handler catches only the error that its call raises, and `sync_k8s_credentials` returns a `CredentialSync` for each credential. Verify with `uv run devops ci test tests/test_k8s_credentials.py` and `uv run mypy src/devops_cli/k8s/credentials.py src/devops_cli/exceptions/k8s.py`
- [x] 1.3 Delete `_verify_argocd_token`, `_verify_grafana_token`, `_resolve_existing_token`, `_resolve_service_url`, `_safe_keyring_set`, `_post_argocd_session`, `_decode_k8s_secret_field`, `_sync_argocd_credentials` and `_sync_grafana_credentials`, and the old tests of the module that patched devops-cli names. Lower the ceiling of the module with `uv run python -m tests.test_swallowed_failures_ratchet --lower`. Verify with `uv run devops ci test tests/test_swallowed_failures_ratchet.py tests/test_architectural_invariants.py`
- [x] 1.4 Run the tests of the callers and of the other users of `stub_web`. Verify with `uv run devops ci test tests/test_argo.py tests/test_argo_gitops.py tests/test_grafana.py tests/test_k8s_push_secrets.py tests/test_k8s_qdrant_security.py tests/test_common_tools.py tests/test_semgrep_registry.py tests/test_vault_broker.py tests/test_github_client.py tests/test_http_broker.py`

## 2. The command

- [x] 2.1 Write the failing test `test_sync_secrets_shows_each_failure_with_its_cause_and_exits_1` in `tests/test_k8s_credentials.py`. Verify with `uv run devops ci test tests/test_k8s_credentials.py`
- [x] 2.2 Print each `CredentialSync` in `sync-secrets` and in the `infra` step of `deploy-stack` (`src/devops_cli/commands/k8s/stack_lifecycle.py`), and exit with status 1 from `sync-secrets` when a step failed. Give the three tests that patch the sync an empty result. Verify with `uv run devops ci test tests/test_k8s_credentials.py tests/test_k8s.py tests/test_k8s_tempo.py tests/test_k8s_bootstrap.py`
- [x] 2.3 Say in the help text of `sync-secrets` which token the command keeps, which it mints, and when it exits with status 1, and regenerate the documents. Verify with `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## Workflow follow-up

- The Grafana mint revokes the old tokens of the `devops-cli` service account before it creates the new token. A create that fails after the revoke leaves the account with no token. Create the new token first, then revoke the other tokens: #2208.
- For a missing Grafana admin password, the command prints "Grafana secret not found in active cluster.", but the sync reads that password from the OS keyring, not from the cluster. Name the keyring in that line: #2209.
- `credentials.py` still reads and writes the keyring through the private `_keyring_get` and `_keyring_set` of `config/settings.py`: #1318.
- The Argo CD and Grafana clients still come from `httpx2.Client` and not from the egress-checked factory: #1381.
- Pending a person: run `devops k8s sync-secrets` against the homelab cluster one time after the merge, and read the line of each credential. The sync writes the keyring and can mint tokens, so no agent ran it.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
