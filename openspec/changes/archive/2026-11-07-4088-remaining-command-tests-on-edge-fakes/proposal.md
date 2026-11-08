# Proposal

## Why

Issue #4088 is group 4 of #3769. #3769 asks that no command test patches a name inside `devops_cli`. It splits the work by command group: the k8s tests, the pr, gh and repos tests, the ci and test_selection tests, and then Cloudflare, Valkey and every other command test.

The group 4 files were counted again at `origin/main` 74ba76b8 (2026-11-07), because the text of #3769 is older than the tree. They hold 328 string patches of a `devops_cli` name in 30 files. The largest are `test_devcontainer.py` (45), `test_cloudflare_commands.py` (36), `test_analyze.py` (28), `test_valkey.py` (27) and `test_tf.py` (25).

The patches double code that runs inside the process: `commands.cloudflare.load_settings`, `commands.cloudflare._resolve_client`, `commands.valkey._resolve_client`, `commands.vault.VaultSecretBroker` and the keyring helpers of `commands.vault`. Each such double hides the edge that the command reaches, so a mutation of the HTTP request, the Valkey command or the keyring write can pass.

## What Changes

This change migrates the 12 command test files below to the shared edge fakes. Together they held 106 of the 328 patches. 222 patches in 18 files stay for later items.

- `tests/commands/test_cloudflare_commands.py` (36) and `test_cloudflare_dry_run.py` (2): the settings come from the `config` fixture, the token from the environment variable of the option, and the Cloudflare API from a small in-file server over the `web` fake. The server answers by method and path and answers 404 for a path no test expects, so an unexpected request fails the test. The `CloudflareClient` cases that patched `_request` and the client's own methods use the same server. The private `_normalize_ip_cidr` import is gone: the CIDR cases call `create_or_update_access_policy` and read the posted body.
- `tests/commands/test_valkey.py` (27): the CLI cases use the in-memory server of the `valkey` fixture, or the loopback server of `serving_valkey` where the test needs INFO, a server error or the recorded commands. The `ai runs connect` case answers `kubectl` through `process_fake`.
- `tests/commands/test_vault_cmd.py` (16): the broker doubles are replaced by Vault replies over the `web` fake, and the keyring patches by the `keyring_store` fake (`values`, `writes`, `locked`, `selected`).
- `tests/commands/test_tls_cmd.py` (8), `test_uv.py` (6), `test_kustomize.py` (1), `test_load_and_pipeline.py` (3), `test_telemetry_cmd.py` (2), `test_docker_dry_run.py` (1), `test_config_cmd.py` (2) and `test_ai_local_dry_run.py` (2): `run_subprocess` doubles become `process_fake`; the telemetry doubles become the `otlp` collector fake; the Docker guard becomes the `docker_daemon` fake and a check of its calls; the project root of the uv tests comes from the working directory; the keyring doubles become the `keyring_store` fake.
- Each test keeps its name and the behavior it checks. 389 node ids are collected before and after, and three names change, because no test mocks any more: `test_tls_commands_mocked` is now `test_tls_ca_cert_and_inspect_commands_read_each_others_files`, `test_telemetry_status_live_mocked` is now `test_telemetry_status_live`, and `test_telemetry_test_live_mocked` is now `test_telemetry_test_live`.
- Three assertions follow the real code path instead of the double: `vault status` prints "did not answer" for a refused connection (the double printed its own text), `vault sync` counts the fields it wrote, and `access sync --bypass-ips` prints the IP as typed while the posted policy holds the `/32` form.
- This change touches no path under `src/` and alters no behavior a consumer observes. It has no spec delta, and `skip_specs: true` is set.
- This change fits one pull request. The files that stay are named under Impact.

## Impact

