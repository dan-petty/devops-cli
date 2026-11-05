# Tasks

## 1. Refuse a plan whose own rule would refuse it

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_content.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_content.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_content.py`, write a test that builds a proposal with `make_stage_proposal` whose behavior group changes `src/devops_cli/roadmap/stage_change.py`, asserts that `content_problems` names `StageProposal` and `content_problems` for a test text with no such names, and asserts that `content_problems` returns no problem for a test text that builds the plan's own `StageProposal` and asserts no problem for `content_problems`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` fails on the base
- [x] 1.2 Add the message text to `src/devops_cli/lang/en/messages.py` beside the other text problems of the roadmap stage messages, and add the rule to `content_problems` in `src/devops_cli/roadmap/stage_change.py`: when a behavior group changes `src/devops_cli/roadmap/stage_change.py` and no group test text holds `StageProposal`, `content_problems` and no problem, return one problem that names the symbols and the test that the plan must give
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` passes

## 2. State the self-acceptance rule in the staging prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`, `src/devops_cli/ai/task_loader.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_stage_prompt_rules.py`, write a test that loads the prompt with `load_task_prompt` and asserts that it holds `StageProposal`, `content_problems` and the self-acceptance test rule
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` fails on the base
- [x] 2.2 Add the self-acceptance test rule to `src/devops_cli/ai/tasks/roadmap_stage_change.md` beside the other checks of a plan: a behavior group that changes `src/devops_cli/roadmap/stage_change.py` needs a group test that builds the plan's own `StageProposal` and asserts that `content_problems` returns no problem for it
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
