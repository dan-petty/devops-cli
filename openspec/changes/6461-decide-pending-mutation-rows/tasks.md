# Tasks

## 1. Decide the eight rows that run 1 finished

Kind: other. Reads: the run 1 results of #2176. Changes: `tests/http/test_http_async_client.py` and `tests/module_durations.json`, because each other row of the group has an own mutant.

- [x] 1.1 For each row, the row file alone must kill each run 1 mutant again in a fresh process outside every checkout, and no other file that runs its statement may kill it. A row with such an own mutant is `kept`. A row with none loses the tests that `## Weakened checks` of the #2176 proposal names
  - Verification: `$ uv run devops ci test tests/http`

## 2. Run and decide the five rows with no run 1

Kind: other. Reads: `pyproject.toml`. Changes: none, because each of the five rows is `kept`.

- [x] 2.1 Run 1 of each row first mutates the functions whose body only its file runs, and then each function whose body its file runs. Then apply the rule of task 1.1 to each row
  - Verification: `$ uv run devops ci test tests/commands/test_config.py tests/ai/client/test_ai_gateway_base_url.py tests/ai/spend/test_ai_spend_dispatch.py tests/ai/retries/test_pydantic_ai_retries.py tests/valkey/test_valkey_cache_tier.py`

## 3. Record the decisions

Kind: other. Reads: none. Changes: none.

- [x] 3.1 Post the record comment on the pull request of this item: for each row its decision, the run counts and durations, and its own mutants with the test that kills each of them. Confirm that `fail_under` in `pyproject.toml` stays the same
  - Verification: `$ uv run devops openspec check`
