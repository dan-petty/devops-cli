# Tasks

Selection: the owner changed the scope of #1647 on 2026-10-28. No organization is made. The roadmap Service acts as GitHub App `devops-roadmap`, which the personal account owns, and a separate item makes the roadmap work without the project board.

## 1. The process acts as the GitHub App

- [x] 1.1 Write the tests of the App's token, login, ledger and commit email in the new `tests/test_github_app_identity.py`, over `github_api` with an RSA key that the run generates, and verify that `uv run devops ci test tests/test_github_app_identity.py` fails on the base
- [x] 1.2 Add `service.github_app` (`GitHubAppConfig`) and the managed credential `service.github_app.private_key` to the settings, the options, the variables and the secret registry. Add `acts_as_github_app`, `GitHubIdentity`, `github_identity` and the renewal to `src/devops_cli/core/process.py`, and the new `src/devops_cli/github/app_installation.py` that mints the token with `gidgethub.apps`. Key the session and the ledger by the identity, send the current token with each request, and add `GitHubSession.commit_email`. Verify that `uv run devops ci test tests/test_github_app_identity.py tests/test_github_session.py tests/test_github_rate_limiter.py tests/test_subprocess_env_boundary.py` passes
- [x] 1.3 Delete `service.machine_account` and `k8s.github_account` with their options, variables, rows of `devops config show` and settings fields, and verify that `uv run devops ci test tests/test_config_cmd.py` passes

## 2. The Service, its webhook consumer and the job clone

- [x] 2.1 Change the tests of `devops serve --service`, the webhook consumer and the job clone to the App (`tests/test_server.py`, `tests/test_server_service.py`, `tests/test_service_limits.py`, `tests/test_roadmap_run.py`), and verify that they fail on the base
- [x] 2.2 Make `devops serve --service` require the App's settings and its key in the environment, refuse the bot's deliveries with `ignored_own_write`, name the pause identity by the bot login, and commit the job clone as the session's login and `commit_email`. Verify that `uv run devops ci test tests/test_server.py tests/test_server_service.py tests/test_service_limits.py tests/test_roadmap_run.py` passes

## 3. The cluster Secret and the ConfigMap

- [x] 3.1 Change the tests of the Secret table, `devops k8s push-secrets` and the ConfigMap to the App's key and settings, delete the tests of the gh account read, and verify that `uv run devops ci test tests/test_k8s_push_secrets.py tests/test_k8s_configmap.py` fails on the base
- [x] 3.2 Replace the `GH_TOKEN` row with `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` from keyring `service_github_app_private_key`, delete `GitHubAccountSource`, `read_github_account_token`, `--github-account` and the gh requests of the dry run, render the ConfigMap's service block through PyYAML with `service.github_app`, and change `k8s/devops/configmap.example.yaml`. Verify that `uv run devops ci test tests/test_k8s_push_secrets.py tests/test_k8s_configmap.py tests/test_k8s.py tests/test_k8s_devops_stack.py tests/test_k8s_deploy_stack_urls.py tests/test_k8s_roadmap_service.py tests/test_k8s_qdrant_security.py` passes

## 4. Decision record and documents

- [x] 4.1 Write ADR 0015, which supersedes ADR 0002, mark ADR 0002 as superseded, and change ADR 0004 and ADR 0009 where they name the machine account
- [x] 4.2 Describe the App in `k8s/README.md` (the Secret table, the `devops-cli` in the cluster commands, and the Roadmap service note and steps 1 to 3 and 9), the comment of `k8s/devops/roadmap-service/deployment.yaml`, `config.example.yaml` and the knowledge base, regenerate the docs with `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes
- [x] 4.3 Verify that `uv run devops ci test tests/test_swallowed_failures_ratchet.py tests/test_architectural_invariants.py` passes, that `git grep -n "machine_account\|github_account\|GitHubAccountSource" -- src/` prints nothing, and that `uv run devops ci` passes

## Workflow follow-up

- The roadmap store keeps its board reads and writes. An App installation cannot reach the board of a personal account, so a separate item, which the parent session files, moves the roadmap state to labels and milestones. `deployment/roadmap-service` stays at `replicas: 0` until that item merges.
- Replacing the webhooks of each repository with the App's own webhook is a later item.
- Pending a person: create GitHub App `devops-roadmap` on the personal account with the repository permissions of `k8s/README.md` (Roadmap service, step 1), install it on the managed repositories, and generate its private key.
- Pending a person: run `devops config set service.github_app.app_id <app-id>`, `devops config set service.github_app.installation_id <installation-id>`, `devops config set service.github_app.slug devops-roadmap` and `devops config set service.github_app.private_key --from-file <key.pem>`.
- Pending a person: run `devops k8s push-secrets --stack devops`, which changes Secret `devops/devops-cli`. The server-side apply drops the old `GH_TOKEN` key, which field manager `devops-cli` owned.
- Pending a person: with the App's key in `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, run `devops gh api repos/<owner>/<repo>/issues --jq '.[0].number'` and confirm that the read succeeds as `devops-roadmap[bot]`.
- Pending a person: raise `replicas` of `deployment/roadmap-service` only after the board-independence item merges.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
