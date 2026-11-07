# Tasks

## 1. The Cloudflare and Valkey command tests reach the HTTP and Valkey edges (test-only edits)

- [x] 1.1 Move `tests/commands/test_cloudflare_commands.py` and `tests/commands/test_cloudflare_dry_run.py` to the `config` fixture, the token variable and a route table over the `web` fake. Replace the private `_normalize_ip_cidr` import with calls of `create_or_update_access_policy`.
  Verification: `uv run pytest tests/commands/test_cloudflare_commands.py tests/commands/test_cloudflare_dry_run.py`
- [x] 1.2 Move the CLI cases of `tests/commands/test_valkey.py` to the `valkey` fixture and `serving_valkey`, and the `ai runs connect` case to `process_fake`.
  Verification: `uv run pytest tests/commands/test_valkey.py`

## 2. The Vault and TLS command tests reach the HTTP, keyring and process edges (test-only edits)

- [x] 2.1 Replace the broker doubles of `tests/commands/test_vault_cmd.py` with Vault replies over the `web` fake, and the keyring patches with the `keyring_store` fake.
  Verification: `uv run pytest tests/commands/test_vault_cmd.py`
- [x] 2.2 Replace the doubles of `tests/commands/test_tls_cmd.py` with the real certificate functions and `process_fake`, and rename the one test whose name said that the crypto was mocked.
  Verification: `uv run pytest tests/commands/test_tls_cmd.py`

## 3. The process, telemetry, Docker and config command tests reach their edge fakes (test-only edits)

- [x] 3.1 Move `tests/commands/test_uv.py`, `tests/commands/test_kustomize.py` and `tests/commands/test_load_and_pipeline.py` to `process_fake` and the `cli` fixture. The uv tests find the project root from the working directory.
  Verification: `uv run pytest tests/commands/test_uv.py tests/commands/test_kustomize.py tests/commands/test_load_and_pipeline.py`
- [x] 3.2 Move `tests/commands/test_telemetry_cmd.py` to the `otlp` fake, `tests/commands/test_docker_dry_run.py` to the `docker_daemon` fake, and `tests/commands/test_config_cmd.py` and `tests/commands/test_ai_local_dry_run.py` to the `keyring_store` and `process_fake` fakes.
  Verification: `uv run pytest tests/commands/test_telemetry_cmd.py tests/commands/test_docker_dry_run.py tests/commands/test_config_cmd.py tests/commands/test_ai_local_dry_run.py`

## 4. No migrated file patches a devops_cli name (test-only edits)

- [x] 4.1 Check that none of the 12 migrated files passes a `devops_cli` or `commands.` name to a patch.
  Verification: `! git grep -n -F -e '("devops_cli.' -e '("commands.' -- tests/commands/test_valkey.py tests/commands/test_cloudflare_commands.py tests/commands/test_cloudflare_dry_run.py tests/commands/test_vault_cmd.py tests/commands/test_tls_cmd.py tests/commands/test_uv.py tests/commands/test_kustomize.py tests/commands/test_load_and_pipeline.py tests/commands/test_telemetry_cmd.py tests/commands/test_docker_dry_run.py tests/commands/test_config_cmd.py tests/commands/test_ai_local_dry_run.py`

## 5. Documents (documents)

- [x] 5.1 Check that the change folder is valid.
  Verification: `uv run devops openspec check`

## 6. Archive

- [x] 6.1 Archive the change.
  Verification: `uv run devops openspec archive 4088-remaining-command-tests-on-edge-fakes`
