# Tasks

## 1. Answer count and cached tokens of a request

Kind: behavior. Reads: `src/devops_cli/ai/client/factory.py`, `src/devops_cli/roadmap/agent_run.py`, `tests/ai/client/test_agent_factory.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`. Changes: `src/devops_cli/ai/client/factory.py`, `src/devops_cli/ai/spend/ledger.py`, `src/devops_cli/roadmap/agent_run.py`.

- [x] 1.1 Write `test_each_model_request_of_an_agent_adds_one_answer_count`, `test_a_request_on_the_deepseek_group_costs_its_cached_and_new_input_and_its_output` and `test_each_model_request_of_the_run_counts_its_answer_one_time_under_its_row`, and watch them fail
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add `model_answer_labels`, emit the count and pass `cache_read_tokens` in the hook of `build_agent`, and use the helper in `record_run_spend`
  - Verification: `$ uv run pytest -q tests/ai/client/test_agent_factory.py tests/ai/client/test_roadmap_agent_run.py tests/roadmap/refine/test_roadmap_refine_investigation.py`

## 2. Row label

Kind: behavior. Reads: `src/devops_cli/github/request_scope.py`, `src/devops_cli/roadmap/run.py`. Changes: `src/devops_cli/ai/spend/ledger.py`, `src/devops_cli/commands/roadmap.py`.

- [x] 2.1 Write `test_the_ai_series_of_a_request_carry_the_job_row_that_sent_it` and `test_confirm_in_a_runner_counts_its_model_requests_under_the_implement_row`, and watch them fail
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 2.2 Add `row` to the labels of `track_request_spend`, and apply the implement plan in the scope of the row `implement`
  - Verification: `$ uv run pytest -q tests/ai/client/test_agent_factory.py tests/roadmap/implement/test_roadmap_implement_command.py`
- [x] 2.3 Census of the series bound: 53 series of the four in 7 days for roadmap-service, at most 6 rows each, so at most 318
  - Verification: `$ uv run devops prometheus query 'count by (job) (count_over_time(devops_cli_ai_tokens_total[7d]))'`

## 3. Documents

Kind: documents. Reads: `docs/TELEMETRY.md`. Changes: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`.

- [x] 3.1 Name the row in the four instrument descriptions and in the AI spend text, and generate the documents
  - Verification: `$ uv run devops docs generate --check`
