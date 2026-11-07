# Tasks

## 1. Declare the token and its two Secret entries

Reads: `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/k8s/secret_push.py`. Changes: `src/devops_cli/config/env.py`, `src/devops_cli/k8s/cluster_secrets.py`, `k8s/argocd/apps/projects.yaml`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`, `tests/invariants/test_k8s_manifests.py`, `tests/commands/test_config_audit_keys.py`, `tests/security/test_config_declarations.py`, `tests/config/test_config_keys.py`, `tests/commands/test_config.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_qdrant_security.py`.

- [x] 1.1 Add the tests: the table rows, the shared keyring entry, the env variables, one generated token for both Secrets with no value in output, and the audit of the key
  - Verification: `uv run devops ci test tests/k8s/test_cluster_secret_plan.py` fails on the base
- [x] 1.2 Add the credential `crawl4ai.api_token`, the row `devops/crawl4ai`, the key `DEVOPS_CLI_CRAWL4AI_API_TOKEN` and the Argo CD ignore entry
  - Verification: `uv run devops ci test tests/k8s/test_cluster_secret_push.py` passes

## 2. Document the rows

Changes: `k8s/README.md`, `docs/ENV_VARS.md`.

- [x] 2.1 List both rows and a note on the token in the secret table of `k8s/README.md`, and regenerate `docs/ENV_VARS.md`
  - Verification: `uv run devops ci test tests/invariants/test_k8s_manifests.py` passes

## Workflow follow-up

- The manifests issue (#3884) adds `deployment/crawl4ai` to the restarts of the row `devops/crawl4ai`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
- Pending a person: run `devops k8s push-secrets --only devops/crawl4ai --only devops/devops-cli` to create the Secrets.
