# Tasks

## 1. Fail the token count when the cache is missing

Reads: `src/devops_cli/ai/context_budget.py`, `tests/ai/test_context_budget.py`. Changes: `src/devops_cli/ai/context_budget.py`, `tests/ai/test_context_budget.py`.

- [ ] 1.1 In `tests/ai/test_context_budget.py`, write a test that points the tiktoken cache at an empty directory and asserts `count_tokens` raises an error that names the cache, and a test that `count_tokens` of a text equals the count of the same text through `get_tiktoken_encoding().encode`
  - Verification: `uv run devops ci test tests/ai/test_context_budget.py` fails on the base
- [ ] 1.2 Replace the character fallback in `count_tokens` with an error that names the resolved cache directory, so both the stage and the Job stop instead of counting characters. Keep the encoding load in `_get_tiktoken_encoding` and its cache
  - Verification: `uv run devops ci test tests/ai/test_context_budget.py` passes

## 2. Measure created files and refuse a missing estimate

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 2.1 In `tests/roadmap/test_roadmap_stage_plan.py`, write a test that a group whose `creates` entry gives 1,500 lines counts as 48,000 tokens and lands in `over_budget` at the 40,000-token budget, and a test that a group whose `creates` path gives no estimate is refused with an error that names the path
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 2.2 Add the line estimate to the group of `stage_change.py` beside `creates`, add 32 tokens for each estimated line of each `creates` path to the group measure, and refuse a `creates` path that has no estimate. State the rule in the schema description so the model reply carries it
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. State the budget and the estimate rule in the prompts

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 In `tests/roadmap/test_roadmap_stage_prompt_rules.py`, write tests that both staging task prompts state the 40,000-token step budget and the rule that each `creates` path carries a line estimate
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` fails on the base
- [ ] 3.2 Add the 40,000-token step budget and the rule that each `creates` path carries a line estimate to both staging task prompts, so the prompt tests and the #3210 prompt assertions pass
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Criteria

- Group 1: A test shows that the same group text measures the same with the real counter and with the fallback, within the stated bound, or that the fallback is refused in the Job.
- Group 2: A test shows that a group that creates a 1,500-line file is counted as over the budget.
- Group 3: The prompt states the budget and the creation estimate, and the #3210 test passes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
