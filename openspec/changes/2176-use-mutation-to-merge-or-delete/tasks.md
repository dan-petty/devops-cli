# Tasks

## 1. Census the 26 table rows against this tree

Kind: other. Reads: `docs/TESTING.md`. Changes: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py` (new).

- [ ] 1.1 Add a `## Mutation decisions` section to `docs/TESTING.md` with one row for each of the 26 rows of the issue table: the path the table gives, the path that holds that test at this commit, the commit that removed the old path when no file holds it, the campaign command, the duration, the killed-mutant count, the own-mutant count and one decision of `kept`, `deleted`, `moved` or `settled`. State the settle rule once in that section: a row with no own mutant loses its file or moves its one distinct case into the mirror module of its subject, and a row with an own mutant keeps its file and names that mutant key and the test that kills it. Add `tests/invariants/test_mutation_decisions.py`, which parses the section and asserts 26 rows, 22 campaign rows whose path is a file of this tree, four settled rows that name the commit which removed the old path, a decision on every row, and no campaign row under `tests/invariants/`
  - Verification: `$ uv run devops ci test tests/invariants/test_mutation_decisions.py` passes
- [ ] 1.2 Edit `docs/TESTING.md` with the 26-row mutation decisions section
  - Verification: `$ uv run devops ci docs` passes

## 2. Repair the mutation test selection and the copy list

Kind: manifest. Reads: `pyproject.toml`, `tests/openspec/test_openspec_new.py`. Changes: `pyproject.toml`, `tests/invariants/test_mutmut_selection.py` (new).

- [ ] 2.1 The case `test_every_selection_path_is_a_file_of_this_tree` in `tests/invariants/test_mutmut_selection.py` fails on the first `--ignore` entry of the mutation test selection, which names a module of the old root-level tests folder that no file of this tree holds
  - Verification: `$ uv run devops ci test tests/invariants/test_mutmut_selection.py` fails on the base
- [ ] 2.2 Point each `--ignore` and `--deselect` entry of `pytest_add_cli_args_test_selection` in `pyproject.toml` at the module that holds that test at this commit, and drop an entry whose test no module holds. Add `openspec` to `also_copy`, because `tests/openspec/test_openspec_new.py` reads a spec of the checkout. Add `tests/invariants/test_mutmut_selection.py`, which asserts that each entry names a file of this tree, that each deselected case exists in its module, and that `also_copy` holds `openspec`
  - Verification: `$ uv run devops ci test tests/invariants/test_mutmut_selection.py` passes

## 3. Campaign the seven AI rows

Kind: other. Reads: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/ai/client/test_ai_client_credentials.py`, `tests/ai/client/test_ai_gateway_base_url.py`, `tests/ai/test_ai_client_style_request.py`, `tests/ai/test_ai_task_loader.py`, `tests/ai/test_pydantic_ai_format_prompt.py`, `tests/ai/spend/test_ai_spend_dispatch.py`, `tests/ai/retries/test_pydantic_ai_retries.py`. Changes: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/ai/client/test_ai_client_credentials.py`, `tests/ai/client/test_ai_gateway_base_url.py`, `tests/ai/test_ai_client_style_request.py`, `tests/ai/test_ai_task_loader.py`, `tests/ai/test_pydantic_ai_format_prompt.py`, `tests/ai/spend/test_ai_spend_dispatch.py`, `tests/ai/retries/test_pydantic_ai_retries.py`.

