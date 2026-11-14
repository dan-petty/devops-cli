# Tasks

## 1. Census the 26 table rows against this tree

Kind: other. Reads: `docs/TESTING.md`, `tests/invariants/test_source_tree.py`, `tests/invariants/test_agents_md.py`. Changes: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py` (new).

- [ ] 1.1 Add a `## Mutation decisions` section to `docs/TESTING.md`. State the settle rule and the seven decision words of `design.md` once, and write one row for each of the 26 rows of `## Record rows` in `design.md`, in its order, with the columns table path, path now, decision, reason or commit, command, duration, killed, own mutants and killing test. Write each path as plain text and not as a code span, because `test_the_test_rules_name_only_test_files_that_exist` fails on a backticked `tests/` path that no file holds. Give the 17 campaign rows the decision `pending` and a dash in each campaign column, give the two `settled` rows their commits, and give the seven `unjudged` rows their reasons. Add `test_mutation_decisions.py` to the list of invariant files in the `tests/invariants/` rule of `docs/TESTING.md`. Add `tests/invariants/test_mutation_decisions.py` with `test_the_record_holds_one_row_for_each_table_row`, which parses the section and asserts that it holds 26 rows whose table paths are the 26 paths of the issue table, that each row holds one of the seven decision words, that each `settled` row names a commit, that each `unjudged` row names a reason, that each path now of a `pending`, `kept`, `trimmed` or `unjudged` row is a file of this tree, that no file holds a path now of a `deleted` or `moved` row, that a `moved` row names a target module that is a file, and that no path now is under `tests/invariants/`. These assertions stay true while groups 3 to 7 replace `pending`
  - Verification: `$ uv run devops ci test tests/invariants/test_mutation_decisions.py tests/invariants/test_source_tree.py tests/invariants/test_agents_md.py` passes
- [ ] 1.2 Edit `docs/TESTING.md` with the 26-row mutation decisions section and the new entry of the invariant file list
  - Verification: `$ uv run devops ci docs` passes

## 2. Repair the mutation test selection and the copy list

Kind: manifest. Reads: `pyproject.toml`, `tests/ci/test_ci_mutate.py`, `tests/openspec/test_openspec_new.py`. Changes: `pyproject.toml`, `tests/ci/test_ci_mutate.py`.

- [ ] 2.1 The case `test_each_mutation_selection_entry_names_a_test_of_this_tree` in `tests/ci/test_ci_mutate.py` reads `[tool.mutmut]` of `pyproject.toml` with `tomllib`, as `test_mutate_runs_mutmut_serially_on_the_changed_function_globs` does, and asserts that each `--ignore` entry of `pytest_add_cli_args_test_selection` is a file of this tree and that each `--deselect` entry names a test that its module defines; it fails on the first `--ignore` entry, which names a module of the old root-level tests folder. The case `test_the_mutation_copy_list_holds_the_living_specs` asserts that `also_copy` holds `openspec`, and fails because it holds none
  - Verification: `$ uv run devops ci test tests/ci/test_ci_mutate.py` fails on the base
- [ ] 2.2 Point each `--ignore` and `--deselect` entry of `pytest_add_cli_args_test_selection` in `pyproject.toml` at the module that holds that test at this commit: commit 513bb31f2 moved each of them into its package folder, so the entry for the task loader names `tests/ai/test_ai_task_loader.py`. Keep the comment of each entry. Add `openspec` to `also_copy`, because `tests/openspec/test_openspec_new.py` reads a spec of the checkout
  - Verification: `$ uv run devops ci test tests/ci/test_ci_mutate.py` passes

## 3. Campaign the six AI client rows

Kind: other. Reads: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/ai/client/test_ai_client_credentials.py`, `tests/ai/client/test_ai_gateway_base_url.py`, `tests/ai/test_ai_client_style_request.py`, `tests/ai/test_pydantic_ai_format_prompt.py`, `tests/ai/spend/test_ai_spend_dispatch.py`, `tests/ai/retries/test_pydantic_ai_retries.py`. Changes: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/ai/client/test_ai_client_credentials.py`, `tests/ai/client/test_ai_gateway_base_url.py`, `tests/ai/test_ai_client_style_request.py`, `tests/ai/test_pydantic_ai_format_prompt.py`, `tests/ai/spend/test_ai_spend_dispatch.py`, `tests/ai/retries/test_pydantic_ai_retries.py`.