- `tests/commands/` (the 12 files above).
- Patches that stay in group 4 (328 before, 222 after), by file and reason:
  - Size. Each file below holds 9 or more patches. They do not fit in this pull request with the 12 files above, so a later item takes each of them: `test_devcontainer.py` (45), `test_analyze.py` (28), `test_tf.py` (25), `test_config_commands.py` (20), `test_telemetry_profile.py` (19), `test_scan.py` (14), `test_workspace.py` (13), `test_ai_cmd.py` (11), `test_test_runner.py` (11) and `test_memory_profiler.py` (9).
  - Next wave. These files hold 5 patches or fewer. A later item takes them, so that one pull request stays small to review: `test_rag.py` (5), `test_config_workspace_docs_dry_run.py` (4), `test_review_adjudication.py` (4), `test_review_scope.py` (3), `test_argo.py` (2), `test_argo_dry_run.py` (2) and `test_devcontainer_install_tools_dry_run.py` (2).
  - Needs a change in `src/`. `test_mcp_serve_stdio_and_sse.py` (5): see the next item.
- `test_mcp_serve_stdio_and_sse.py` waits for a change in `src/`: `commands/mcp.py` looks up `run_mcp_server` by name on its own module so that a test can replace it. That is a shape for tests, and the fix belongs to a change of the product code.
- `test_vault_cmd.py` keeps the import of the private `_validate_vault_path` in four unchanged tests. Two other test files outside group 4 import it too, so its move into a public function needs a change that touches those groups.
- No ratchet file counts these patches in the tree today, so no ceiling goes down. #1336 adds the ban.

## Feasibility

Checked on `origin/main` 74ba76b8, 2026-11-07. The premise of #3769 holds for group 4.

- The count: `uv run python` over the AST of `tests/commands` (first argument of `monkeypatch.setattr`, `patch` and `patch.object` is a string with `devops_cli` or `commands.`), excluding the k8s, pr, gh, repos, ci and test_selection files, gives 328 patches in 30 files. After this change it gives 222 patches in 18 files.
- The edges exist. `uv run pytest tests/commands/test_valkey.py tests/commands/test_vault_cmd.py` passed on the `web`, `keyring_store`, `valkey`, `serving_valkey` and `process_fake` fixtures before the migration.
- The option `cloudflare.api_token` maps to the variable `DEVOPS_CLI_CLOUDFLARE_API_TOKEN` (`config/env.py`), so the tests need no patch of `get_cloudflare_api_token`. `CloudflareClient` already takes its transport from the `web` fixture through `http_client`, so no `transport=` argument is needed.
- `resolve_valkey_client` honors the override that `install_valkey_client` sets, and the `valkey` fixture installs it. `FakeServer` answers no INFO, so the INFO cases use `serving_valkey`.
- Mutation check, run on a copy of the product code outside the work tree, restored after each run: 16 mutations each fail a migrated test. They are a zone id taken from the account id, a DELETE request that is not sent, a merge that drops the catch-all rule, a bypass policy without its IP, `valkey flush --all` that flushes one database, a backup that sends no BGSAVE, a logout that keeps the stored login, a logout that revokes nothing, a uv command run in the wrong directory, a uv failure that exits 0, `kustomize diff` that runs apply, a pipeline failure that exits 0, a telemetry status that is never connected, an audit stream that counts nothing, a TLS verify that accepts every certificate, and an enable-k8s that applies before the render.

## Existing Tool Considered

The shared fakes and fixtures of #1307 (`web`, `config`, `cli`, `keyring_store`, `valkey`, `serving_valkey`, `process_fake`, `otlp`, `docker_daemon`) cover every edge of these tests, and `pytest` runs them. No new tool is needed.

The Cloudflare tests build one small helper in their own file, `cloudflare_api`, a route table on top of `web.serve`. It costs about 1,500 tokens to write and 300 tokens each month to keep. A shared Cloudflare fake would need a contract suite against recorded responses, which is more than two files use. `respx` and `pytest-httpx` patch the HTTP library and do not know the egress check, so they are not used.
