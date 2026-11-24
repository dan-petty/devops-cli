# Tasks

## 1. Declare the valkey.username setting

Kind: behavior. Reads: `src/devops_cli/config/settings.py`, `tests/security/test_config_declarations.py`. Changes: `src/devops_cli/config/settings.py`, `tests/security/test_config_declarations.py`.

- [x] 1.1 Add the case `test_valkey_username_is_declared_with_its_variable` to `tests/security/test_config_declarations.py`; it fails until `valkey.username` is a declared variable with the variable `DEVOPS_CLI_VALKEY_USER` and an empty default
  - Verification: `$ uv run devops ci test tests/security/test_config_declarations.py` fails on the base
- [x] 1.2 Add `username` to `ValkeyConfig` in `src/devops_cli/config/settings.py` as an optional `Variable()` field beside `password`, with a description that says it names the ACL user and that an empty value keeps the default user, and add `DEVOPS_CLI_VALKEY_USER` to `_VARIABLES_OF_LATER_SETTINGS` in `tests/security/test_config_declarations.py`
  - Verification: `$ uv run devops ci test tests/security/test_config_declarations.py` passes

## 2. Send the ACL user from the cache tier

Kind: behavior. Reads: `src/devops_cli/valkey/cache.py`, `src/devops_cli/config/settings.py`, `tests/valkey/test_valkey_cache_tier.py`, `tests/ai/rag/test_library_store_wiring.py`, `tests/commands/test_library_vector_tier.py`, `tests/commands/test_valkey.py`, `tests/roadmap/stores/test_brain_issues.py`, `tests/roadmap/stores/test_github_store_brain.py`, `tests/roadmap/stores/test_listing_shared.py`, `tests/server/routes/test_webhooks_brain.py`, `tests/valkey/test_tiered.py`. Changes: `src/devops_cli/valkey/cache.py`, `tests/valkey/test_valkey_cache_tier.py`.

- [x] 2.1 Add the case `test_configured_tier_sends_the_user_of_valkey_username` to `tests/valkey/test_valkey_cache_tier.py`; it fails until the provider returns `sweep` and the password when `valkey.username` is set, and the password alone when it is unset
  - Verification: `$ uv run devops ci test tests/valkey/test_valkey_cache_tier.py` fails on the base
- [x] 2.2 Return the user and the password from `_SettingsValkeyCredentialProvider.get_credentials` in `src/devops_cli/valkey/cache.py` when `valkey.username` and the resolved password are both set, and the password alone otherwise, so a snapshot write through the configured tier authenticates as the role user of its settings
  - Verification: `$ uv run devops ci test tests/valkey/test_valkey_cache_tier.py` passes

## 3. Generate the role passwords and the aclfile in the Secret table

