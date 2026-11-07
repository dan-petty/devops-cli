# Tasks

## 1. Refuse a prompt change with no prompt-rule test

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`.

- [ ] 1.1 Write `test_a_prompt_change_with_no_prompt_rule_test_is_refused`, `test_a_prompt_change_that_verifies_another_command_is_refused`, `test_a_prompt_change_that_gives_a_process_is_refused_once` and `test_the_plan_check_accepts_the_plan_of_this_change` in `tests/roadmap/stage/test_roadmap_stage_content.py`, where the last test builds the plan's own `StageProposal` and asserts that `content_problems` returns no problem for it
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py` fails on the base
- [ ] 1.2 Add `PROMPT_PREFIX`, `PROMPT_SUFFIX` and `PROMPT_RULE_TEST` to `src/devops_cli/roadmap/stage/stage_change.py`, and add `_prompt_rule_problems` to the problems that `content_problems` returns. Add `stage_problem_prompt_rule` to `src/devops_cli/lang/en/messages.py`. Run `uv run devops roadmap eval stage --replay` and state the score before and after the change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py` passes

## 2. State the prompt-rule rule in the planner prompts

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 2.1 Add one sentence to each planner prompt: a group that changes a `roadmap_stage_*.md` prompt lists `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` in `reads` or `changes` and gives it as `verify`. Add the assertion that pins the sentence in both prompts to `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
- [ ] 2.2 Edit `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_stage_split.md`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
