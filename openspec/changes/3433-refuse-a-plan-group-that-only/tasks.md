# Tasks

## 1. Refuse a test-only other group with no named test

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_content.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_content.py`.

- [ ] 1.1 Add cases to `tests/roadmap/test_roadmap_stage_content.py`: an other group whose changes are all under tests and whose implementation names no test function is refused, the same group with `test_conditional_group` in a code span is accepted, an other group that also changes `src/devops_cli/roadmap/stage_change.py` is accepted, and the refusal sentence holds the title of the group
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` fails on the base
- [ ] 1.2 Add the refusal sentence to the messages table in `src/devops_cli/lang/en/messages.py`, formatted with the group title. Add a helper in `src/devops_cli/roadmap/stage_change.py` that reads each code span of the implementation and accepts a span that starts with `test_` or ends with `::test_`, with optional parentheses. Call it from `content_problems` for each other group whose changes all start with tests
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` passes

## 2. State the rule in the planner prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`.

- [ ] 2.1 State in `src/devops_cli/ai/tasks/roadmap_stage_change.md` that a group gives one exact change: the planner names the failing test that the change updates in a code span, or it plans no group. State that a group never fixes a test only if it breaks
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes
- [ ] 2.2 The prompt is the planner's instruction, so the rule is written there and in no other document, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
