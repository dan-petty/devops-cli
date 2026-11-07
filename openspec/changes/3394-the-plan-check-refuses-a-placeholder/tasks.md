# Tasks

## 1. Refuse a placeholder body and placeholder What Changes lines

Reads: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_content.py`, `tests/support/builders.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_content.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_content.py`, add a case that `content_problems(make_stage_proposal(pull_request_body="placeholder"))` holds a problem naming `pull_request_body` and the placeholder word, a case that `content_problems(make_stage_proposal(what_changes=["placeholder"]))` holds a problem naming `what_changes` and the placeholder word, a case that a `pull_request_body` shorter than `PLAN_FIELD_MIN_CHARS` is refused with the least length, a case that a `what_changes` line shorter than `PLAN_FIELD_MIN_CHARS` is refused with the least length, and a case that a valid body and valid What Changes lines give no problem
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` fails on the base
- [ ] 1.2 In `_plan_texts` of `src/devops_cli/roadmap/stage_change.py`, add `("pull_request_body", proposal.pull_request_body)` to `named` and append one `("what_changes", line)` pair for each line of `proposal.what_changes`, so that the existing loop of `content_problems` applies the length rule and `is_placeholder` to both fields
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` passes

## 2. State the two checked fields in the plan stage prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 2.1 In `tests/roadmap/test_roadmap_stage_prompt_rules.py`, add a test that reads the Texts rule of the prompt and asserts that it names `pull_request_body` and each `what_changes` line
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` fails on the base
- [ ] 2.2 In the Texts rule of `src/devops_cli/ai/tasks/roadmap_stage_change.md`, name `pull_request_body` and each `what_changes` line beside `why`, `existing_tool`, each line of `feasibility`, each decision and each task, with the same least length and the same placeholder rule
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