- [ ] 3.1 Run the two campaigns of the seven AI rows: `tests/ai/client/test_ai_client_credentials.py`, `tests/ai/client/test_ai_gateway_base_url.py`, `tests/ai/test_ai_client_style_request.py`, `tests/ai/test_ai_task_loader.py`, `tests/ai/test_pydantic_ai_format_prompt.py`, `tests/ai/spend/test_ai_spend_dispatch.py` and `tests/ai/retries/test_pydantic_ai_retries.py`. For each row, mutate the `src/` files whose lines it covers once with the whole suite and once with the file left out of the selection, then write the command, the duration, the killed-mutant count and the own-mutant count in its row of the record. Apply the settle rule of the record: delete the file, or move its one distinct case into the mirror module of its subject, when it has no own mutant, and keep it with the mutant key and the killing test when it has one. Add `test_the_ai_rows_are_settled` to `tests/invariants/test_mutation_decisions.py`, which asserts that each of the seven rows holds a command, a duration, two counts and a decision, that a `kept` row names a mutant key and a test, and that a `deleted` or `moved` row counts no own mutant
  - Verification: `$ uv run devops ci test tests/invariants/test_mutation_decisions.py tests/ai` passes
- [ ] 3.2 Edit `docs/TESTING.md` with the killed and own mutant counts of the seven AI rows
  - Verification: `$ uv run devops ci docs` passes

## 4. Campaign the three configuration rows

Kind: other. Reads: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/config/test_settings_cache.py`, `tests/config/test_headless_auth.py`, `tests/commands/test_config.py`, `tests/config/test_config_key_removal.py`, `tests/config/test_config_file_that_is_not_yaml.py`. Changes: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/config/test_settings_cache.py`, `tests/config/test_headless_auth.py`, `tests/commands/test_config.py`, `tests/config/test_config_key_removal.py`, `tests/config/test_config_file_that_is_not_yaml.py`.

- [ ] 4.1 Run the two campaigns of the three configuration rows: `tests/config/test_settings_cache.py`, `tests/config/test_headless_auth.py` and `tests/commands/test_config.py`. Move each distinct case of the command file that no other test asserts into the mirror module of its subject: the credential redaction and dry-run cases into `tests/config/test_config_key_removal.py`, and the config-file error case into `tests/config/test_config_file_that_is_not_yaml.py`. Keep a case that is the file's own in `tests/commands/test_config.py` and keep the file. Write the command, the duration and the two counts in each row, and apply the settle rule to the three rows. Add `test_the_config_rows_are_settled` to `tests/invariants/test_mutation_decisions.py` with the same assertions as the AI rows
  - Verification: `$ uv run devops ci test tests/invariants/test_mutation_decisions.py tests/config tests/commands` passes
- [ ] 4.2 Edit `docs/TESTING.md` with the killed and own mutant counts of the three configuration rows
  - Verification: `$ uv run devops ci docs` passes

## 5. Campaign the core, HTTP, language and Valkey rows

Kind: other. Reads: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/core/test_cleanup_fuzzing.py`, `tests/core/test_third_party_telemetry.py`, `tests/core/test_consolidation_binaries.py`, `tests/http/test_http_async_client.py`, `tests/lang/test_language_catalogs.py`, `tests/valkey/test_valkey_cache_tier.py`. Changes: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/core/test_cleanup_fuzzing.py`, `tests/core/test_third_party_telemetry.py`, `tests/core/test_consolidation_binaries.py`, `tests/http/test_http_async_client.py`, `tests/lang/test_language_catalogs.py`, `tests/valkey/test_valkey_cache_tier.py`.

- [ ] 5.1 Run the two campaigns of the six core, HTTP, language and Valkey rows: `tests/core/test_cleanup_fuzzing.py`, `tests/core/test_third_party_telemetry.py`, `tests/core/test_consolidation_binaries.py`, `tests/http/test_http_async_client.py`, `tests/lang/test_language_catalogs.py` and `tests/valkey/test_valkey_cache_tier.py`. Keep the fuzz settings and the example cases with the cleanup case when it moves, write the command, the duration and the two counts in each row, and apply the settle rule to the six rows. Add `test_the_core_http_lang_valkey_rows_are_settled` to `tests/invariants/test_mutation_decisions.py` with the same assertions as the AI rows
  - Verification: `$ uv run devops ci test tests/invariants/test_mutation_decisions.py tests/core tests/http tests/lang tests/valkey` passes
