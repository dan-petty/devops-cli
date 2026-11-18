# Tasks

## 1. Add the generator lookup to the cluster Secret table

Kind: behavior. Reads: `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/k8s/secret_push.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_gitea.py`, `tests/commands/k8s/test_k8s_qdrant_security.py`, `tests/invariants/test_k8s_manifests.py`, `tests/invariants/test_k8s_renovate.py`, `tests/invariants/test_k8s_searxng.py`, `tests/k8s/test_cluster_secret_key_refs.py`, `tests/k8s/test_grafana_renderer_optional.py`, `tests/k8s/test_roadmap_service_key.py`. Changes: `src/devops_cli/k8s/cluster_secrets.py`, `tests/k8s/test_cluster_secret_plan.py`.
Adds: `generator_for_option`, `generator_option_names`

- [x] 1.1 `test_the_command_and_the_push_read_one_row` in `tests/k8s/test_cluster_secret_plan.py`
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py` fails on the base
- [x] 1.2 Add `generator_for_option(option)` and `generator_option_names()` beside `keyring_sources` in `src/devops_cli/k8s/cluster_secrets.py`. The first walks `CLUSTER_SECRETS`, keeps the entries that declare a generator and whose `keyring_sources(entry)` name the option, and returns that generator or None. The second returns the sorted option of every entry that declares one. Write `test_the_command_and_the_push_read_one_row` in `tests/k8s/test_cluster_secret_plan.py` first: it asserts that the lookup gives the URL-safe 32-byte generator for `crawl4ai.api_token` and None for `gemini.api_key`, and that `generator_option_names()` holds one entry per managed option whose row declares a generator, which is the census that the group stops on when the count differs
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py` passes

## 2. Add the generate and rotate flags to the set command

Kind: behavior. Reads: `src/devops_cli/commands/config.py`, `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/config/os_keyring.py`, `src/devops_cli/config/env.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_config_commands.py`, `tests/support/cluster_secret_fakes.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/commands/test_zero_plaintext_invariants.py`, `tests/commands/k8s/test_k8s_context.py`, `tests/commands/test_config.py`, `tests/commands/test_config_audit_keys.py`, `tests/commands/test_config_cmd.py`, `tests/commands/test_config_field_validation.py`, `tests/commands/test_config_workspace_docs_dry_run.py`, `tests/http/test_http_egress.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/commands/config.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_config_commands.py`.
Adds: `_store_generated`

- [x] 2.1 `test_generate_the_crawl4ai_token` in `tests/commands/test_config_commands.py`
  - Verification: `$ uv run devops ci test tests/commands/test_config_commands.py` fails on the base
- [x] 2.2 Add the generate option, the rotate option and their rules to `set_value` in `src/devops_cli/commands/config.py`, with the new messages in `src/devops_cli/lang/en/messages.py` and the new help text in `src/devops_cli/lang/en/help.py`. A helper `_store_generated(key, rotate, dry_run)` resolves `generator_for_option(key)`; when it is None it exits 1 and names `generator_option_names()`. It calls `require_persistent_keyring()` and reads `keyring_read(credential(key).keyring_name)`; a value with no rotate flag exits 1 and names it. It makes the value with `generate()` and stores it with `keyring_write`, then prints that it stored the credential and no part of the value. With the dry run it prints the encoding, the byte count and a masked placeholder and returns before any read. A VALUE or `--from-file` with the generate flag, and the rotate flag alone, raise `typer.BadParameter`. Write the tests first in `tests/commands/test_config_commands.py`: `test_generate_the_crawl4ai_token`, `test_a_typed_credential_has_no_generator`, `test_a_token_is_already_stored`, `test_rotate_the_token`, `test_dry_run_of_a_generate`, `test_a_typed_value_and_generate_together`, `test_rotate_without_generate` and `test_the_plan_reads_a_stored_token`, which runs the generate and then `plan_push` over the Crawl4AI row with `FakeCluster` and asserts the state is created and the label is the keyring entry of that credential
  - Verification: `$ uv run devops ci test tests/commands/test_config_commands.py` passes

## 3. Name both commands in the configuration page

Kind: behavior. Reads: `src/devops_cli/docs/generator.py`, `tests/docs/test_docs.py`, `docs/CONFIGURATION.md`, `tests/ai/agents/test_pydantic_ai_exceptions.py`, `tests/ai/mcp/test_mcp_tool_registry.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/commands/test_cli_format_adoption.py`, `tests/docs/test_docs_adr_records.py`, `tests/docs/test_docs_inventory.py`, `tests/docs/test_docs_knowledge_base_argv.py`, `tests/docs/test_docs_source_argv_collector.py`, `tests/docs/test_docs_synced_blocks.py`, `tests/docs/test_exceptions.py`. Changes: `src/devops_cli/docs/generator.py`, `tests/docs/test_docs.py`.

- [x] 3.1 `test_the_configuration_page_names_the_generate_command` in `tests/docs/test_docs.py`
  - Verification: `$ uv run devops ci test tests/docs/test_docs.py` fails on the base
- [x] 3.2 Extend the prose of the set command in `generate_configuration_docs` of `src/devops_cli/docs/generator.py`, so the page names the set command with its generate flag for a credential that no person chooses, and names `devops k8s push-secrets` for the Secrets that read it. Write `test_the_configuration_page_names_the_generate_command` in `tests/docs/test_docs.py` first: it builds `DocGenerator` with the module's `generator` fixture, calls `generate_configuration_docs` and asserts that the text holds both command strings
  - Verification: `$ uv run devops ci test tests/docs/test_docs.py` passes

## 4. Edit the Crawl4AI bullet and regenerate the pages

Kind: other. Reads: `k8s/README.md`, `docs/CONFIGURATION.md`, `docs/commands/config.md`, `docs/CLI_REFERENCE.md`, `src/devops_cli/docs/generator.py`. Changes: `k8s/README.md`, `docs/CONFIGURATION.md`, `docs/commands/config.md`, `docs/CLI_REFERENCE.md`.

- [x] 4.1 Rewrite the Crawl4AI bullet of `k8s/README.md` so it names the set command with its generate flag for the token and `devops k8s push-secrets --only devops/crawl4ai --only devops/devops-cli` for the two Secrets, and keeps the sentence that no other command writes them. Then run `uv run devops docs generate`, which writes `docs/CONFIGURATION.md`, `docs/commands/config.md` and `docs/CLI_REFERENCE.md` from the generator and the help text. Edit no generated line by hand
  - Verification: `$ uv run devops ci docs` passes
- [x] 4.2 Edit the Crawl4AI bullet of `k8s/README.md` and regenerate `docs/CONFIGURATION.md`, `docs/commands/config.md` and `docs/CLI_REFERENCE.md` with `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 2: `devops config set crawl4ai.api_token --generate` stores a new token of the declared kind and length in the keyring, and prints that it did so without printing the value.
- Group 1: The command takes the generator from the same declaration that `devops k8s push-secrets` uses. There is one declaration per credential, not two.
- Group 2: A key with no declared generator exits non-zero and names the keys that have one.
- Group 2: A credential that is already set is not replaced. `--rotate` replaces it. `--dry-run` makes no keyring write and no request.
- Group 2: `--generate` and a typed value or `--from-file` together are an error.
- Group 2: After the command, `devops k8s push-secrets --plan` shows the entry as taken from the keyring, not as generated.
- Group 4: The docs of `config set` and the line in `k8s/README.md` that says a person creates the Crawl4AI Secret name the two commands.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
