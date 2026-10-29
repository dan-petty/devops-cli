# Tasks

## 1. The push writes Argo CD's GitHub notifier Secret

- [x] Add failing tests: the table row and its three optional entries; the two settings and the managed credential with their variables and keyring name; a three-line PEM-shaped keyring value and two IDs reach the Secret byte for byte with no restart; with no value the push writes nothing and names the three `devops config set` commands; `--plan` and `--dry-run` name the keys with no value, and `--dry-run` runs no command
  - Verification: `uv run devops ci test tests/test_k8s_push_secrets.py tests/test_config_declarations.py`
- [x] Add the two settings on `ArgoCDConfig`, the credential `argocd.github_app_private_key`, the row `argocd/argocd-notifications-secret`, and the `devops config set` hint for a setting with no value
  - Verification: `uv run devops ci test tests/test_k8s_push_secrets.py tests/test_config_declarations.py`
- [x] List the three rows in the Cluster Secrets table of `k8s/README.md`, describe how a person stores the values, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 2. The push is the one owner of the Secret

- [x] Add a failing test: the Argo CD values set `notifications.secret.create` to false and the `homelab` project ignores Secret `argocd-notifications-secret` as an orphan
  - Verification: `uv run devops ci test tests/test_k8s_argocd_apps.py`
- [x] Set `notifications.secret.create: false` in `k8s/argocd/values.yaml` and add the Secret to the `homelab` project's orphan ignore list
  - Verification: `uv run devops ci test tests/test_k8s_argocd_apps.py`

## 3. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2000-argocd-notifier-app-secret`
- Pending a person: store the values and push the Secret: `devops config set argocd.github_app_id <id>`, `devops config set argocd.github_app_installation_id <id>`, `devops config set argocd.github_app_private_key --from-file <key.pem>`, then `devops k8s push-secrets --only argocd/argocd-notifications-secret`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

## Workflow follow-up

- #1393 configures `service.github` in `argocd-notifications-cm` and turns notifications on; it refers to the three keys as `$github-appID`, `$github-installationID` and `$github-privateKey`.
