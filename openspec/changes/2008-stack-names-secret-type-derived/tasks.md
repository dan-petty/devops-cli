# Tasks

## 1. The stack names are declared once

- [x] Add a failing test: the deploy-stack summary, the push-secrets `--stack` help and the bootstrap-k8s `--stack` help name every stack and `all`, push-secrets also names `base`, and the bootstrap-k8s help does not name `monitoring`
  - Verification: `uv run devops ci test tests/test_k8s_networking.py`
- [x] Declare `CONST_K8S_STACKS` and `CONST_K8S_ALL_STACKS`, derive `CONST_K8S_VALID_STACKS`, `_resolve_stacks` and the help texts from them, register deploy-stack with `HELP.k8s.deploy_stack`, delete the `VALID_STACKS` of `stack_lifecycle.py`, and import the one of `networking.py` in the package and the tests
  - Verification: `uv run devops ci test tests/test_k8s_networking.py tests/test_k8s_devops_stack.py tests/test_k8s_logging_stack.py tests/test_k8s_gitea.py tests/test_k8s.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 2. Derived entries and Secret types in the push table

- [x] Add failing tests: a connection string from a literal user and a generated password parses back with `urlsplit`, and the keyring holds no value for it; a derived entry before its input in the table is `unchanged`; a missing managed input is skipped with its `devops config set` command; `--plan` and `--dry-run` name `derived from` with no value and no keyring write; a differing derived value needs `--rotate`; a `kubernetes.io/basic-auth` row and a row with no type carry their types in the applied and the dry-run manifests; `keyring_only_keys` counts a derived keyring input
  - Verification: `uv run devops ci test tests/test_k8s_push_secrets.py`
- [x] Add `DerivedSource`, `ClusterSecret.secret_type` and `CONST_K8S_MATTERMOST_URL`; resolve derived entries after every other entry in `plan_push` and list their reads in the same order in the dry run
  - Verification: `uv run devops ci test tests/test_k8s_push_secrets.py`
- [x] Describe derived entries and Secret types in the Cluster Secrets section of `k8s/README.md`
  - Verification: `uv run devops docs check`

## 3. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2008-stack-names-secret-type-derived`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

## Workflow follow-up

- #1391 adds the `mattermost/mattermost-db` row of type `kubernetes.io/basic-auth` with the derived `DB_CONNECTION_STRING`, and the `chat` stack to `CONST_K8S_STACKS`.
- #1392 and #1393 add the derived hook URLs from `CONST_K8S_MATTERMOST_URL`.
