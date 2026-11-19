# Tasks

## 1. Repair the mutation test selection and the copy list

Kind: manifest. Reads: `pyproject.toml`, `tests/module_durations.json`. Changes: `pyproject.toml`.

- [ ] 1.1 Point each `--ignore` and `--deselect` entry of `pytest_add_cli_args_test_selection` in `pyproject.toml` at the module that holds that test at this commit: commit 513bb31f2 moved each of them into its package folder. Remove the entry whose test no file of this tree holds. Add to `also_copy` each top-level entry that a selected test reads, `openspec` included, because `tests/openspec/test_openspec_new.py` reads a spec of the checkout. Keep the comment of each entry
  - Verification: in the mutants tree that mutmut 3.8.1 makes for all of `src/devops_cli`, `pytest -n 8` with the selection of `pyproject.toml` passes, and `uv run pytest --collect-only -q <node id>` collects the test of each `--deselect` entry

## 2. Measure the scope of each campaign row

Kind: other. Reads: `pyproject.toml`, `src/devops_cli/ci/mutate.py`. Changes: none.

- [ ] 2.1 Run the suite with `COVERAGE_CORE=ctrace` and `--cov-context=test`, and map the context of each line to the function that mutmut mutates around it with `mutable_functions` of `src/devops_cli/ci/mutate.py`. For each of the 17 campaign rows, list the functions whose body its tests run and the other test files that run those functions
  - Verification: the map gives at least one function for each campaign row whose file calls a function of `src/`

## 3. Campaign the six AI client rows

Kind: other. Reads: `tests/ai/client/test_ai_client_credentials.py`, `tests/ai/client/test_ai_gateway_base_url.py`, `tests/ai/test_ai_client_style_request.py`, `tests/ai/test_pydantic_ai_format_prompt.py`, `tests/ai/spend/test_ai_spend_dispatch.py`, `tests/ai/retries/test_pydantic_ai_retries.py`. Changes: the same files.

- [ ] 3.1 For each row, run 1 selects the file alone and mutates the functions of the row; run 2 selects the other files that run those functions and runs again each mutant that run 1 killed. Write the command, the duration, the mutant count, the killed counts and the keys of the own mutants in the row of the record. Apply the settle rule: a row with an own mutant keeps its file whole and names one own mutant and the test of the file that kills it (`kept`); a row with no own mutant loses each test of its file that `## Weakened checks` of `proposal.md` names, and its file goes (`deleted`) or keeps only its other cases (`trimmed`). Remove no test that `## Weakened checks` does not name
  - Verification: `uv run devops ci test tests/ai` passes

## 4. Campaign the toolsets row

Kind: other. Reads: `tests/ai/toolsets/test_function_toolset.py`, `tests/ai/toolsets/test_toolset_authoring.py`, `tests/ai/toolsets/test_toolset_combinators.py`. Changes: the same files.

- [ ] 4.1 Run the two campaigns of the toolsets row with the three files as one unit: run 1 selects the three files, and run 2 leaves the three files out together. Apply the settle rule to the row as one unit, and remove no test that `## Weakened checks` of `proposal.md` does not name
  - Verification: `uv run devops ci test tests/ai/toolsets` passes, or reports no test module when the row is `deleted`

## 5. Campaign the three configuration rows

Kind: other. Reads: `tests/config/test_settings_cache.py`, `tests/config/test_headless_auth.py`, `tests/commands/test_config.py`, `tests/config/test_config_key_removal.py`, `tests/config/test_config_file_that_is_not_yaml.py`. Changes: the same files.

- [ ] 5.1 Run the two campaigns of the three configuration rows, and decide each row only from its counts. For `tests/commands/test_config.py` with no own mutant, a case whose rule no case of `tests/config/test_config_key_removal.py` or `tests/config/test_config_file_that_is_not_yaml.py` holds moves into that module unchanged (`moved`), and the file goes; with no such case the row is `deleted`
  - Verification: `uv run devops ci test tests/config tests/commands` passes

## 6. Campaign the core, HTTP and Valkey rows

Kind: other. Reads: `tests/core/test_cleanup_fuzzing.py`, `tests/core/test_consolidation_binaries.py`, `tests/http/test_http_async_client.py`, `tests/valkey/test_valkey_cache_tier.py`. Changes: the same files.

- [ ] 6.1 Run the two campaigns of the four rows and apply the settle rule: a row with an own mutant keeps its file whole (`kept`), and a row with none loses its file (`deleted`)
  - Verification: `uv run devops ci test tests/core tests/http tests/valkey` passes

## 7. Campaign the docs, benchmark and audit rows

Kind: other. Reads: `tests/docs/test_exceptions.py`, `tests/ai/benchmark/test_data_dir_configuration.py`, `tests/commands/test_dependency_audit.py`. Changes: the same files.

- [ ] 7.1 Run the two campaigns of the three rows and apply the settle rule: a row with an own mutant keeps its file whole (`kept`); a row with none loses the tests of its file that `## Weakened checks` of `proposal.md` names, and its file keeps only its unjudged cases (`trimmed`). No row of the record stays `pending`
  - Verification: `uv run devops ci test tests/docs tests/ai/benchmark tests/commands` passes

## 8. Record the coverage total and the gate result

Kind: other. Reads: `pyproject.toml`. Changes: none.

- [ ] 8.1 Write the result of the required checks of the pull request and the total line coverage of its `Tests & Coverage` job in the record, and confirm that `fail_under` in `pyproject.toml` stays at 85
  - Verification: the required checks of the pull request pass

## 9. Record the Tests and Coverage time of the pull request

Kind: other. Reads: none. Changes: none.

- [ ] 9.1 Write the mean time of the `Tests & Coverage` job on `main` from `uv run devops ci job-time --runs 20` and the time of that job on the pull request from `uv run devops gh api` in the record
  - Verification: the time of the pull request is not longer than the mean on `main`

## Criteria

- Group 7: The pull request gives, for each file in the table, the mutants it killed with the whole suite and the mutants that survive without it.
- Group 8: Each file with no mutant of its own is deleted, or its distinct case moves into the file that covers its lines. The line coverage and `fail_under` stay as they are or rise.
- Group 1: No contract suite and no invariant test is deleted by this item.
- Group 9: `uv run devops ci` passes, and the `Tests & Coverage` job takes no longer than before.
