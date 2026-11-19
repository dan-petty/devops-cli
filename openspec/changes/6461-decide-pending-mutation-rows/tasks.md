# Tasks

## 1. Decide the eight rows that run 1 finished

Kind: other. Reads: the run 1 results of #2176. Changes: `tests/ai/client/test_ai_client_credentials.py`, `tests/config/test_headless_auth.py`, `tests/docs/test_exceptions.py`, `tests/commands/test_dependency_audit.py`, `tests/config/test_settings_cache.py`, `tests/ai/test_ai_client_style_request.py`, `tests/ai/benchmark/test_data_dir_configuration.py`, `tests/http/test_http_async_client.py`.

- [ ] 1.1 For each row, give each mutant that run 1 killed the other test files that run its statement. A row with a mutant that no other file runs, outside import-time code, is `kept`. For each other row, run 2 and run 3 decide: a row with no own mutant loses the tests that `## Weakened checks` of the #2176 proposal names
  - Verification: `uv run devops ci test tests/ai/client tests/config tests/docs tests/commands tests/ai/test_ai_client_style_request.py tests/ai/benchmark tests/http` passes

## 2. Run and decide the five rows with no run 1

Kind: other. Reads: `pyproject.toml`. Changes: `tests/commands/test_config.py`, `tests/ai/client/test_ai_gateway_base_url.py`, `tests/ai/spend/test_ai_spend_dispatch.py`, `tests/ai/retries/test_pydantic_ai_retries.py`, `tests/valkey/test_valkey_cache_tier.py`.

- [ ] 2.1 Run 1 selects the file of each row alone, and mutates the functions whose body the file runs. Then apply the rule of task 1.1 to each row
  - Verification: `uv run devops ci test tests/commands tests/ai/client tests/ai/spend tests/ai/retries tests/valkey` passes

## 3. Record the decisions

Kind: other. Reads: none. Changes: none.

- [ ] 3.1 Post the record comment on the pull request of this item: for each row its decision, the run counts and durations, and its own mutants with the test that kills one of them. Confirm that `fail_under` in `pyproject.toml` stays the same
  - Verification: `uv run devops openspec check` passes, and the required checks of the pull request pass