- [ ] 3.1 Run the two campaigns of the six AI client rows: `tests/ai/client/test_ai_client_credentials.py`, `tests/ai/client/test_ai_gateway_base_url.py`, `tests/ai/test_ai_client_style_request.py`, `tests/ai/test_pydantic_ai_format_prompt.py`, `tests/ai/spend/test_ai_spend_dispatch.py` and `tests/ai/retries/test_pydantic_ai_retries.py`. For each row, mutate the `src/` files whose lines it covers once with the whole suite and once with the file left out of the selection, and write in its row the command, the duration, the killed count of the whole-suite run and the keys of its own mutants: the mutants that the whole suite kills and the run without the file leaves alive. The format-prompt row gets no run, because `src/devops_cli/ai/format_prompt.py` holds no function: write `none` as its command and 0 for both counts. Apply the settle rule: a row with an own mutant keeps its file whole and names one own mutant key and the test of the file that kills it (`kept`); a row with no own mutant loses each test of its file that `## Weakened checks` of `proposal.md` names, and its file goes (`deleted`) or keeps only its unjudged cases (`trimmed`). Remove no test that `## Weakened checks` does not name. Add `test_the_ai_client_rows_are_decided` to `tests/invariants/test_mutation_decisions.py`, which asserts that none of the six rows is `pending`, that each holds a command, a duration, a killed count and an own-mutant entry, that a `kept` row names a mutant key and a test, and that a `deleted` or `trimmed` row names no own mutant
  - Verification: `$ uv run devops ci test tests/invariants/test_mutation_decisions.py tests/ai` passes
- [ ] 3.2 Edit `docs/TESTING.md` with the counts and the decisions of the six AI client rows
  - Verification: `$ uv run devops ci docs` passes

## 4. Campaign the toolsets row

Kind: other. Reads: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/ai/toolsets/test_function_toolset.py`, `tests/ai/toolsets/test_toolset_authoring.py`, `tests/ai/toolsets/test_toolset_combinators.py`. Changes: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/ai/toolsets/test_function_toolset.py`, `tests/ai/toolsets/test_toolset_authoring.py`, `tests/ai/toolsets/test_toolset_combinators.py`.

- [ ] 4.1 Run the two campaigns of the toolsets row, whose table file a later commit split into `tests/ai/toolsets/test_function_toolset.py`, `tests/ai/toolsets/test_toolset_authoring.py` and `tests/ai/toolsets/test_toolset_combinators.py`. Mutate the `src/` files whose lines the three files cover once with the whole suite and once with the three files left out together, and write the command, the duration, the killed count and the keys of the own mutants in its row. Apply the settle rule to the row as one unit: a row with an own mutant keeps the three files (`kept`), and a row with none loses the three files (`deleted`). Remove no test that `## Weakened checks` of `proposal.md` does not name. Add `test_the_toolsets_row_is_decided` to `tests/invariants/test_mutation_decisions.py` with the same assertions as the AI client rows
  - Verification: `$ uv run devops ci test tests/invariants/test_mutation_decisions.py tests/ai` passes
- [ ] 4.2 Edit `docs/TESTING.md` with the counts and the decision of the toolsets row
  - Verification: `$ uv run devops ci docs` passes

## 5. Campaign the three configuration rows

Kind: other. Reads: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/config/test_settings_cache.py`, `tests/config/test_headless_auth.py`, `tests/commands/test_config.py`, `tests/config/test_config_key_removal.py`, `tests/config/test_config_file_that_is_not_yaml.py`. Changes: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/config/test_settings_cache.py`, `tests/config/test_headless_auth.py`, `tests/commands/test_config.py`, `tests/config/test_config_key_removal.py`, `tests/config/test_config_file_that_is_not_yaml.py`.

- [ ] 5.1 Run the two campaigns of the three configuration rows: `tests/config/test_settings_cache.py`, `tests/config/test_headless_auth.py` and `tests/commands/test_config.py`, and write the command, the duration, the killed count and the keys of the own mutants in each row. Decide each row only from its counts. A row with an own mutant keeps its file whole (`kept`). A row with none loses the tests of its file that `## Weakened checks` of `proposal.md` names. For `tests/commands/test_config.py` with no own mutant, a case whose rule no case of `tests/config/test_config_key_removal.py` or `tests/config/test_config_file_that_is_not_yaml.py` holds moves into that module unchanged, the row names that module (`moved`), and the file goes; with no such case the row is `deleted`. Move no case before the counts of its row are in the record. Add `test_the_config_rows_are_decided` to `tests/invariants/test_mutation_decisions.py` with the same assertions as the AI client rows, and that a `moved` row names no own mutant
  - Verification: `$ uv run devops ci test tests/invariants/test_mutation_decisions.py tests/config tests/commands` passes
- [ ] 5.2 Edit `docs/TESTING.md` with the counts and the decisions of the three configuration rows
  - Verification: `$ uv run devops ci docs` passes

## 6. Campaign the core, HTTP and Valkey rows

Kind: other. Reads: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/core/test_cleanup_fuzzing.py`, `tests/core/test_consolidation_binaries.py`, `tests/http/test_http_async_client.py`, `tests/valkey/test_valkey_cache_tier.py`. Changes: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/core/test_cleanup_fuzzing.py`, `tests/core/test_consolidation_binaries.py`, `tests/http/test_http_async_client.py`, `tests/valkey/test_valkey_cache_tier.py`.