Kind: behavior. Reads: `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/k8s/secret_push.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`, `tests/invariants/test_k8s_manifests.py`, `k8s/README.md`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_gitea.py`, `tests/commands/k8s/test_k8s_qdrant_security.py`, `tests/commands/test_config_commands.py`, `tests/invariants/test_k8s_searxng.py`, `tests/k8s/test_cluster_secret_key_refs.py`, `tests/k8s/test_cluster_secrets.py`, `tests/k8s/test_cluster_secrets_file.py`, `tests/k8s/test_grafana_renderer_optional.py`, `tests/k8s/test_roadmap_service_key.py`. Changes: `src/devops_cli/k8s/cluster_secrets.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`, `tests/invariants/test_k8s_manifests.py`, `k8s/README.md`.
Adds: `DEVOPS_CACHE_VALKEY_SWEEP_KEY`, `DEVOPS_CACHE_VALKEY_BRAIN_KEY`, `DEVOPS_CACHE_VALKEY_AGENT_KEY`, `DEVOPS_CACHE_VALKEY_METRICS_KEY`, `DEVOPS_CACHE_VALKEY_ACL_TEMPLATE`

- [x] 3.1 Add the case `test_valkey_role_passwords_and_derived_aclfile` to `tests/k8s/test_cluster_secret_plan.py`, extend the expected rows of `test_table_holds_each_secret_entry_with_its_source_and_restarts` in the same module with one generated `hex` 32-byte entry for each of `sweep`, `brain`, `agent` and `metrics` and with the derived `users.acl` entry of `llm/valkey-devops-auth`, extend the applied-key map of `test_apply_is_one_server_side_apply_of_a_list_on_stdin` in `tests/k8s/test_cluster_secret_push.py` with the five keys, extend the expected `sorted(backend.writes)` list of `test_a_generated_value_is_stored_in_the_keyring_before_the_apply` in the same module with the four role keys, and extend the keyring-only set of `tests/invariants/test_k8s_manifests.py`; the cases fail until the plan of `llm/valkey-devops-auth` generates one 64-character hex value for each of the four role keys, a `users.acl` value whose user lines are exactly `default`, `sweep`, `brain`, `agent` and `metrics`, and `k8s/README.md` holds the row that `test_readme_lists_the_table` computes for each new key
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/k8s/test_cluster_secret_push.py tests/invariants/test_k8s_manifests.py` fails on the base
- [x] 3.2 Add the four keyring key constants and the aclfile template to `src/devops_cli/k8s/cluster_secrets.py`, add the four generated `hex` 32-byte entries and the derived `users.acl` entry to the row `llm/valkey-devops-auth`, leave `DEVOPS_CLI_VALKEY_PASSWORD` of `devops/devops-cli` on key `password`, add the five expected rows to `test_table_holds_each_secret_entry_with_its_source_and_restarts` in `tests/k8s/test_cluster_secret_plan.py`, add the five keys to the applied-key map of `test_apply_is_one_server_side_apply_of_a_list_on_stdin` and the four role keys to the keyring-write list of `test_a_generated_value_is_stored_in_the_keyring_before_the_apply` in `tests/k8s/test_cluster_secret_push.py`, and write the five rows that `test_readme_lists_the_table` computes plus the cache paragraph that names the aclfile and the `sweep` rule of the shared snapshot into `k8s/README.md`; the template writes `user default on` with `password`, one `user` line for each role, `+@all -@dangerous` for `sweep`, `brain` and `agent`, and the seven explicit commands for `metrics`
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/k8s/test_cluster_secret_push.py tests/invariants/test_k8s_manifests.py` passes
- [x] 3.3 Edit `k8s/README.md` to hold the row of each new key of `llm/valkey-devops-auth` and the paragraph that names the aclfile and the `sweep` rule of the shared snapshot
  - Verification: `$ uv run devops ci docs` passes

## 4. Load the aclfile from the Secret and scrape as metrics

Kind: other. Reads: `src/devops_cli/k8s/cluster_secrets.py`. Changes: `dan-petty/homelab`.

- [x] 4.1 In `dan-petty/homelab`, replace the `config` emptyDir and the `auth.conf` render with a read-only Secret volume of key `users.acl` of Secret `valkey-devops-auth` at `/run/valkey`, start `valkey-server --aclfile /run/valkey/users.acl` with the existing flags, drop the `VALKEY_PASSWORD` env of the valkey container, and set `REDIS_USER` to `metrics` with `REDIS_PASSWORD` from key `metrics` on the exporter (`k8s/llm/valkey-devops.yaml` in this repository stays unchanged under `environment-freeze`)
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 5. Share a private repository's snapshot only under the sweep user

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/listing_shared.py`, `src/devops_cli/roadmap/stores/listing_snapshot.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/stores/test_listing_shared.py`. Changes: `src/devops_cli/roadmap/stores/listing_shared.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/stores/test_listing_shared.py`.
Adds: `SWEEP_USER`, `_configured_valkey_user`

- [x] 5.1 Add the case `test_a_private_repository_is_shared_only_under_the_sweep_user` to `tests/roadmap/stores/test_listing_shared.py`; it fails until the `valkey_server` fake holds a private repository's snapshot when the process sends the `sweep` user, and holds none when the process sends no user
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_listing_shared.py` fails on the base
- [x] 5.2 Add `SWEEP_USER` and a `user` field to `TieredSnapshotStore` in `src/devops_cli/roadmap/stores/listing_shared.py`, with `_configured_valkey_user` reading `valkey.username` as its default, treat a private repository as shared in `load` and in `_share` when `self.user()` gives `sweep` so that `_checked` keeps the copy, and update the docstring of the write result enum in `src/devops_cli/config/constants.py`; the test helper takes the user as a keyword that gives none by default
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_listing_shared.py` passes

## 6. Document the setting in the generated configuration pages

Kind: other. Reads: `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`. Changes: `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`.

- [x] 6.1 Regenerate `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` with `uv run devops docs generate` so they hold `valkey.username` and `DEVOPS_CLI_VALKEY_USER`; the rows and the cache paragraph of `k8s/README.md` already hold the new Secret keys from group 3
  - Verification: `$ uv run devops ci docs` passes
- [x] 6.2 Edit `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` to name `valkey.username` and its variable
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Pending person: `valkey-cli ACL USERS` lists the 3 users, and the default user is off., Only a person with cluster access runs the live command, and the owner's comment of 2026-11-21 keeps the default user on and adds the `metrics` user, so the live list holds `default`, `sweep`, `brain`, `agent` and `metrics`, and `default` stays on until #6600.
- Pending person: A test: the `agent` user gets `NOPERM` on `valkey:roadmap:*`., No test doubles Valkey's ACL, the runner image holds no valkey-server, and the NOPERM answer comes only from the deployed pod, so a person runs the valkey-cli probe of the scenario Agent refuses a roadmap key; the aclfile that causes the refusal is asserted offline by group 3.
- Group 5: A test: the tiered cache writes the snapshot of a private repository only under the `sweep` user.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
