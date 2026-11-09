# Tasks

## 1. Tool choice of a Claude group

Kind: behavior. Reads: `src/devops_cli/ai/pydantic_ai_bridge.py`, `tests/ai/test_pydantic_ai_profiles_and_providers.py`. Changes: `src/devops_cli/ai/pydantic_ai_bridge.py`.

- [x] 1.1 Write `test_a_claude_group_is_sent_tool_choice_auto_for_a_tool_output`, `test_a_model_that_is_not_a_claude_group_keeps_the_default_tool_choice` and `test_a_claude_group_profile_allows_no_forced_tool_choice` in `tests/ai/test_pydantic_ai_profiles_and_providers.py`, and watch them fail
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Build the model of a Claude group on a gateway as `OpenAIChatModel` with the profile `supports_forced_tool_choice=False` in `_resolve_remote_inferred_model`, and keep `served_by`
  - Verification: `$ uv run devops ci test tests/ai/test_pydantic_ai_profiles_and_providers.py`

## 2. Answered model of a run

Kind: behavior. Reads: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/telemetry/instruments.py`, `tests/ai/client/test_roadmap_agent_run.py`. Changes: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/telemetry/instruments.py`.

- [x] 2.1 Write the five tests on the answered model in `tests/ai/client/test_roadmap_agent_run.py`, and watch them fail
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 2.2 Add the instrument `AI_MODEL_ANSWERS_TOTAL` (`devops_cli_ai_model_answers_total`), read the model name of each reply in `record_run_spend`, pass `served_model` to `track_request_spend`, and emit the count with the labels `asked`, `answered` and `fallback`
  - Verification: `$ uv run devops ci test tests/ai/client/test_roadmap_agent_run.py`
- [x] 2.3 Census of the series bound: 11 chat groups and 7 fallback pairs (6 rules of the gateway config, one chain), so at most 18 series; the pull request states the count
  - Verification: `$ grep -cE "^    - [a-z0-9.:-]+: \[" k8s/llm/gateway/config.yaml`

## 3. Documents

Kind: documents. Reads: `README.md`, `docs/`. Changes: the documents that list the instruments.

- [x] 3.1 Add the new series to every document and test that lists the instruments, and run the instrument tests
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py`

## Workflow follow-up

- Pending a person: decide whether the gateway fallback `claude-sonnet-5-5 -> deepseek-v4.1-flash-1017` stays. This change does not alter it.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