- [ ] 6.1 Run the two campaigns of the four core, HTTP and Valkey rows: `tests/core/test_cleanup_fuzzing.py`, `tests/core/test_consolidation_binaries.py`, `tests/http/test_http_async_client.py` and `tests/valkey/test_valkey_cache_tier.py`. Write the command, the duration, the killed count and the keys of the own mutants in each row, and apply the settle rule: a row with an own mutant keeps its file whole (`kept`), and a row with none loses its file (`deleted`). Remove no test that `## Weakened checks` of `proposal.md` does not name. Add `test_the_core_http_valkey_rows_are_decided` to `tests/invariants/test_mutation_decisions.py` with the same assertions as the AI client rows
  - Verification: `$ uv run devops ci test tests/invariants/test_mutation_decisions.py tests/core tests/http tests/valkey` passes
- [ ] 6.2 Edit `docs/TESTING.md` with the counts and the decisions of the four core, HTTP and Valkey rows
  - Verification: `$ uv run devops ci docs` passes

## 7. Campaign the docs, benchmark and audit rows

Kind: other. Reads: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/docs/test_exceptions.py`, `tests/ai/benchmark/test_data_dir_configuration.py`, `tests/commands/test_dependency_audit.py`. Changes: `docs/TESTING.md`, `tests/invariants/test_mutation_decisions.py`, `tests/docs/test_exceptions.py`, `tests/ai/benchmark/test_data_dir_configuration.py`, `tests/commands/test_dependency_audit.py`.

- [ ] 7.1 Run the two campaigns of the three docs, benchmark and audit rows: `tests/docs/test_exceptions.py`, `tests/ai/benchmark/test_data_dir_configuration.py` and `tests/commands/test_dependency_audit.py`. Write the command, the duration, the killed count and the keys of the own mutants in each row, and apply the settle rule: a row with an own mutant keeps its file whole (`kept`); a row with none loses the tests of its file that `## Weakened checks` of `proposal.md` names, and its file keeps only its unjudged cases (`trimmed`). Add `test_the_docs_benchmark_audit_rows_are_decided` to `tests/invariants/test_mutation_decisions.py` with the same assertions as the AI client rows, and add `test_no_row_is_pending`, which asserts that no row of the record is `pending` and that each of the 17 campaign rows holds a command, a killed count and an own-mutant entry
  - Verification: `$ uv run devops ci test tests/invariants/test_mutation_decisions.py tests/docs tests/ai/benchmark tests/commands` passes
- [ ] 7.2 Edit `docs/TESTING.md` with the counts and the decisions of the three docs, benchmark and audit rows
  - Verification: `$ uv run devops ci docs` passes

## 8. Record the coverage total and the gate result

Kind: other. Reads: `docs/TESTING.md`, `pyproject.toml`. Changes: `docs/TESTING.md`.

- [ ] 8.1 Run `uv run devops ci`, write its result and the total line coverage beside the baseline in the record, and confirm that `fail_under` in `pyproject.toml` stays at 85 or higher. The record names the total that the run reports and the `fail_under` value that the file holds
  - Verification: `$ uv run devops ci` passes
- [ ] 8.2 Edit `docs/TESTING.md` with the gate result and the total line coverage
  - Verification: `$ uv run devops ci docs` passes

## 9. Record the Tests and Coverage time of the pull request

Kind: other. Reads: `docs/TESTING.md`. Changes: `docs/TESTING.md`.

- [ ] 9.1 Write the mean time of the Tests and Coverage job on `main` and the time of that job on the pull request in the record beside the coverage total, and stop the pull request when its time is longer than the mean on `main`, and run this check by hand: Run `uv run devops ci job-time --runs 20` before the pull request merges, and take the mean that it prints as the time on `main`. Run `uv run devops gh api repos/{owner}/{repo}/commits/<head commit of the pull request>/check-runs --jq '.check_runs[] | select(.name | startswith("Tests & Coverage")) | [.name, .started_at, .completed_at]'`, and take the time of the `Tests & Coverage` run plus the time of its slowest shard run, as `devops ci job-time` counts a job. Write both times in the record, and stop the pull request when its time is longer than the mean on `main`.
- [ ] 9.2 Edit `docs/TESTING.md` with the two times
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 7: The pull request gives, for each file in the table, the mutants it killed with the whole suite and the mutants that survive without it.
- Group 8: Each file with no mutant of its own is deleted, or its distinct case moves into the file that covers its lines. The line coverage and `fail_under` stay as they are or rise.
- Group 1: No contract suite and no invariant test is deleted by this item.
- Group 9: `uv run devops ci` passes, and the `Tests & Coverage` job takes no longer than before.