- [ ] 5.2 Edit `docs/TESTING.md` with the killed and own mutant counts of the six core, HTTP, language and Valkey rows
  - Verification: `$ uv run devops ci docs` passes

## 6. Campaign the docs, benchmark, analyze and audit rows

Kind: other. Reads: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/docs/test_exceptions.py`, `tests/ai/benchmark/test_data_dir_configuration.py`, `tests/ai/analyze/test_ai_init.py`, `tests/commands/test_openspec_scaffold.py`, `tests/commands/test_cli_format_adoption.py`, `tests/commands/test_dependency_audit.py`. Changes: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/docs/test_exceptions.py`, `tests/ai/benchmark/test_data_dir_configuration.py`, `tests/ai/analyze/test_ai_init.py`, `tests/commands/test_openspec_scaffold.py`, `tests/commands/test_cli_format_adoption.py`, `tests/commands/test_dependency_audit.py`.

- [ ] 6.1 Run the two campaigns of the six docs, benchmark, analyze and audit rows: `tests/docs/test_exceptions.py`, `tests/ai/benchmark/test_data_dir_configuration.py`, `tests/ai/analyze/test_ai_init.py`, `tests/commands/test_openspec_scaffold.py`, `tests/commands/test_cli_format_adoption.py` and `tests/commands/test_dependency_audit.py`. Write the command, the duration and the two counts in each row, and apply the settle rule to the six rows. Add `test_the_docs_benchmark_analyze_audit_rows_are_settled` to `tests/invariants/test_mutation_decisions.py` with the same assertions as the AI rows
  - Verification: `$ uv run devops ci test tests/invariants/test_mutation_decisions.py tests/docs tests/commands tests/ai/benchmark tests/ai/analyze` passes
- [ ] 6.2 Edit `docs/TESTING.md` with the killed and own mutant counts of the six docs, benchmark, analyze and audit rows
  - Verification: `$ uv run devops ci docs` passes

## 7. Record the coverage total and the gate result

Kind: other. Reads: `docs/TESTING.md`, `pyproject.toml`. Changes: `docs/TESTING.md`.

- [ ] 7.1 Run `uv run devops ci`, write its result and the total line coverage beside the baseline in the record, and confirm that `fail_under` in `pyproject.toml` stays at 85 or higher. The record names the total that the run reports and the `fail_under` value that the file holds
  - Verification: `$ uv run devops ci` passes
- [ ] 7.2 Edit `docs/TESTING.md` with the gate result and the total line coverage
  - Verification: `$ uv run devops ci docs` passes

## 8. Record the Tests and Coverage duration of the pull request

Kind: other. Reads: `docs/TESTING.md`. Changes: `docs/TESTING.md`.

- [ ] 8.1 Read the start and the completion of the Tests and Coverage check run of the pull request and of the newest run of the gate on `main`, subtract each pair, write both durations in the record beside the coverage total, and stop when the pull request's run is longer than the run on `main`, and run this check by hand: Run `gh pr checks --json name,startedAt,completedAt` on the branch of the pull request and take the start and completion of the `Tests & Coverage` row. Run `gh run list --workflow ci.yml --branch main --limit 1 --json databaseId`, then run `gh run view --json jobs` with that id and take the same two times of the job of that name. Subtract each pair, write both durations in the record, and stop the pull request when its run is longer than the run on `main`.
- [ ] 8.2 Edit `docs/TESTING.md` with the two durations
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: The pull request gives, for each file in the table, the mutants it killed with the whole suite and the mutants that survive without it.
- Group 3: Each file with no mutant of its own is deleted, or its distinct case moves into the file that covers its lines. The line coverage and `fail_under` stay as they are or rise.
- Group 1: No contract suite and no invariant test is deleted by this item.
- Group 8: `uv run devops ci` passes, and the `Tests & Coverage` job takes no longer than before.
